"""Proxy creation explanation and quality selection."""

import tkinter as tk
from tkinter import ttk


class ProxyDialog:
    OPTIONS = {
        "Leve — 960 px": 960,
        "Equilibrado — 1280 px": 1280,
        "Detalhado — 1920 px": 1920,
    }

    def __init__(self, parent, video_info, start_callback):
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Criar proxy de edição")
        self.window.geometry("580x440")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(
            self.window,
            text="Deixar a edição mais leve",
            font=("Segoe UI", 21, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text=(
                "Um proxy é uma cópia menor usada somente para assistir, navegar e marcar. "
                "O original continua intacto e será usado na restauração e no render final."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 18))

        width = int((video_info or {}).get("width", 0) or 0)
        height = int((video_info or {}).get("height", 0) or 0)
        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24)
        tk.Label(
            panel,
            text=f"Original detectado: {width} × {height}" if width else "Resolução original não detectada",
            font=("Segoe UI", 11, "bold"),
            fg="#f5f3f7",
            bg="#241c31",
        ).pack(anchor=tk.W)
        tk.Label(
            panel,
            text="O proxy pode ser apagado e recriado a qualquer momento.",
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#241c31",
        ).pack(anchor=tk.W, pady=(4, 0))

        controls = tk.Frame(self.window, bg="#17131f")
        controls.pack(fill=tk.X, padx=24, pady=20)
        tk.Label(controls, text="Qualidade do proxy", font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        recommended = self.recommended_option(width)
        self.option_var = tk.StringVar(value=recommended)
        ttk.Combobox(
            controls,
            textvariable=self.option_var,
            values=list(self.OPTIONS),
            state="readonly",
            font=("Segoe UI", 11),
        ).pack(fill=tk.X, pady=(6, 4))
        tk.Label(
            controls,
            text="Equilibrado é adequado para a maioria dos computadores.",
            font=("Segoe UI", 9),
            fg="#b8afc4",
            bg="#17131f",
        ).pack(anchor=tk.W)

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(buttons, text="Agora não", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Criar proxy", command=self._start, bg="#a855f7", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)

    def _start(self):
        width = self.OPTIONS[self.option_var.get()]
        self.window.destroy()
        self.start_callback(width)

    @classmethod
    def recommended_option(cls, source_width):
        if source_width and source_width <= 1280:
            return "Leve — 960 px"
        return "Equilibrado — 1280 px"
