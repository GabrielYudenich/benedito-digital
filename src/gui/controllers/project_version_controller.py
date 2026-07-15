"""GUI orchestration for local project branches and collaboration packages."""

from __future__ import annotations

import os
import shutil
from pathlib import Path
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
        stop_review = getattr(editor, "stop_frame_review", None)
        if stop_review is not None:
            stop_review(silent=True)
        artifacts = {}
        mask_path = editor._mask_path_for_frame(info["path"])
        legacy_mask_path = editor._legacy_mask_path_for_frame(info["path"])
        reset_paths = [
            ("previous_mask", mask_path),
            ("previous_legacy_mask", legacy_mask_path),
            (
                "previous_auto_mask",
                editor._auto_mask_path_for_frame(info["path"]),
            ),
            (
                "previous_selection",
                editor._selection_path_for_frame(info["path"]),
            ),
            ("previous_result", os.path.join(editor.restored_dir, info["filename"])),
            (
                "previous_manual_stabilization",
                os.path.join(editor.manual_stab_dir, info["filename"]),
            ),
            (
                "previous_auto_stabilization",
                os.path.join(editor.auto_stab_dir, info["filename"]),
            ),
            (
                "previous_tone_normalization",
                os.path.join(
                    getattr(
                        editor,
                        "tone_normalized_dir",
                        os.path.join(os.path.dirname(editor.restored_dir), "tone_normalized"),
                    ),
                    info["filename"],
                ),
            ),
            ("previous_upscale", os.path.join(editor.upscaled_dir, info["filename"])),
        ]
        layers_root = Path(editor.clean_plate_layers_dir)
        if layers_root.is_dir():
            for layer_index, layer_root in enumerate(layers_root.iterdir()):
                if not layer_root.is_dir():
                    continue
                for kind in ("composite", "corrected", "reveal_masks"):
                    reset_paths.append(
                        (
                            f"previous_plate_{kind}_{layer_index}",
                            str(layer_root / kind / info["filename"]),
                        )
                    )
        for artifact_name, path in reset_paths:
            if os.path.exists(path):
                artifacts[artifact_name] = path
        editor.workspace.commit_operation(
            "frame.reset",
            payload={"target": "original"},
            frame_number=info["index"],
            artifacts=artifacts,
        )
        for _artifact_name, path in reset_paths:
            if os.path.exists(path):
                os.remove(path)
        editor._current_mask = None
        editor._current_mask_path = None
        editor._selection_mask = None
        editor._selection_frame_path = None
        editor._clean_plate_layers_cache = None
        if hasattr(editor, "_review_preview_cache"):
            editor._review_preview_cache.clear()
        if hasattr(editor, "_review_preview_order"):
            editor._review_preview_order.clear()
        retouch_controller = getattr(editor, "retouch_controller", None)
        if retouch_controller is not None:
            retouch_controller.reset_for_branch()
        editor.view_mode = "original"
        editor.status_var.set(f"Frame {info['index'] + 1} restaurado ao original")
        editor.show_current_frame()

    def reset_all_results_to_original(self):
        editor = self.editor
        if not self._workspace_available():
            return
        if not messagebox.askyesno(
            "Reset total dos resultados",
            "Descartar todas as derivações desta branch e voltar a visualizar os "
            "frames extraídos do filme original?\n\n"
            "Serão removidos: restauração, estabilização, upscale, máscaras, "
            "seleções, camadas de placa e checkpoints.\n\n"
            "O vídeo original, os frames extraídos, o proxy e as placas limpas "
            "salvas serão preservados.",
        ):
            return
        stop_review = getattr(editor, "stop_frame_review", None)
        if stop_review is not None:
            stop_review(silent=True)

        worktree = Path(editor.workspace.branch_worktree()).resolve()
        targets = [
            ("restauração", Path(editor.restored_dir)),
            ("estabilização manual", Path(editor.manual_stab_dir)),
            ("estabilização automática", Path(editor.auto_stab_dir)),
            (
                "normalização tonal",
                Path(getattr(editor, "tone_normalized_dir", worktree / "tone_normalized")),
            ),
            ("upscale", Path(editor.upscaled_dir)),
            ("máscaras manuais", Path(editor.masks_dir)),
            ("máscaras automáticas", Path(editor.auto_masks_dir)),
            ("seleções", Path(editor.selections_dir)),
            ("camadas de placa", Path(editor.clean_plate_layers_dir)),
            ("checkpoints", worktree / ".jobs"),
        ]

        def reset_task(context):
            removed_files = 0
            cleared = []
            for position, (label, raw_path) in enumerate(targets):
                context.check_cancelled()
                target = raw_path.resolve()
                if target == worktree or worktree not in target.parents:
                    raise RuntimeError(
                        f"Diretório de {label} está fora da área de trabalho: {target}"
                    )
                if target.exists():
                    removed_files += sum(1 for path in target.rglob("*") if path.is_file())
                    shutil.rmtree(target)
                    cleared.append(label)
                target.mkdir(parents=True, exist_ok=True)
                context.report(
                    (position + 1) * 100.0 / len(targets),
                    f"Limpando {label} — {position + 1}/{len(targets)}",
                )
            editor.workspace.commit_operation(
                "project.reset_results",
                payload={
                    "target": "extracted_original_frames",
                    "directories": cleared,
                    "removed_files": removed_files,
                    "preserved": ["sources", "frames", "proxy", "clean_plates"],
                },
            )
            return {"removed_files": removed_files, "directories": len(cleared)}

        def reset_complete(result):
            for attribute in (
                "use_manual_stab_var",
                "use_auto_stab_var",
                "view_upscale_var",
                "use_upscale_render_var",
            ):
                variable = getattr(editor, attribute, None)
                if variable is not None:
                    variable.set(False)
            editor._current_mask = None
            editor._current_mask_path = None
            editor._selection_mask = None
            editor._selection_frame_path = None
            editor._clean_plate_layers_cache = None
            if hasattr(editor, "_review_preview_cache"):
                editor._review_preview_cache.clear()
            if hasattr(editor, "_review_preview_order"):
                editor._review_preview_order.clear()
            retouch_controller = getattr(editor, "retouch_controller", None)
            if retouch_controller is not None:
                retouch_controller.reset_for_branch()
            editor.view_mode = "original"
            editor.status_var.set(
                f"Reset total concluído — {result['removed_files']} arquivos derivados removidos"
            )
            editor.show_current_frame()
            messagebox.showinfo(
                "Reset total concluído",
                f"{result['removed_files']} arquivos derivados foram removidos de "
                f"{result['directories']} áreas.\n\n"
                "A visualização voltou aos frames extraídos do filme original. "
                "As placas limpas continuam disponíveis para edição.",
            )

        editor._start_ui_job(
            "Resetar resultados para o original", reset_task, reset_complete
        )

    def reset_camera_segment_results(self, segment):
        editor = self.editor
        if not self._workspace_available() or not editor.frame_manager:
            return
        if not messagebox.askyesno(
            "Resetar posicionamento",
            f"Descartar somente os resultados de {segment.name} — frames "
            f"{segment.start + 1}–{segment.end + 1}?\n\n"
            "Outros posicionamentos, os frames extraídos e as placas salvas serão preservados.",
        ):
            return
        stop_review = getattr(editor, "stop_frame_review", None)
        if stop_review is not None:
            stop_review(silent=True)

        frames = list(editor.frame_manager.frames)
        if not frames:
            return
        start = max(0, min(int(segment.start), len(frames) - 1))
        end = max(start, min(int(segment.end), len(frames) - 1))
        frames_dir = editor.frame_manager.frames_dir
        layer_roots = []
        layers_dir = Path(editor.clean_plate_layers_dir)
        if layers_dir.is_dir():
            layer_roots = [path for path in layers_dir.iterdir() if path.is_dir()]

        def reset_task(context):
            removed_files = 0
            for position, frame_index in enumerate(range(start, end + 1)):
                context.check_cancelled()
                filename = frames[frame_index]
                frame_path = os.path.join(frames_dir, filename)
                paths = [
                    os.path.join(editor.restored_dir, filename),
                    os.path.join(editor.manual_stab_dir, filename),
                    os.path.join(editor.auto_stab_dir, filename),
                    os.path.join(
                        getattr(
                            editor,
                            "tone_normalized_dir",
                            os.path.join(os.path.dirname(editor.restored_dir), "tone_normalized"),
                        ),
                        filename,
                    ),
                    os.path.join(editor.upscaled_dir, filename),
                    editor._mask_path_for_frame(frame_path),
                    editor._legacy_mask_path_for_frame(frame_path),
                    editor._auto_mask_path_for_frame(frame_path),
                    editor._selection_path_for_frame(frame_path),
                ]
                for layer_root in layer_roots:
                    paths.extend(
                        str(layer_root / kind / filename)
                        for kind in ("composite", "corrected", "reveal_masks")
                    )
                for path in paths:
                    if os.path.isfile(path):
                        os.remove(path)
                        removed_files += 1
                context.report(
                    (position + 1) * 95.0 / (end - start + 1),
                    f"Resetando {segment.name} — {position + 1}/{end - start + 1}",
                )

            checkpoints = Path(editor.workspace.branch_worktree()) / ".jobs"
            if checkpoints.is_dir():
                shutil.rmtree(checkpoints)
            checkpoints.mkdir(parents=True, exist_ok=True)
            editor.workspace.commit_operation(
                "camera_segment.reset_results",
                payload={
                    "id": segment.id,
                    "name": segment.name,
                    "start": start,
                    "end": end,
                    "removed_files": removed_files,
                    "target": "extracted_original_frames",
                },
            )
            context.report(100, f"{segment.name} restaurado aos frames originais")
            return removed_files

        def reset_complete(removed_files):
            editor._current_mask = None
            editor._current_mask_path = None
            editor._selection_mask = None
            editor._selection_frame_path = None
            editor._clean_plate_layers_cache = None
            if hasattr(editor, "_review_preview_cache"):
                editor._review_preview_cache.clear()
            if hasattr(editor, "_review_preview_order"):
                editor._review_preview_order.clear()
            retouch_controller = getattr(editor, "retouch_controller", None)
            if retouch_controller is not None:
                retouch_controller.reset_for_branch()
            editor.view_mode = "original"
            editor._apply_camera_segment(segment)
            editor.status_var.set(
                f"{segment.name} resetado — {removed_files} arquivos derivados removidos"
            )
            messagebox.showinfo(
                "Posicionamento resetado",
                f"{segment.name} voltou aos frames extraídos do filme original.\n\n"
                f"Arquivos derivados removidos: {removed_files}.",
            )

        editor._start_ui_job(
            f"Resetar {segment.name}", reset_task, reset_complete
        )

    def _workspace_available(self) -> bool:
        editor = self.editor
        if editor._active_job_id:
            messagebox.showwarning("Versionamento", "Aguarde ou cancele a tarefa atual.")
            return False
        if not editor.workspace:
            messagebox.showerror("Versionamento", "Workspace local indisponível.")
            return False
        return True
