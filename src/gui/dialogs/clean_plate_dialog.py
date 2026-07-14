"""Guided clean-plate workflow for static backgrounds."""

import tkinter as tk


class CleanPlateDialog:
    def __init__(
        self,
        parent,
        start_frame,
        end_frame,
        has_selection,
        start_callback,
    ):
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Placa limpa de fundo")
        self.window.geometry("680x540")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(
            self.window,
            text="Construir placa limpa do fundo",
            font=("Segoe UI", 21, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text=(
                f"Intervalo atual: frames {start_frame}–{end_frame}. O Benedito alinha "
                "amostras, calcula a mediana temporal e identifica somente regiões estáveis."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=620,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        safe = tk.Frame(self.window, bg="#162a22", padx=16, pady=14)
        safe.pack(fill=tk.X, padx=24)
        tk.Label(
            safe,
            text="Proteção de pessoas e objetos em movimento",
            font=("Segoe UI", 11, "bold"),
            fg="#86efac",
            bg="#162a22",
        ).pack(anchor=tk.W)
        tk.Label(
            safe,
            text=(
                "Braços, rostos e outros componentes grandes que diferem da placa são "
                "excluídos. Por segurança, a placa substitui apenas pequenos defeitos "
                "detectados dentro do fundo estável — nunca o quadro inteiro."
            ),
            font=("Segoe UI", 10),
            fg="#f5f3f7",
            bg="#162a22",
            wraplength=590,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 0))

        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.X, padx=24, pady=16)
        self.apply_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            panel,
            text="Aplicar a placa aos defeitos do intervalo após criar",
            variable=self.apply_var,
            fg="#f5f3f7",
            bg="#241c31",
            selectcolor="#352a45",
            activebackground="#241c31",
            activeforeground="#f5f3f7",
        ).pack(anchor=tk.W)
        tk.Label(
            panel,
            text=(
                "Se a câmera não for considerada estática, o processo para antes de "
                "alterar qualquer frame e recomenda separar melhor a cena."
            ),
            font=("Segoe UI", 9),
            fg="#b8afc4",
            bg="#241c31",
            wraplength=580,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(7, 0))

        selection_panel = tk.Frame(
            self.window, bg="#1d2939", padx=16, pady=14
        )
        selection_panel.pack(fill=tk.X, padx=24, pady=(0, 16))
        self.selection_var = tk.BooleanVar(value=bool(has_selection))
        selection_toggle = tk.Checkbutton(
            selection_panel,
            text="Usar a seleção atual como recorte em todo o trecho",
            variable=self.selection_var,
            fg="#f5f3f7",
            bg="#1d2939",
            selectcolor="#352a45",
            activebackground="#1d2939",
            activeforeground="#f5f3f7",
        )
        selection_toggle.pack(anchor=tk.W)
        if not has_selection:
            selection_toggle.config(state=tk.DISABLED)
        tk.Label(
            selection_panel,
            text=(
                "Faça antes uma seleção Retângulo ou Laço no frame representativo. "
                "O mesmo recorte será usado como região segura da placa nos demais frames."
            ),
            font=("Segoe UI", 9),
            fg="#b8afc4",
            bg="#1d2939",
            wraplength=580,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(6, 0))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(
            buttons,
            text="Cancelar",
            command=self.window.destroy,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=16,
            pady=9,
        ).pack(side=tk.RIGHT)
        tk.Button(
            buttons,
            text="Analisar e construir placa",
            command=self._start,
            bg="#a855f7",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=16,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.RIGHT, padx=8)

    def _start(self):
        apply_after_build = bool(self.apply_var.get())
        use_selection = bool(self.selection_var.get())
        self.window.destroy()
        self.start_callback(apply_after_build, use_selection)
