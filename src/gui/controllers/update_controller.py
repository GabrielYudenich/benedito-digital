"""User-controlled update notification flow."""

import json
import webbrowser

from tkinter import messagebox

from core.app_info import get_app_info
from core.paths import resource_path
from core.updates import UpdateChecker


class UpdateController:
    def __init__(self, editor):
        self.editor = editor

    def check(self):
        config = json.loads(resource_path("config.json").read_text(encoding="utf-8"))
        updates = config.get("updates", {})
        manifest_url = updates.get("manifest_url")
        if not manifest_url:
            messagebox.showinfo("Atualizações", "O canal de atualização não está configurado.")
            return

        def task(context):
            context.report(10, "Consultando canal oficial...")
            result = UpdateChecker(manifest_url).check(get_app_info().version)
            context.report(100, "Consulta concluída")
            return result

        def complete(result):
            if not result.available:
                messagebox.showinfo("Atualizações", f"Você já usa a versão mais recente ({result.current_version}).")
                return
            open_release = messagebox.askyesno(
                "Atualização disponível",
                f"Versão instalada: {result.current_version}\nNova versão: {result.latest_version}\n\n{result.notes}\n\nAbrir a página oficial da versão?",
            )
            if open_release:
                webbrowser.open(result.release_url)

        self.editor._start_ui_job("Verificação de atualização", task, complete)
