"""Scrollable editor for per-user keyboard shortcuts."""

import tkinter as tk
from tkinter import messagebox, ttk

from core.shortcuts import SHORTCUT_DEFINITIONS


class ShortcutSettingsDialog:
    def __init__(self, parent, preferences, save_callback):
        self.preferences = preferences
        self.save_callback = save_callback
        self.entries = {}
        self.window = tk.Toplevel(parent)
        self.window.title("Atalhos do usuário")
        self.window.geometry("680x720")
        self.window.minsize(560, 480)
        self.window.configure(bg="#17131f")
        self.window.transient(parent)
        self.window.grab_set()

        tk.Label(
            self.window,
            text="Atalhos do usuário",
            font=("Segoe UI", 20, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=24, pady=(20, 4))
        tk.Label(
            self.window,
            text=(
                "Digite combinações como Ctrl+Alt+P, Shift+S, F8 ou Left. "
                "As preferências valem para todos os projetos deste usuário."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=620,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 14))

        container = tk.Frame(self.window, bg="#241c31")
        container.pack(fill=tk.BOTH, expand=True, padx=24)
        canvas = tk.Canvas(container, bg="#241c31", highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)
        form = tk.Frame(canvas, bg="#241c31")
        window_id = canvas.create_window((0, 0), window=form, anchor=tk.NW)
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        form.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>", lambda event: canvas.itemconfig(window_id, width=event.width)
        )
        canvas.bind(
            "<MouseWheel>",
            lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"),
        )

        for row, definition in enumerate(SHORTCUT_DEFINITIONS):
            tk.Label(
                form,
                text=definition.label,
                font=("Segoe UI", 9),
                fg="#f5f3f7",
                bg="#241c31",
                anchor=tk.W,
            ).grid(row=row, column=0, sticky=tk.EW, padx=(12, 8), pady=5)
            variable = tk.StringVar(value=preferences.get(definition.action))
            entry = tk.Entry(
                form,
                textvariable=variable,
                bg="#100c17",
                fg="#f5f3f7",
                insertbackground="#c084fc",
                relief=tk.FLAT,
            )
            entry.grid(row=row, column=1, sticky=tk.EW, padx=(8, 12), pady=5)
            self.entries[definition.action] = variable
        form.columnconfigure(0, weight=1)
        form.columnconfigure(1, weight=1)

        actions = tk.Frame(self.window, bg="#17131f")
        actions.pack(fill=tk.X, padx=24, pady=18)
        tk.Button(
            actions,
            text="Restaurar padrões",
            command=self._reset,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.LEFT)
        tk.Button(
            actions,
            text="Cancelar",
            command=self.window.destroy,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.RIGHT)
        tk.Button(
            actions,
            text="Salvar atalhos",
            command=self._save,
            bg="#a855f7",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.RIGHT, padx=6)

    def _save(self):
        try:
            self.preferences.replace(
                {action: variable.get() for action, variable in self.entries.items()}
            )
        except ValueError as error:
            messagebox.showerror("Atalho inválido", str(error), parent=self.window)
            return
        self.save_callback()
        self.window.destroy()

    def _reset(self):
        defaults = {item.action: item.default for item in SHORTCUT_DEFINITIONS}
        for action, variable in self.entries.items():
            variable.set(defaults[action])
