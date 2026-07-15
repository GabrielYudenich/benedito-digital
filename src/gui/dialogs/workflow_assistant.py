"""Beginner-friendly restoration workflow assistant."""

import tkinter as tk


class WorkflowAssistant:
    def __init__(self, parent, actions):
        self.window = tk.Toplevel(parent)
        self.window.title("Assistente de restauração")
        self.window.geometry("720x650")
        self.window.minsize(620, 520)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        canvas = tk.Canvas(self.window, bg="#17131f", highlightthickness=0)
        scrollbar = tk.Scrollbar(self.window, orient=tk.VERTICAL, command=canvas.yview)
        content = tk.Frame(canvas, bg="#17131f")
        content.bind("<Configure>", lambda _event: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=content, anchor="nw", width=680)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        tk.Label(content, text="Vamos restaurar juntos", font=("Segoe UI", 23, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            content,
            text="Você pode seguir estas etapas ou usar as ferramentas livremente. Nada aqui altera o original.",
            font=("Segoe UI", 11), fg="#b8afc4", bg="#17131f", wraplength=620, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 14))

        steps = [
            ("1", "Adicionar o material original", "O arquivo será copiado e verificado. Isso pode demorar em vídeos grandes.", "Escolher vídeo", actions.get("import")),
            ("2", "Preparar os frames", "Extraia frames sem perda. Uma janela mostrará porcentagem e tempo restante.", "Abrir preparação", actions.get("prepare")),
            ("3", "Inspecionar e selecionar", "Navegue quadro a quadro, marque início e fim ou pinte uma máscara sobre a sujeira.", "Abrir frames", actions.get("frames")),
            ("4", "Aplicar restauração", "Escolha um perfil simples ou ajuste ferramentas avançadas quando precisar.", "Abrir restauração", actions.get("restore")),
            ("5", "Comparar e exportar", "Confira original e restaurado antes de gerar o arquivo final.", "Abrir exportação", actions.get("export")),
        ]
        for number, title, description, button_text, command in steps:
            self._step(content, number, title, description, button_text, command)

        tk.Button(
            content, text="Fechar assistente", command=self.window.destroy, bg="#352a45", fg="white",
            relief=tk.FLAT, padx=18, pady=10, font=("Segoe UI", 10, "bold"),
        ).pack(anchor=tk.E, padx=24, pady=(8, 24))

    def _step(self, parent, number, title, description, button_text, command):
        panel = tk.Frame(parent, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24, pady=6)
        badge = tk.Label(panel, text=number, width=3, font=("Segoe UI", 14, "bold"), fg="white", bg="#a855f7")
        badge.pack(side=tk.LEFT, anchor=tk.N, padx=(0, 14))
        body = tk.Frame(panel, bg="#241c31")
        body.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        tk.Label(body, text=title, font=("Segoe UI", 13, "bold"), fg="#f5f3f7", bg="#241c31").pack(anchor=tk.W)
        tk.Label(body, text=description, font=("Segoe UI", 10), fg="#b8afc4", bg="#241c31", wraplength=430, justify=tk.LEFT).pack(anchor=tk.W, pady=(3, 8))
        if command:
            tk.Button(body, text=button_text, command=lambda: self._run(command), bg="#3b82f6", fg="white", relief=tk.FLAT, padx=12, pady=7).pack(anchor=tk.W)

    def _run(self, command):
        self.window.withdraw()
        command()
