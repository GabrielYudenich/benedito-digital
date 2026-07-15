"""Guided local damage analysis options."""

import tkinter as tk
from tkinter import ttk


class DamageAnalysisDialog:
    SENSITIVITY_LABELS = {
        "Conservadora — menos marcações": "low",
        "Equilibrada — recomendada": "normal",
        "Sensível — encontra mais suspeitas": "high",
    }

    def __init__(self, parent, range_start, range_end, total_frames, start_callback):
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Analisar danos nos frames")
        self.window.geometry("620x500")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Localizar frames para revisão", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text=(
                "A análise procura poeira, riscos, manchas, perfurações, deslocamentos, frames vazios e duplicações. "
                "Ela apenas cria marcações na timeline; nenhuma imagem é modificada."
            ),
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 18))

        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24)
        self.scope_var = tk.StringVar(value="range")
        tk.Radiobutton(panel, text=f"Intervalo atual: {range_start}–{range_end}", variable=self.scope_var, value="range", fg="#f5f3f7", bg="#241c31", selectcolor="#352a45", activebackground="#241c31", activeforeground="#f5f3f7", font=("Segoe UI", 11)).pack(anchor=tk.W, pady=4)
        tk.Radiobutton(panel, text=f"Projeto inteiro: {total_frames} frames", variable=self.scope_var, value="all", fg="#f5f3f7", bg="#241c31", selectcolor="#352a45", activebackground="#241c31", activeforeground="#f5f3f7", font=("Segoe UI", 11)).pack(anchor=tk.W, pady=4)

        controls = tk.Frame(self.window, bg="#17131f")
        controls.pack(fill=tk.X, padx=24, pady=18)
        tk.Label(controls, text="Sensibilidade", font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        self.sensitivity_var = tk.StringVar(value="Equilibrada — recomendada")
        ttk.Combobox(controls, textvariable=self.sensitivity_var, values=list(self.SENSITIVITY_LABELS), state="readonly", font=("Segoe UI", 11)).pack(fill=tk.X, pady=(6, 12))

        info = tk.Frame(self.window, bg="#162a22", padx=14, pady=12)
        info.pack(fill=tk.X, padx=24)
        tk.Label(info, text="Revisão humana continua importante", font=("Segoe UI", 11, "bold"), fg="#22c55e", bg="#162a22").pack(anchor=tk.W)
        tk.Label(info, text="Filmes antigos possuem grão, cortes e características que podem parecer danos. As marcações são sugestões, não decisões automáticas.", font=("Segoe UI", 10), fg="#f5f3f7", bg="#162a22", wraplength=530, justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 0))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(buttons, text="Cancelar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Iniciar análise", command=self._start, bg="#a855f7", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)

    def _start(self):
        scope = self.scope_var.get()
        sensitivity = self.SENSITIVITY_LABELS[self.sensitivity_var.get()]
        self.window.destroy()
        self.start_callback(scope, sensitivity)
