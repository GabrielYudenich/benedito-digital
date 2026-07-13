"""Accessible dialogs for choosing and reviewing a video import."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.media_import import MediaImportPlanError, build_import_plan, format_timecode
from core.storage import format_bytes, storage_preflight


class ImportModeDialog:
    """Ask what should be imported before any media analysis starts."""

    def __init__(self, parent, source_path, confirm_callback):
        self.source_path = Path(source_path)
        self.confirm_callback = confirm_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Escolher forma de importação")
        self.window.geometry("620x430")
        self.window.minsize(540, 390)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg="#17131f")
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.bind("<Return>", lambda _event: self._confirm())
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        content = tk.Frame(self.window, bg="#17131f")
        content.grid(row=0, column=0, sticky="nsew", padx=26, pady=(22, 12))

        tk.Label(
            content,
            text="O que deseja importar?",
            font=("Segoe UI", 22, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W)
        tk.Label(
            content,
            text=(
                "Confirme a escolha abaixo. A análise da mídia só começará depois "
                "que você pressionar OK."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=550,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(4, 14))

        file_panel = tk.Frame(content, bg="#241c31", padx=15, pady=12)
        file_panel.pack(fill=tk.X)
        tk.Label(
            file_panel,
            text=(
                f"Arquivo: {self.source_path.name}\n"
                f"Tamanho: {format_bytes(self.source_path.stat().st_size)}"
            ),
            font=("Segoe UI", 10),
            fg="#f5f3f7",
            bg="#241c31",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        self.mode_var = tk.StringVar(value="full")
        options = tk.LabelFrame(
            content,
            text=" Escolha uma opção ",
            font=("Segoe UI", 11, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
            padx=14,
            pady=9,
        )
        options.pack(fill=tk.X, pady=(15, 0))
        radio_options = {
            "variable": self.mode_var,
            "font": ("Segoe UI", 10),
            "fg": "#f5f3f7",
            "bg": "#17131f",
            "selectcolor": "#352a45",
            "activebackground": "#17131f",
            "activeforeground": "#f5f3f7",
            "anchor": tk.W,
            "justify": tk.LEFT,
        }
        self.full_radio = tk.Radiobutton(
            options,
            text="Filme inteiro — copiar todo o arquivo para o projeto",
            value="full",
            **radio_options,
        )
        self.full_radio.pack(fill=tk.X, pady=4)
        tk.Radiobutton(
            options,
            text="Somente um trecho — escolher início e final após a análise",
            value="segment",
            **radio_options,
        ).pack(fill=tk.X, pady=4)

        footer = tk.Frame(self.window, bg="#201829", padx=26, pady=14)
        footer.grid(row=1, column=0, sticky="ew")
        tk.Button(
            footer,
            text="Cancelar",
            command=self._cancel,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=18,
            pady=9,
        ).pack(side=tk.RIGHT)
        tk.Button(
            footer,
            text="OK — analisar mídia",
            command=self._confirm,
            bg="#a855f7",
            fg="white",
            relief=tk.FLAT,
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        ).pack(side=tk.RIGHT, padx=(0, 8))
        self.full_radio.focus_set()

    def _cancel(self):
        self.window.destroy()

    def _confirm(self):
        mode = self.mode_var.get()
        if mode not in {"full", "segment"}:
            messagebox.showerror(
                "Escolha necessária",
                "Selecione filme inteiro ou somente um trecho.",
                parent=self.window,
            )
            return
        self.window.destroy()
        self.confirm_callback(mode)


class ImportVideoDialog:
    """Review metadata, interval and disk space after media analysis."""

    def __init__(
        self,
        parent,
        source_path,
        video_info,
        destination_dir,
        mode,
        start_callback,
    ):
        if mode not in {"full", "segment"}:
            raise ValueError("Invalid import mode")
        self.source_path = Path(source_path)
        self.video_info = video_info or {}
        self.destination_dir = Path(destination_dir)
        self.mode = mode
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title(
            "Confirmar filme inteiro" if mode == "full" else "Definir trecho do filme"
        )
        screen_height = max(560, self.window.winfo_screenheight())
        dialog_height = min(680, screen_height - 100)
        self.window.geometry(f"720x{dialog_height}")
        self.window.minsize(620, min(520, dialog_height))
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg="#17131f")
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self.window.bind("<Escape>", lambda _event: self.window.destroy())
        self.window.bind("<Return>", lambda _event: self._start())
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        body_container = tk.Frame(self.window, bg="#17131f")
        body_container.grid(row=0, column=0, sticky="nsew")
        body_container.columnconfigure(0, weight=1)
        body_container.rowconfigure(0, weight=1)
        canvas = tk.Canvas(
            body_container,
            bg="#17131f",
            highlightthickness=0,
            borderwidth=0,
        )
        scrollbar = ttk.Scrollbar(body_container, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        body = tk.Frame(canvas, bg="#17131f")
        body_window = canvas.create_window((0, 0), window=body, anchor="nw")
        body.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(body_window, width=event.width),
        )

        title = "Revisar filme inteiro" if mode == "full" else "Escolher início e final"
        tk.Label(
            body,
            text=title,
            font=("Segoe UI", 22, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=26, pady=(22, 4))
        tk.Label(
            body,
            text=(
                "A mídia foi analisada. Revise os dados e confirme a importação. "
                "Nada será alterado no arquivo original."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=650,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=26, pady=(0, 14))

        duration = float(self.video_info.get("duration", 0) or 0)
        info = tk.Frame(body, bg="#241c31", padx=16, pady=13)
        info.pack(fill=tk.X, padx=26)
        tk.Label(
            info,
            text=(
                f"Arquivo: {self.source_path.name}\n"
                f"Tamanho: {format_bytes(self.source_path.stat().st_size)}\n"
                f"Duração: {format_timecode(duration)}  •  "
                f"Imagem: {int(self.video_info.get('width', 0) or 0)} × "
                f"{int(self.video_info.get('height', 0) or 0)}"
            ),
            font=("Segoe UI", 10),
            fg="#f5f3f7",
            bg="#241c31",
            justify=tk.LEFT,
        ).pack(anchor=tk.W)

        selected = tk.Frame(body, bg="#17283a", padx=15, pady=12)
        selected.pack(fill=tk.X, padx=26, pady=(15, 0))
        selected_text = (
            "Escolha confirmada: filme inteiro"
            if mode == "full"
            else "Escolha confirmada: somente um trecho"
        )
        tk.Label(
            selected,
            text=selected_text,
            font=("Segoe UI", 11, "bold"),
            fg="#93c5fd",
            bg="#17283a",
        ).pack(anchor=tk.W)

        self.start_var = tk.StringVar(value="00:00:00")
        self.end_var = tk.StringVar(value=format_timecode(duration, milliseconds=True))
        if mode == "segment":
            interval = tk.Frame(body, bg="#17131f")
            interval.pack(fill=tk.X, padx=26, pady=(16, 0))
            tk.Label(
                interval,
                text="Intervalo do trecho (HH:MM:SS)",
                font=("Segoe UI", 11, "bold"),
                fg="#f5f3f7",
                bg="#17131f",
            ).grid(row=0, column=0, columnspan=3, sticky="w")
            tk.Label(
                interval, text="Início", fg="#b8afc4", bg="#17131f"
            ).grid(row=1, column=0, sticky="w", pady=(8, 3))
            tk.Label(
                interval, text="Final", fg="#b8afc4", bg="#17131f"
            ).grid(row=1, column=2, sticky="w", pady=(8, 3))
            self.start_entry = ttk.Entry(
                interval, textvariable=self.start_var, width=22
            )
            self.start_entry.grid(row=2, column=0, sticky="ew")
            tk.Label(
                interval, text="até", fg="#b8afc4", bg="#17131f"
            ).grid(row=2, column=1, padx=12)
            self.end_entry = ttk.Entry(interval, textvariable=self.end_var, width=22)
            self.end_entry.grid(row=2, column=2, sticky="ew")
            interval.columnconfigure(0, weight=1)
            interval.columnconfigure(2, weight=1)
            self.start_entry.bind("<KeyRelease>", lambda _event: self._refresh())
            self.end_entry.bind("<KeyRelease>", lambda _event: self._refresh())

        estimate = tk.Frame(body, bg="#1d2937", padx=15, pady=13)
        estimate.pack(fill=tk.X, padx=26, pady=(18, 0))
        self.estimate_var = tk.StringVar()
        self.space_var = tk.StringVar()
        tk.Label(
            estimate,
            text="Estimativa antes de começar",
            font=("Segoe UI", 11, "bold"),
            fg="#93c5fd",
            bg="#1d2937",
        ).pack(anchor=tk.W)
        tk.Label(
            estimate,
            textvariable=self.estimate_var,
            font=("Segoe UI", 10),
            fg="#f5f3f7",
            bg="#1d2937",
        ).pack(anchor=tk.W, pady=(4, 0))
        self.space_label = tk.Label(
            estimate,
            textvariable=self.space_var,
            font=("Segoe UI", 10, "bold"),
            fg="#86efac",
            bg="#1d2937",
            wraplength=620,
            justify=tk.LEFT,
        )
        self.space_label.pack(anchor=tk.W, pady=(2, 0))

        if mode == "segment":
            tk.Label(
                body,
                text=(
                    "O trecho usa FFV1 intraframe e áudio PCM. É maior que um vídeo "
                    "comum, mas não adiciona perdas antes da restauração frame por frame."
                ),
                font=("Segoe UI", 9),
                fg="#b8afc4",
                bg="#17131f",
                wraplength=650,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, padx=26, pady=(12, 18))

        footer = tk.Frame(self.window, bg="#201829", padx=26, pady=14)
        footer.grid(row=1, column=0, sticky="ew")
        tk.Button(
            footer,
            text="Cancelar",
            command=self.window.destroy,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=18,
            pady=9,
        ).pack(side=tk.RIGHT)
        button_text = (
            "Importar filme inteiro"
            if mode == "full"
            else "Importar trecho selecionado"
        )
        self.start_button = tk.Button(
            footer,
            text=button_text,
            command=self._start,
            bg="#a855f7",
            fg="white",
            relief=tk.FLAT,
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        self.start_button.pack(side=tk.RIGHT, padx=(0, 8))
        self._refresh()
        if mode == "segment":
            self.start_entry.focus_set()
        else:
            self.start_button.focus_set()

    def _current_plan(self):
        return build_import_plan(
            self.source_path,
            self.mode,
            self.video_info,
            start_value=self.start_var.get(),
            end_value=self.end_var.get(),
        )

    def _refresh(self):
        try:
            plan = self._current_plan()
            preflight = storage_preflight(self.destination_dir, plan.estimated_bytes)
            duration_text = (
                f" • trecho de {format_timecode(plan.duration or 0)}"
                if plan.is_segment
                else ""
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
                messagebox.showerror(
                    "Espaço insuficiente", self.space_var.get(), parent=self.window
                )
                return
        except (MediaImportPlanError, OSError) as error:
            messagebox.showerror(
                "Importação inválida", str(error), parent=self.window
            )
            return
        self.window.destroy()
        self.start_callback(plan)
