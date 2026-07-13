"""Guided restoration workflows for different source materials."""

import os
import tkinter as tk
from tkinter import filedialog, ttk


class RestorationWorkflowDialog:
    def __init__(self, parent, select_callback):
        self.window = tk.Toplevel(parent)
        self.window.title("Escolher fluxo de restauração")
        self.window.geometry("760x620")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Que material você está restaurando?", font=("Segoe UI", 22, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(self.window, text="O Benedito prepara as ferramentas recomendadas. Você continua podendo alterar qualquer ajuste.", font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=690, justify=tk.LEFT).pack(anchor=tk.W, padx=24, pady=(0, 14))

        self._card(
            "Filme quadro a quadro",
            "Para películas digitalizadas, riscos, poeira, manchas, furos e correções manuais por frame.",
            ["FPS original e PNG sem perda", "Análise de danos", "Seleção, máscara e restauração temporal"],
            lambda: self._select(select_callback, "film"),
            "#a855f7",
        )
        self._card(
            "VHS e vídeo entrelaçado",
            "Para fitas com linhas entrelaçadas, ruído de luminância/cor e instabilidade de captura.",
            ["Desentrelaçamento", "Denoise temporal/espacial", "Estabilização opcional"],
            lambda: self._select(select_callback, "vhs"),
            "#3b82f6",
        )
        self._card(
            "Melhoria rápida e conservadora",
            "Para materiais razoavelmente preservados que precisam de limpeza leve e comparação antes/depois.",
            ["Denoise moderado", "Sem upscale automático", "Resultado reversível"],
            lambda: self._select(select_callback, "quick"),
            "#22c55e",
        )

        tk.Button(self.window, text="Fechar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(anchor=tk.E, padx=24, pady=16)

    def _card(self, title, description, bullets, command, color):
        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24, pady=6)
        stripe = tk.Frame(panel, bg=color, width=6)
        stripe.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 14))
        body = tk.Frame(panel, bg="#241c31")
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(body, text=title, font=("Segoe UI", 14, "bold"), fg="#f5f3f7", bg="#241c31").pack(anchor=tk.W)
        tk.Label(body, text=description, font=("Segoe UI", 10), fg="#b8afc4", bg="#241c31", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 5))
        tk.Label(body, text=" • " + "\n • ".join(bullets), font=("Segoe UI", 9), fg="#d8d1df", bg="#241c31", justify=tk.LEFT).pack(anchor=tk.W)
        tk.Button(panel, text="Usar este fluxo", command=command, bg=color, fg="white", relief=tk.FLAT, padx=12, pady=8, font=("Segoe UI", 9, "bold")).pack(side=tk.RIGHT, padx=(12, 0))

    def _select(self, callback, workflow):
        self.window.destroy()
        callback(workflow)


class VHSProcessingDialog:
    DENOISE = {
        "Desligado": "off",
        "Leve": "light",
        "Médio — recomendado": "medium",
        "Forte": "strong",
    }

    def __init__(self, parent, default_output, start_callback):
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Restauração guiada de VHS")
        self.window.geometry("620x540")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Preparar restauração de VHS", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(self.window, text="O processamento cria um novo vídeo. O arquivo capturado permanece intacto.", font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=560, justify=tk.LEFT).pack(anchor=tk.W, padx=24, pady=(0, 16))

        options = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        options.pack(fill=tk.X, padx=24)
        self.deinterlace_var = tk.BooleanVar(value=True)
        self.stabilize_var = tk.BooleanVar(value=False)
        self._check(options, "Desentrelaçar linhas da captura", self.deinterlace_var)
        self._check(options, "Estabilizar tremores leves", self.stabilize_var)
        tk.Label(options, text="Redução de ruído", font=("Segoe UI", 10, "bold"), fg="#f5f3f7", bg="#241c31").pack(anchor=tk.W, pady=(12, 4))
        self.denoise_var = tk.StringVar(value="Médio — recomendado")
        ttk.Combobox(options, textvariable=self.denoise_var, values=list(self.DENOISE), state="readonly", font=("Segoe UI", 10)).pack(fill=tk.X)

        output = tk.Frame(self.window, bg="#17131f")
        output.pack(fill=tk.X, padx=24, pady=18)
        tk.Label(output, text="Arquivo restaurado", font=("Segoe UI", 10, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        row = tk.Frame(output, bg="#17131f")
        row.pack(fill=tk.X, pady=(6, 0))
        self.output_var = tk.StringVar(value=default_output)
        tk.Entry(row, textvariable=self.output_var, font=("Segoe UI", 10)).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(row, text="Escolher...", command=self._browse, bg="#352a45", fg="white", relief=tk.FLAT, padx=10, pady=5).pack(side=tk.RIGHT, padx=(6, 0))

        warning = tk.Frame(self.window, bg="#332711", padx=14, pady=12)
        warning.pack(fill=tk.X, padx=24)
        tk.Label(warning, text="Faça primeiro um trecho curto quando possível", font=("Segoe UI", 10, "bold"), fg="#fbbf24", bg="#332711").pack(anchor=tk.W)
        tk.Label(warning, text="Denoise forte pode apagar textura e detalhes. O nível Médio é um ponto de partida, não uma regra.", font=("Segoe UI", 9), fg="#f5f3f7", bg="#332711", wraplength=520, justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 0))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(buttons, text="Cancelar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Iniciar restauração", command=self._start, bg="#3b82f6", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)

    def _check(self, parent, text, variable):
        tk.Checkbutton(parent, text=text, variable=variable, font=("Segoe UI", 10), fg="#f5f3f7", bg="#241c31", selectcolor="#352a45", activebackground="#241c31", activeforeground="#f5f3f7").pack(anchor=tk.W, pady=3)

    def _browse(self):
        path = filedialog.asksaveasfilename(defaultextension=".mp4", filetypes=[("Vídeo MP4", "*.mp4")])
        if path:
            self.output_var.set(path)

    def _start(self):
        output = self.output_var.get().strip()
        if not output:
            return
        config = {
            "output": output,
            "deinterlace": bool(self.deinterlace_var.get()),
            "stabilize": bool(self.stabilize_var.get()),
            "denoise": self.DENOISE[self.denoise_var.get()],
        }
        self.window.destroy()
        self.start_callback(config)
