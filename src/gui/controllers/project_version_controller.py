"""GUI orchestration for local project branches and collaboration packages."""

from __future__ import annotations

import os
from tkinter import messagebox, simpledialog

from gui.dialogs.branch_manager import BranchManagerDialog
from gui.dialogs.branch_merge_dialog import BranchMergeDialog


class ProjectVersionController:
    def __init__(self, editor):
        self.editor = editor

    def open_manager(self):
        editor = self.editor
        if editor._active_job_id:
            messagebox.showwarning("Versionamento", "Aguarde ou cancele a tarefa atual.")
            return
        if not editor.workspace:
            messagebox.showerror("Versionamento", "Workspace local indisponível.")
            return
        BranchManagerDialog(
            editor.root,
            editor.workspace,
            self.on_branch_changed,
            export_callback=self.export_branch_package,
            import_callback=self.import_branch_package,
            merge_callback=self.open_branch_merge,
        )

    def export_branch_package(self, branch_name, package_path):
        editor = self.editor

        def export_task(context):
            try:
                return editor.workspace.export_branch(
                    package_path,
                    branch_name=branch_name,
                    progress_callback=lambda progress: context.report(
                        progress, "Empacotando alterações da branch..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except Exception:
                context.check_cancelled()
                raise

        def export_complete(_manifest):
            messagebox.showinfo(
                "Branch exportada",
                f"Pacote salvo em:\n{package_path}\n\nO vídeo original não foi incluído.",
            )

        editor._start_ui_job("Exportação de branch", export_task, export_complete)

    def import_branch_package(self, package_path):
        editor = self.editor
        target_branch = editor.workspace.active_branch

        def import_task(context):
            try:
                return editor.workspace.import_branch(
                    package_path,
                    progress_callback=lambda progress: context.report(
                        progress, "Verificando e importando alterações..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except Exception:
                context.check_cancelled()
                raise

        def import_complete(branch_name):
            compare_now = messagebox.askyesno(
                "Branch importada",
                f"A branch '{branch_name}' foi verificada. O vídeo original não foi duplicado.\n\n"
                f"Deseja comparar e mesclar esse trabalho na branch '{target_branch}' agora?",
            )
            if compare_now:
                self.open_branch_merge(branch_name, target_branch)

        editor._start_ui_job("Importação de branch", import_task, import_complete)

    def open_branch_merge(self, source_branch, target_branch):
        editor = self.editor
        try:
            BranchMergeDialog(
                editor.root,
                editor.workspace,
                target_branch,
                source_branch,
                self.merge_branch,
            )
        except Exception as error:
            messagebox.showerror("Não foi possível comparar", str(error))

    def merge_branch(self, source_branch, target_branch, resolutions):
        editor = self.editor

        def merge_task(context):
            context.report(10, "Comparando históricos das branches...")
            result = editor.workspace.merge_branch(
                source_branch,
                resolutions=resolutions,
                target_branch=target_branch,
            )
            context.report(95, "Atualizando a branch mesclada...")
            return result

        def merge_complete(result):
            editor.workspace.checkout(target_branch)
            self.on_branch_changed()
            messagebox.showinfo(
                "Mesclagem concluída",
                f"{result['replayed_operations']} operação(ões) recebida(s).\n"
                f"{result['conflicts']} conflito(s) resolvido(s) por frame.",
            )

        editor._start_ui_job("Mesclagem de branches", merge_task, merge_complete)

    def create_local_branch(self):
        editor = self.editor
        if not self._workspace_available():
            return
        name = simpledialog.askstring(
            "Nova branch", "Nome da branch (exemplo: rolo-1):", parent=editor.root
        )
        if not name:
            return
        try:
            editor.workspace.create_branch(name.strip())
            editor.workspace.checkout(name.strip())
            self.on_branch_changed()
        except Exception as error:
            messagebox.showerror("Versionamento", str(error))

    def checkout_local_branch(self):
        editor = self.editor
        if not self._workspace_available():
            return
        names = [branch["name"] for branch in editor.workspace.list_branches()]
        name = simpledialog.askstring(
            "Trocar branch",
            "Branches disponíveis:\n" + "\n".join(names) + "\n\nDigite o nome:",
            parent=editor.root,
        )
        if not name:
            return
        try:
            editor.workspace.checkout(name.strip())
            self.on_branch_changed()
        except Exception as error:
            messagebox.showerror("Versionamento", str(error))

    def on_branch_changed(self):
        editor = self.editor
        editor._configure_branch_paths()
        editor.retouch_controller.reset_for_branch()
        editor._current_mask = None
        editor._current_mask_path = None
        editor._selection_mask = None
        editor._selection_frame_path = None
        editor.view_mode = "original"
        editor.status_var.set(f"Branch atual: {editor.workspace.active_branch}")
        editor.show_current_frame()

    def show_current_frame_history(self):
        editor = self.editor
        if not editor.workspace or not editor.frame_manager:
            return
        info = editor.frame_manager.get_current_frame_info()
        if not info:
            return
        history = editor.workspace.get_frame_history(info["index"])
        if not history:
            text = "Este frame ainda não possui operações nesta branch."
        else:
            text = "\n".join(
                f"{index + 1}. {operation['type']} — {operation['created_at']}"
                for index, operation in enumerate(history)
            )
        messagebox.showinfo(
            f"Histórico — frame {info['index'] + 1}",
            f"Branch: {editor.workspace.active_branch}\n\n{text}",
        )

    def reset_current_frame_to_original(self):
        editor = self.editor
        if not editor.workspace or not editor.frame_manager:
            return
        info = editor.frame_manager.get_current_frame_info()
        if not info:
            return
        if not messagebox.askyesno(
            "Resetar frame", "Descartar as alterações desta branch para este frame?"
        ):
            return
        artifacts = {}
        mask_path = editor._mask_path_for_frame(info["path"])
        legacy_mask_path = editor._legacy_mask_path_for_frame(info["path"])
        if os.path.exists(mask_path):
            artifacts["previous_mask"] = mask_path
        elif os.path.exists(legacy_mask_path):
            artifacts["previous_mask"] = legacy_mask_path
        restored_path = os.path.join(editor.restored_dir, info["filename"])
        if os.path.exists(restored_path):
            artifacts["previous_result"] = restored_path
        editor.workspace.commit_operation(
            "frame.reset",
            payload={"target": "original"},
            frame_number=info["index"],
            artifacts=artifacts,
        )
        for path in (mask_path, legacy_mask_path, restored_path):
            if os.path.exists(path):
                os.remove(path)
        editor._current_mask = None
        editor._current_mask_path = None
        editor.view_mode = "original"
        editor.status_var.set(f"Frame {info['index'] + 1} restaurado ao original")
        editor.show_current_frame()

    def _workspace_available(self) -> bool:
        editor = self.editor
        if editor._active_job_id:
            messagebox.showwarning("Versionamento", "Aguarde ou cancele a tarefa atual.")
            return False
        if not editor.workspace:
            messagebox.showerror("Versionamento", "Workspace local indisponível.")
            return False
        return True
