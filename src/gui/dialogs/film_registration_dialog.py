"""Guided options for film registration from sprocket holes."""

import tkinter as tk
from tkinter import messagebox, ttk


class FilmRegistrationDialog:
    def __init__(self, parent, range_start, range_end, apply_callback):
        self.apply_callback = apply_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Alinhar película pelas perfurações")
        self.window.geometry("620x440")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")
        tk.Label(self.window, text="Registro por perfurações", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text="O Benedito localiza os furos laterais da película e corrige somente a translação necessária. Os originais permanecem imutáveis.",
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 18))
        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24)
        tk.Label(panel, text=f"Intervalo selecionado: {range_start}–{range_end}", font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#241c31").pack(anchor=tk.W, pady=(0, 10))
        self.reference_var = tk.StringVar(value="first")
        for text, value in (
            ("Usar o primeiro frame como referência — recomendado", "first"),
            ("Usar o frame anterior alinhado — acompanha variações lentas", "previous"),
        ):
            tk.Radiobutton(panel, text=text, variable=self.reference_var, value=value, fg="#f5f3f7", bg="#241c31", selectcolor="#352a45", activebackground="#241c31", activeforeground="#f5f3f7").pack(anchor=tk.W, pady=3)
        controls = tk.Frame(self.window, bg="#17131f")
        controls.pack(fill=tk.X, padx=24, pady=18)
        tk.Label(controls, text="Confiança mínima", font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        self.confidence_var = tk.DoubleVar(value=0.45)
        ttk.Scale(controls, from_=0.2, to=0.9, variable=self.confidence_var, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(6, 0))
        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(buttons, text="Cancelar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Alinhar intervalo", command=self._apply, bg="#f97316", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)

    def _apply(self):
        confidence = float(self.confidence_var.get())
        if not 0.0 < confidence <= 1.0:
            messagebox.showerror("Película", "Escolha uma confiança válida.")
            return
        self.window.destroy()
        self.apply_callback(self.reference_var.get(), confidence)
