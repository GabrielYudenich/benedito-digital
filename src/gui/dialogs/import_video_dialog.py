"""Accessible dialogs for choosing and reviewing a video import."""

import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from core.media_import import (
    MediaImportPlanError,
    MediaImportSelection,
    build_import_plan,
    build_import_selection,
    format_timecode,
)
from core.storage import format_bytes, storage_preflight
from gui.mousewheel import mousewheel_units


WORKING_FORMAT_LABELS = {
    "mkv_lossless": "MKV sem perdas — FFV1 + PCM",
    "mov_prores": "MOV de edição — ProRes 422 HQ + PCM",
    "mp4_hq": "MP4 alta qualidade — H.264 + AAC",
}
WORKING_FORMAT_NOTES = {
    "mkv_lossless": (
        "Preservação recomendada: imagem e áudio sem perdas, ideal para restauração "
        "frame por frame. Gera arquivos maiores."
    ),
    "mov_prores": (
        "Compatibilidade profissional: ProRes 422 HQ e áudio PCM em contêiner MOV. "
        "É muito fiel, mas não matematicamente sem perdas."
    ),
    "mp4_hq": (
        "Arquivo menor e fácil de reproduzir. Usa compressão com perdas e não é "
        "recomendado como matriz de preservação."
    ),
}
AUDIO_MODE_LABELS = {
    "preserve": "Preservar os canais exatamente como estão",
    "dual_mono_left": "Duplicar o canal esquerdo nos dois lados",
    "dual_mono_right": "Duplicar o canal direito nos dois lados",
    "mono_mix": "Misturar os canais e centralizar nos dois lados",
}


