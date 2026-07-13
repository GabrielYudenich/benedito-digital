"""Accessible export profile chooser."""

from __future__ import annotations

import os
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, Optional


PROFILES = {
    "Entrega MP4 (menor e compatível)": {
        "key": "delivery",
        "extension": ".mp4",
        "description": "Ideal para assistir, compartilhar e publicar. Usa H.264 e áudio AAC.",
    },
    "Intermediário MOV (alta qualidade)": {
        "key": "mezzanine",
        "extension": ".mov",
        "description": "Ideal para continuar editando. Usa ProRes 422 HQ e áudio PCM.",
    },
    "Arquivo MKV (sem perda)": {
        "key": "archive",
        "extension": ".mkv",
        "description": "Ideal para preservação. Usa FFV1 e áudio FLAC, mas gera arquivos grandes.",
    },
}


class ExportDialog:
    def __init__(self, parent, initial_dir: Optional[str] = None, title: str = "Exportar vídeo"):
        self.result: Optional[Dict] = None
        self.initial_dir = initial_dir or os.getcwd()
        self.window = tk.Toplevel(parent)
        self.window.title(title)
        self.window.geometry("650x430")
        self.window.minsize(560, 390)
        self.window.transient(parent)
        self.window.grab_set()

        container = ttk.Frame(self.window, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(container, text="Como deseja guardar este vídeo?", font=("Arial", 15, "bold")).pack(anchor=tk.W)
        ttk.Label(
            container,
            text="Escolha pelo uso. O Benedito manterá a duração e poderá trazer o áudio do material original.",
            wraplength=590,
        ).pack(anchor=tk.W, pady=(5, 18))

        self.profile_var = tk.StringVar(value=next(iter(PROFILES)))
        profile_combo = ttk.Combobox(
            container,
            textvariable=self.profile_var,
            values=list(PROFILES),
            state="readonly",
            font=("Arial", 11),
        )
        profile_combo.pack(fill=tk.X)
        profile_combo.bind("<<ComboboxSelected>>", self._profile_changed)

        self.description_var = tk.StringVar()
        ttk.Label(container, textvariable=self.description_var, wraplength=590).pack(anchor=tk.W, pady=(8, 18))

        ttk.Label(container, text="Arquivo de saída:", font=("Arial", 10, "bold")).pack(anchor=tk.W)
        path_row = ttk.Frame(container)
        path_row.pack(fill=tk.X, pady=(5, 14))
        self.path_var = tk.StringVar()
        ttk.Entry(path_row, textvariable=self.path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_row, text="Escolher...", command=self._browse).pack(side=tk.LEFT, padx=(8, 0))

        self.preserve_audio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            container,
            text="Incluir o áudio do material original",
            variable=self.preserve_audio_var,
        ).pack(anchor=tk.W, pady=4)
        ttk.Label(
            container,
            text="Para um trecho, o áudio começa no mesmo frame inicial da seleção.",
            foreground="#555555",
        ).pack(anchor=tk.W, pady=(0, 12))

        buttons = ttk.Frame(container)
        buttons.pack(side=tk.BOTTOM, fill=tk.X, pady=(18, 0))
        ttk.Button(buttons, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        ttk.Button(buttons, text="Começar exportação", command=self._accept).pack(side=tk.RIGHT)

        self._profile_changed()
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        profile_combo.focus_set()

    def _profile_changed(self, _event=None) -> None:
        settings = PROFILES[self.profile_var.get()]
        self.description_var.set(settings["description"])
        current = self.path_var.get().strip()
        if current:
            self.path_var.set(str(Path(current).with_suffix(settings["extension"])))

    def _browse(self) -> None:
        settings = PROFILES[self.profile_var.get()]
        extension = settings["extension"]
        path = filedialog.asksaveasfilename(
            parent=self.window,
            initialdir=self.initial_dir,
            defaultextension=extension,
            filetypes=[(f"Vídeo {extension.upper()}", f"*{extension}"), ("Todos os arquivos", "*.*")],
        )
        if path:
            self.path_var.set(str(Path(path).with_suffix(extension)))

    def _accept(self) -> None:
        output_path = self.path_var.get().strip()
        if not output_path:
            messagebox.showwarning("Arquivo necessário", "Escolha onde o vídeo será salvo.", parent=self.window)
            return
        settings = PROFILES[self.profile_var.get()]
        self.result = {
            "profile": settings["key"],
            "output_path": str(Path(output_path).with_suffix(settings["extension"])),
            "preserve_audio": self.preserve_audio_var.get(),
        }
        self.window.destroy()

    def show(self) -> Optional[Dict]:
        self.window.wait_window()
        return self.result
