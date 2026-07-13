"""Readability, keyboard, focus, and motion preferences."""

import tkinter as tk

from core.accessibility import AccessibilityPreferences


class AccessibilityDialog:
    def __init__(self, parent, preferences, apply_callback):
        self.window = tk.Toplevel(parent)
        self.window.title("Leitura e acessibilidade")
        self.window.geometry("580x530")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")
        self.preferences = preferences

        tk.Label(self.window, text="Conforto e acesso", font=("Segoe UI", 20, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text="Ajuste leitura, contraste, foco por teclado e movimento. Tab e Shift+Tab percorrem os controles.",
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=520, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        self.scale_var = tk.DoubleVar(value=preferences.scale)
        for label, value in (("Compacta", 0.9), ("Padrão", 1.0), ("Confortável", 1.15), ("Muito grande", 1.3), ("Extra grande", 1.5)):
            tk.Radiobutton(self.window, text=f"{label} — {int(value * 100)}%", variable=self.scale_var, value=value, font=("Segoe UI", 11), fg="#f5f3f7", bg="#241c31", selectcolor="#352a45", activebackground="#241c31", activeforeground="#f5f3f7", anchor=tk.W, padx=14, pady=7, takefocus=True).pack(fill=tk.X, padx=24, pady=2)

        options = tk.Frame(self.window, bg="#17131f")
        options.pack(fill=tk.X, padx=24, pady=(12, 6))
        self.high_contrast_var = tk.BooleanVar(value=preferences.high_contrast)
        self.reduced_motion_var = tk.BooleanVar(value=preferences.reduced_motion)
        self.large_focus_var = tk.BooleanVar(value=preferences.large_focus)
        for text, variable in (
            ("Contraste elevado", self.high_contrast_var),
            ("Reduzir animações e transições visuais", self.reduced_motion_var),
            ("Contorno de foco reforçado para teclado", self.large_focus_var),
        ):
            tk.Checkbutton(options, text=text, variable=variable, fg="#f5f3f7", bg="#17131f", selectcolor="#352a45", activebackground="#17131f", activeforeground="#f5f3f7", takefocus=True).pack(anchor=tk.W, pady=4)

        shortcuts = tk.LabelFrame(self.window, text="Atalhos principais", fg="#d8d2df", bg="#17131f", padx=10, pady=8)
        shortcuts.pack(fill=tk.X, padx=24, pady=8)
        tk.Label(shortcuts, text="←/→ frames  •  I/O intervalo  •  Ctrl+Z/Y histórico\nCtrl+Shift+T timeline  •  Ctrl+Shift+C equipe  •  Ctrl+Shift+S scopes", fg="#b8afc4", bg="#17131f", justify=tk.LEFT).pack(anchor=tk.W)

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, padx=24, pady=16)
        tk.Button(buttons, text="Cancelar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=15, pady=8, takefocus=True).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Aplicar", command=lambda: self._apply(apply_callback), bg="#a855f7", fg="white", relief=tk.FLAT, padx=15, pady=8, takefocus=True).pack(side=tk.RIGHT, padx=8)

    def _apply(self, callback):
        callback(
            AccessibilityPreferences(
                scale=self.scale_var.get(),
                high_contrast=self.high_contrast_var.get(),
                reduced_motion=self.reduced_motion_var.get(),
                large_focus=self.large_focus_var.get(),
            ).normalized()
        )
        self.window.destroy()
