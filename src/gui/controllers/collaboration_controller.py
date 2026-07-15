"""GUI orchestration for secure shared-folder collaboration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from tkinter import messagebox

from core.collaboration import FolderCollaborationRemote
from gui.dialogs.collaboration_dialog import CollaborationDialog


class CollaborationController:
    def __init__(self, editor):
        self.editor = editor

    @property
    def settings_file(self):
        return Path(self.editor.workspace.cache_dir) / "collaboration.json"

    def open_dialog(self):
        CollaborationDialog(
            self.editor.root,
            self.editor.workspace,
            self.load_remote_path(),
            self.push,
            self.pull,
        )

    def push(self, remote_path, branch_name):
        self.save_remote_path(remote_path)

        def task(context):
            remote = FolderCollaborationRemote(remote_path)
            return remote.push(
                self.editor.workspace,
                branch_name,
                progress_callback=lambda value: context.report(value, f"Enviando {branch_name} — {value:.0f}%"),
                cancel_callback=lambda: context.cancellation_requested,
            )

        def complete(result):
            self.editor.status_var.set(f"Push concluído: {result.operations} operações e {result.objects} objetos novos")
            messagebox.showinfo("Push concluído", f"Branch: {result.branch}\nNovas operações: {result.operations}\nNovos objetos: {result.objects}\nTransferidos: {self._format_size(result.transferred_bytes)}")

        self.editor._start_ui_job("Push da equipe", task, complete)

    def pull(self, remote_path, branch_name):
        self.save_remote_path(remote_path)

        def task(context):
            remote = FolderCollaborationRemote(remote_path)
            return remote.pull(
                self.editor.workspace,
                branch_name,
                progress_callback=lambda value: context.report(value, f"Trazendo {branch_name} — {value:.0f}%"),
                cancel_callback=lambda: context.cancellation_requested,
            )

        def complete(result):
            self.editor.status_var.set(f"Pull concluído: branch local {result.local_branch}")
            messagebox.showinfo("Pull concluído", f"A branch remota foi importada como:\n{result.local_branch}\n\nUse o Gerenciador de branches para revisar ou mesclar.")

        self.editor._start_ui_job("Pull da equipe", task, complete)

    def load_remote_path(self):
        try:
            data = json.loads(self.settings_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return ""
        value = data.get("remote_path", "")
        return value if isinstance(value, str) else ""

    def save_remote_path(self, remote_path):
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.settings_file.with_suffix(".tmp")
        temporary.write_text(json.dumps({"remote_path": str(Path(remote_path).expanduser())}, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, self.settings_file)

    @staticmethod
    def _format_size(value):
        size = float(value)
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.1f} {unit}"
            size /= 1024
