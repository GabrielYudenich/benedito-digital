"""Accessible import choice for complete media or an exact lossless segment."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.media_import import MediaImportPlanError, build_import_plan, format_timecode
from core.storage import format_bytes, storage_preflight


class ImportVideoDialog:
    def __init__(self, parent, source_path, video_info, destination_dir, start_callback):
        self.source_path = Path(source_path)
        self.video_info = video_info or {}
        self.destination_dir = Path(destination_dir)
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Como deseja importar o filme?")
        self.window.geometry("720x660")
        self.window.minsize(640, 600)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg="#17131f")
        self.window.bind("<Escape>", lambda _event: self.window.destroy())

        tk.Label(
            self.window, text="Importar material", font=("Segoe UI", 22, "bold"),
            fg="#f5f3f7", bg="#17131f",
        ).pack(anchor=tk.W, padx=26, pady=(22, 4))
        tk.Label(
            self.window,
            text=("Escolha o filme inteiro ou somente o trecho que será restaurado. "
                  "Nada será alterado no arquivo original."),
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f",
            wraplength=650, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=26, pady=(0, 14))

        duration = float(self.video_info.get("duration", 0) or 0)
        info = tk.Frame(self.window, bg="#241c31", padx=16, pady=13)
        info.pack(fill=tk.X, padx=26)
        tk.Label(
            info,
            text=(f"Arquivo: {self.source_path.name}\n"
                  f"Tamanho: {format_bytes(self.source_path.stat().st_size)}\n"
                  f"Duração: {format_timecode(duration)}  •  "
                  f"Imagem: {int(self.video_info.get('width', 0) or 0)} × "
                  f"{int(self.video_info.get('height', 0) or 0)}"),
            font=("Segoe UI", 10), fg="#f5f3f7", bg="#241c31", justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.mode_var = tk.StringVar(value="full")
        modes = tk.LabelFrame(
            self.window, text=" Escolha uma opção ", font=("Segoe UI", 11, "bold"),
            fg="#f5f3f7", bg="#17131f", padx=14, pady=10,
        )
        modes.pack(fill=tk.X, padx=26, pady=(16, 0))
        radio_options = {
            "variable": self.mode_var,
            "command": self._refresh,
            "font": ("Segoe UI", 10),
            "fg": "#f5f3f7",
            "bg": "#17131f",
            "selectcolor": "#352a45",
            "activebackground": "#17131f",
            "activeforeground": "#f5f3f7",
        }
        self.full_radio = tk.Radiobutton(
            modes, text="Filme inteiro — copia o arquivo completo para o projeto",
            value="full", **radio_options,
        )
        self.full_radio.pack(anchor=tk.W, pady=4)
        self.segment_radio = tk.Radiobutton(
            modes, text="Somente um trecho — cria uma cópia lossless exata para restauração",
            value="segment", state=tk.NORMAL if duration > 0 else tk.DISABLED,
            **radio_options,
        )
        self.segment_radio.pack(anchor=tk.W, pady=4)

        interval = tk.Frame(self.window, bg="#17131f")
        interval.pack(fill=tk.X, padx=26, pady=(16, 0))
        tk.Label(
            interval, text="Intervalo do trecho (HH:MM:SS)",
            font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#17131f",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(interval, text="Início", fg="#b8afc4", bg="#17131f").grid(
            row=1, column=0, sticky="w", pady=(8, 3)
        )
        tk.Label(interval, text="Final", fg="#b8afc4", bg="#17131f").grid(
            row=1, column=2, sticky="w", pady=(8, 3)
        )
        self.start_var = tk.StringVar(value="00:00:00")
        self.end_var = tk.StringVar(value=format_timecode(duration, milliseconds=True))
        self.start_entry = ttk.Entry(interval, textvariable=self.start_var, width=22)
        self.start_entry.grid(row=2, column=0, sticky="ew")
        tk.Label(interval, text="até", fg="#b8afc4", bg="#17131f").grid(
            row=2, column=1, padx=12
        )
        self.end_entry = ttk.Entry(interval, textvariable=self.end_var, width=22)
        self.end_entry.grid(row=2, column=2, sticky="ew")
        interval.columnconfigure(0, weight=1)
        interval.columnconfigure(2, weight=1)
        self.start_entry.bind("<KeyRelease>", lambda _event: self._refresh())
        self.end_entry.bind("<KeyRelease>", lambda _event: self._refresh())

        estimate = tk.Frame(self.window, bg="#1d2937", padx=15, pady=13)
        estimate.pack(fill=tk.X, padx=26, pady=(18, 0))
        self.estimate_var = tk.StringVar()
        self.space_var = tk.StringVar()
        tk.Label(
            estimate, text="Estimativa antes de começar", font=("Segoe UI", 11, "bold"),
            fg="#93c5fd", bg="#1d2937",
        ).pack(anchor=tk.W)
        tk.Label(
            estimate, textvariable=self.estimate_var, font=("Segoe UI", 10),
            fg="#f5f3f7", bg="#1d2937",
        ).pack(anchor=tk.W, pady=(4, 0))
        self.space_label = tk.Label(
            estimate, textvariable=self.space_var, font=("Segoe UI", 10, "bold"),
            fg="#86efac", bg="#1d2937",
        )
        self.space_label.pack(anchor=tk.W, pady=(2, 0))

        tk.Label(
            self.window,
            text=("O trecho usa FFV1 intraframe e áudio PCM. É maior que um vídeo comum, "
                  "mas não adiciona perdas antes da restauração frame por frame."),
            font=("Segoe UI", 9), fg="#b8afc4", bg="#17131f",
            wraplength=650, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=26, pady=(12, 0))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=26, pady=22)
        tk.Button(
            buttons, text="Cancelar", command=self.window.destroy, bg="#352a45",
            fg="white", relief=tk.FLAT, padx=18, pady=9,
        ).pack(side=tk.RIGHT)
        self.start_button = tk.Button(
            buttons, text="Continuar", command=self._start, bg="#a855f7",
            fg="white", relief=tk.FLAT, padx=18, pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        self.start_button.pack(side=tk.RIGHT, padx=8)
        self.window.bind("<Return>", lambda _event: self._start())
        self._refresh()
        self.full_radio.focus_set()

    def _current_plan(self):
        return build_import_plan(
            self.source_path, self.mode_var.get(), self.video_info,
            start_value=self.start_var.get(), end_value=self.end_var.get(),
        )

    def _refresh(self):
        segment = self.mode_var.get() == "segment"
        self.start_entry.config(state=tk.NORMAL if segment else tk.DISABLED)
        self.end_entry.config(state=tk.NORMAL if segment else tk.DISABLED)
        try:
            plan = self._current_plan()
            preflight = storage_preflight(self.destination_dir, plan.estimated_bytes)
            duration_text = (
                f" • trecho de {format_timecode(plan.duration or 0)}"
                if plan.is_segment else ""
            )
            self.estimate_var.set(
                f"Dados estimados: {format_bytes(plan.estimated_bytes)}{duration_text}"
            )
            suffix = "espaço suficiente" if preflight.enough else "espaço insuficiente"
            self.space_var.set(
                f"Livre: {format_bytes(preflight.available_bytes)} • "
                f"Necessário com reserva: {format_bytes(preflight.required_bytes)} • {suffix}"
            )
            self.space_label.config(fg="#86efac" if preflight.enough else "#fca5a5")
            self.start_button.config(state=tk.NORMAL if preflight.enough else tk.DISABLED)
        except (MediaImportPlanError, OSError) as error:
            self.estimate_var.set(str(error))
            self.space_var.set("Revise o intervalo para continuar")
            self.space_label.config(fg="#fca5a5")
            self.start_button.config(state=tk.DISABLED)

    def _start(self):
        try:
            plan = self._current_plan()
            preflight = storage_preflight(self.destination_dir, plan.estimated_bytes)
            if not preflight.enough:
                messagebox.showerror("Espaço insuficiente", self.space_var.get())
                return
        except (MediaImportPlanError, OSError) as error:
            messagebox.showerror("Importação inválida", str(error))
            return
        self.window.destroy()
        self.start_callback(plan)