class ImportModeDialog:
    """Ask what should be imported before any media analysis starts."""

    def __init__(self, parent, source_path, confirm_callback):
        self.parent = parent
        self.source_path = Path(source_path)
        self.confirm_callback = confirm_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Escolher forma de importação")
        self.window.geometry("680x620")
        self.window.minsize(600, 520)
        self.window.transient(parent)
        self.window.grab_set()
        self.window.configure(bg="#17131f")
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)
        self.window.bind("<Escape>", lambda _event: self._cancel())
        self.window.bind("<Return>", lambda _event: self._confirm())
        self.window.bind("1", lambda event: self._mode_shortcut(event, "full"))
        self.window.bind("2", lambda event: self._mode_shortcut(event, "segment"))
        self.window.bind("<Up>", lambda event: self._mode_shortcut(event, "full"))
        self.window.bind("<Down>", lambda event: self._mode_shortcut(event, "segment"))
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.window.bind(sequence, self._scroll_selection_body)
        self.window.columnconfigure(0, weight=1)
        self.window.rowconfigure(0, weight=1)

        body_container = tk.Frame(self.window, bg="#17131f")
        body_container.grid(row=0, column=0, sticky="nsew")
        body_container.columnconfigure(0, weight=1)
        body_container.rowconfigure(0, weight=1)
        self.body_canvas = tk.Canvas(
            body_container,
            bg="#17131f",
            highlightthickness=0,
            borderwidth=0,
        )
        self.body_scrollbar = ttk.Scrollbar(
            body_container,
            orient=tk.VERTICAL,
            command=self.body_canvas.yview,
        )
        self.body_canvas.configure(yscrollcommand=self.body_scrollbar.set)
        self.body_canvas.grid(row=0, column=0, sticky="nsew")
        self.body_scrollbar.grid(row=0, column=1, sticky="ns")
        content = tk.Frame(
            self.body_canvas,
            bg="#17131f",
            padx=26,
            pady=12,
        )
        self.body_content = content
        body_window = self.body_canvas.create_window(
            (0, 0), window=content, anchor="nw"
        )
        content.bind("<Configure>", self._sync_selection_scrollregion)
        self.body_canvas.bind(
            "<Configure>",
            lambda event: self._resize_selection_body(body_window, event.width),
        )

        tk.Label(
            content,
            text="O que deseja importar?",
            font=("Segoe UI", 22, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, pady=(10, 0))
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
            "command": self._refresh_selection,
            "font": ("Segoe UI", 10),
            "fg": "#f5f3f7",
            "bg": "#241c31",
            "selectcolor": "#6d28d9",
            "activebackground": "#4c1d95",
            "activeforeground": "#f5f3f7",
            "anchor": tk.W,
            "justify": tk.LEFT,
            "indicatoron": False,
            "relief": tk.FLAT,
            "borderwidth": 0,
            "highlightthickness": 1,
            "highlightbackground": "#4b3f59",
            "highlightcolor": "#c084fc",
            "padx": 14,
            "pady": 10,
            "cursor": "hand2",
            "takefocus": True,
        }
        self.full_radio = tk.Radiobutton(
            options,
            text="FILME INTEIRO\nCopiar todo o arquivo para o projeto",
            value="full",
            **radio_options,
        )
        self.full_radio.pack(fill=tk.X, pady=(4, 6))
        self.segment_radio = tk.Radiobutton(
            options,
            text="SOMENTE UM TRECHO\nInformar início e final nesta janela",
            value="segment",
            **radio_options,
        )
        self.segment_radio.pack(fill=tk.X, pady=(0, 4))

        self.start_var = tk.StringVar(value="00:00:00")
        self.end_var = tk.StringVar(value="")
        self.interval_panel = tk.Frame(content, bg="#241c31", padx=14, pady=11)
        tk.Label(
            self.interval_panel,
            text="Minutagem do trecho",
            font=("Segoe UI", 11, "bold"),
            fg="#f5f3f7",
            bg="#241c31",
        ).grid(row=0, column=0, columnspan=3, sticky="w")
        tk.Label(
            self.interval_panel,
            text="Início (HH:MM:SS)",
            fg="#b8afc4",
            bg="#241c31",
        ).grid(row=1, column=0, sticky="w", pady=(8, 3))
        tk.Label(
            self.interval_panel,
            text="Final (obrigatório)",
            fg="#b8afc4",
            bg="#241c31",
        ).grid(row=1, column=2, sticky="w", pady=(8, 3))
        self.start_entry = ttk.Entry(
            self.interval_panel, textvariable=self.start_var, width=22
        )
        self.start_entry.grid(row=2, column=0, sticky="ew")
        tk.Label(
            self.interval_panel,
            text="até",
            fg="#b8afc4",
            bg="#241c31",
        ).grid(row=2, column=1, padx=12)
        self.end_entry = ttk.Entry(
            self.interval_panel, textvariable=self.end_var, width=22
        )
        self.end_entry.grid(row=2, column=2, sticky="ew")
        tk.Label(
            self.interval_panel,
            text="Exemplo: de 00:12:30 até 00:18:45",
            font=("Segoe UI", 9),
            fg="#b8afc4",
            bg="#241c31",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(7, 0))
        self.interval_panel.columnconfigure(0, weight=1)
        self.interval_panel.columnconfigure(2, weight=1)
        self.start_entry.bind("<KeyRelease>", lambda _event: self._refresh_selection())
        self.end_entry.bind("<KeyRelease>", lambda _event: self._refresh_selection())

        self.selection_panel = tk.Frame(content, bg="#17283a", padx=14, pady=10)
        self.selection_panel.pack(fill=tk.X, pady=(10, 0))
        self.selection_status_var = tk.StringVar()
        self.selection_status_label = tk.Label(
            self.selection_panel,
            textvariable=self.selection_status_var,
            font=("Segoe UI", 10, "bold"),
            fg="#93c5fd",
            bg="#17283a",
            wraplength=540,
            justify=tk.LEFT,
        )
        self.selection_status_label.pack(anchor=tk.W)

        footer = tk.Frame(self.window, bg="#201829", padx=26, pady=14)
        self.footer = footer
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
        self.confirm_button = tk.Button(
            footer,
            command=self._confirm,
            bg="#a855f7",
            fg="white",
            relief=tk.FLAT,
            padx=18,
            pady=9,
            font=("Segoe UI", 10, "bold"),
        )
        self.confirm_button.pack(side=tk.RIGHT, padx=(0, 8))
        self._refresh_selection()
        self.full_radio.focus_set()
        self.window.after_idle(self._fit_to_content)

    def _cancel(self):
        self.window.destroy()

    def _select_mode(self, mode):
        self.mode_var.set(mode)
        self._refresh_selection()
        target = self.start_entry if mode == "segment" else self.full_radio
        target.focus_set()

    def _mode_shortcut(self, event, mode):
        widget_class = event.widget.winfo_class()
        if widget_class in {
            "Entry",
            "TEntry",
            "Text",
            "TCombobox",
            "Spinbox",
            "TSpinbox",
        }:
            return None
        self._select_mode(mode)
        return "break"

    def _refresh_selection(self):
        segment = self.mode_var.get() == "segment"
        self.full_radio.config(
            text=(
                "✓ FILME INTEIRO SELECIONADO\nCopiar todo o arquivo para o projeto"
                if not segment
                else "FILME INTEIRO\nCopiar todo o arquivo para o projeto"
            ),
            relief=tk.SUNKEN if not segment else tk.RAISED,
            bg="#6d28d9" if not segment else "#241c31",
        )
        self.segment_radio.config(
            text=(
                "✓ SOMENTE UM TRECHO SELECIONADO\nInforme início e final abaixo"
                if segment
                else "SOMENTE UM TRECHO\nInformar início e final nesta janela"
            ),
            relief=tk.SUNKEN if segment else tk.RAISED,
            bg="#6d28d9" if segment else "#241c31",
        )
        if segment:
            if not self.interval_panel.winfo_manager():
                self.interval_panel.pack(
                    fill=tk.X,
                    pady=(10, 0),
                    before=self.selection_panel,
                )
            try:
                selection = self._current_selection()
                self.selection_status_var.set(
                    "Trecho definido: "
                    f"{format_timecode(selection.start_time, milliseconds=True)} até "
                    f"{format_timecode(selection.end_time or 0, milliseconds=True)}. "
                    "Pressione OK para analisar e revisar."
                )
                self.selection_status_label.config(fg="#86efac")
                self.confirm_button.config(
                    text="OK — analisar e revisar trecho", state=tk.NORMAL
                )
            except MediaImportPlanError as error:
                self.selection_status_var.set(
                    f"Informe um intervalo válido para continuar: {error}"
                )
                self.selection_status_label.config(fg="#fca5a5")
                self.confirm_button.config(
                    text="Informe início e final", state=tk.DISABLED
                )
        else:
            if self.interval_panel.winfo_manager():
                self.interval_panel.pack_forget()
            self.selection_status_var.set(
                "Selecionado: FILME INTEIRO. Pressione OK para analisar e revisar "
                "a importação completa."
            )
            self.selection_status_label.config(fg="#93c5fd")
            self.confirm_button.config(
                text="OK — analisar filme inteiro", state=tk.NORMAL
            )
        self.window.after_idle(self._fit_to_content)

    def _current_selection(self) -> MediaImportSelection:
        return build_import_selection(
            self.mode_var.get(),
            start_value=self.start_var.get(),
            end_value=self.end_var.get(),
        )

    def _resize_selection_body(self, body_window, width):
        self.body_canvas.itemconfigure(body_window, width=width)
        self._sync_selection_scrollregion()

    def _sync_selection_scrollregion(self, _event=None):
        self.body_canvas.configure(scrollregion=self.body_canvas.bbox("all"))
        if self.body_canvas.winfo_height() <= 1:
            return
        if self.body_content.winfo_reqheight() > self.body_canvas.winfo_height():
            self.body_scrollbar.grid()
        else:
            self.body_scrollbar.grid_remove()
            self.body_canvas.yview_moveto(0)

    def _scroll_selection_body(self, event):
        if self.body_content.winfo_reqheight() > self.body_canvas.winfo_height():
            units = mousewheel_units(event)
            if units:
                self.body_canvas.yview_scroll(units, "units")
        return "break"

    def _fit_to_content(self):
        if not self.window.winfo_exists():
            return
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        requested_width = max(
            self.body_content.winfo_reqwidth(), self.footer.winfo_reqwidth()
        )
        requested_height = (
            self.body_content.winfo_reqheight() + self.footer.winfo_reqheight()
        )
        width = min(max(640, requested_width + 12), screen_width - 60)
        height = min(max(520, requested_height + 8), screen_height - 80)
        try:
            parent_x = self.parent.winfo_rootx()
            parent_y = self.parent.winfo_rooty()
            parent_width = self.parent.winfo_width()
            parent_height = self.parent.winfo_height()
            x = max(20, parent_x + (parent_width - width) // 2)
            y = max(20, parent_y + (parent_height - height) // 2)
        except tk.TclError:
            x = max(20, (screen_width - width) // 2)
            y = max(20, (screen_height - height) // 2)
        self.window.geometry(f"{width}x{height}+{x}+{y}")
        self.window.after_idle(self._sync_selection_scrollregion)

    def _confirm(self):
        try:
            selection = self._current_selection()
        except MediaImportPlanError as error:
            messagebox.showerror(
                "Intervalo necessário",
                str(error),
                parent=self.window,
            )
            return
        self.window.destroy()
        self.confirm_callback(selection)


class ImportVideoDialog:
    """Review metadata, interval and disk space after media analysis."""

    def __init__(
        self,
        parent,
        source_path,
        video_info,
        destination_dir,
        selection,
        start_callback,
    ):
        if isinstance(selection, str):
            selection = MediaImportSelection(mode=selection)
        mode = selection.mode
        if mode not in {"full", "segment"}:
            raise ValueError("Invalid import mode")
        self.source_path = Path(source_path)
        self.video_info = video_info or {}
        self.destination_dir = Path(destination_dir)
        self.selection = selection
        self.mode = mode
        self.start_callback = start_callback
        self.window = tk.Toplevel(parent)
        self.window.title(
            "Confirmar filme inteiro" if mode == "full" else "Revisar trecho do filme"
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
        self.body_canvas = canvas
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
        for sequence in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.window.bind(sequence, self._scroll_body)

        title = "Revisar filme inteiro" if mode == "full" else "Revisar trecho escolhido"
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
            else (
                "Escolha confirmada: "
                f"{format_timecode(selection.start_time, milliseconds=True)} até "
                f"{format_timecode(selection.end_time or 0, milliseconds=True)}"
            )
        )
        tk.Label(
            selected,
            text=selected_text,
            font=("Segoe UI", 11, "bold"),
            fg="#93c5fd",
            bg="#17283a",
        ).pack(anchor=tk.W)

        self.start_var = tk.StringVar(
            value=format_timecode(selection.start_time, milliseconds=True)
        )
        self.end_var = tk.StringVar(
            value=(
                format_timecode(selection.end_time, milliseconds=True)
                if selection.end_time is not None
                else format_timecode(duration, milliseconds=True)
            )
        )
        self.working_format_var = tk.StringVar(value="mkv_lossless")
        audio_analysis = self.video_info.get("audio_analysis", {})
        suggested_audio_mode = audio_analysis.get("suggested_mode", "preserve")
        if suggested_audio_mode not in AUDIO_MODE_LABELS:
            suggested_audio_mode = "preserve"
        self.audio_mode_var = tk.StringVar(value=suggested_audio_mode)
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

            format_panel = tk.Frame(body, bg="#241c31", padx=15, pady=13)
            format_panel.pack(fill=tk.X, padx=26, pady=(16, 0))
            tk.Label(
                format_panel,
                text="Formato do trecho de trabalho",
                font=("Segoe UI", 11, "bold"),
                fg="#f5f3f7",
                bg="#241c31",
            ).pack(anchor=tk.W)
            self.format_combo = ttk.Combobox(
                format_panel,
                state="readonly",
                values=list(WORKING_FORMAT_LABELS.values()),
                width=54,
                style="Dark.TCombobox",
            )
            self.format_combo.set(WORKING_FORMAT_LABELS["mkv_lossless"])
            self.format_combo.pack(fill=tk.X, pady=(7, 5))
            self.format_combo.bind("<<ComboboxSelected>>", self._format_changed)
            self.format_note_var = tk.StringVar()
            tk.Label(
                format_panel,
                textvariable=self.format_note_var,
                font=("Segoe UI", 9),
                fg="#b8afc4",
                bg="#241c31",
                wraplength=620,
                justify=tk.LEFT,
            ).pack(anchor=tk.W)

            audio_panel = tk.Frame(body, bg="#2b1d2b", padx=15, pady=13)
            audio_panel.pack(fill=tk.X, padx=26, pady=(12, 0))
            tk.Label(
                audio_panel,
                text="Canais de áudio",
                font=("Segoe UI", 11, "bold"),
                fg="#f5f3f7",
                bg="#2b1d2b",
            ).pack(anchor=tk.W)
            analysis_summary = audio_analysis.get(
                "summary", "O áudio não recebeu uma recomendação automática."
            )
            tk.Label(
                audio_panel,
                text=analysis_summary,
                font=("Segoe UI", 9),
                fg="#fbbf24" if suggested_audio_mode != "preserve" else "#b8afc4",
                bg="#2b1d2b",
                wraplength=620,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(5, 6))
            self.audio_combo = ttk.Combobox(
                audio_panel,
                state="readonly",
                values=list(AUDIO_MODE_LABELS.values()),
                width=54,
                style="Dark.TCombobox",
            )
            self.audio_combo.set(AUDIO_MODE_LABELS[suggested_audio_mode])
            self.audio_combo.pack(fill=tk.X)
            self.audio_combo.bind("<<ComboboxSelected>>", self._audio_changed)
            tk.Label(
                audio_panel,
                text=(
                    "O tratamento afeta somente a cópia de trabalho. O arquivo "
                    "original permanece intocado e a escolha fica registrada."
                ),
                font=("Segoe UI", 9),
                fg="#b8afc4",
                bg="#2b1d2b",
                wraplength=620,
                justify=tk.LEFT,
            ).pack(anchor=tk.W, pady=(6, 0))

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
            tk.Frame(body, bg="#17131f", height=18).pack(fill=tk.X)

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

    def _scroll_body(self, event):
        units = mousewheel_units(event)
        if units:
            self.body_canvas.yview_scroll(units, "units")
        return "break"

    def _format_changed(self, _event=None):
        selected_label = self.format_combo.get()
        for value, label in WORKING_FORMAT_LABELS.items():
            if label == selected_label:
                self.working_format_var.set(value)
                break
        self._refresh()

    def _audio_changed(self, _event=None):
        selected_label = self.audio_combo.get()
        for value, label in AUDIO_MODE_LABELS.items():
            if label == selected_label:
                self.audio_mode_var.set(value)
                break
        self._refresh()

    def _current_plan(self):
        return build_import_plan(
            self.source_path,
            self.mode,
            self.video_info,
            start_value=self.start_var.get(),
            end_value=self.end_var.get(),
            working_format=self.working_format_var.get(),
            audio_mode=self.audio_mode_var.get(),
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
            if plan.is_segment:
                self.format_note_var.set(WORKING_FORMAT_NOTES[plan.working_format])
                format_name = WORKING_FORMAT_LABELS[plan.working_format].split(" —", 1)[0]
                self.start_button.config(text=f"Importar trecho em {format_name}")
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
