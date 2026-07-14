"""Explicit scope chooser for long restoration operations."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class OperationScope:
    kind: str
    start: int
    end: int
    label: str
    segment: object | None = None


class OperationScopeDialog:
    def __init__(
        self,
        parent,
        operation_name,
        total_frames,
        active_range,
        useful_range,
        segments,
        suggested_segment=None,
    ):
        self.operation_name = operation_name
        self.total_frames = total_frames
        self.active_range = active_range
        self.useful_range = useful_range
        self.segments = list(segments)
        self.result = None
        self.window = tk.Toplevel(parent)
        self.window.title(f"Escopo — {operation_name}")
        self.window.geometry("700x520")
        self.window.minsize(620, 470)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")
        self.window.protocol("WM_DELETE_WINDOW", self._cancel)

        tk.Label(
            self.window,
            text=f"Onde aplicar {operation_name.lower()}?",
            font=("Segoe UI", 20, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text=(
                "Confirme o intervalo antes de iniciar. O Benedito não processará "
                "automaticamente o filme inteiro sem esta escolha."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=650,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        default_kind = "position" if self.segments else "active"
        self.scope_var = tk.StringVar(value=default_kind)
        panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        panel.pack(fill=tk.BOTH, expand=True, padx=24)

        position_row = tk.Frame(panel, bg="#241c31")
        position_row.pack(fill=tk.X, pady=4)
        self.position_radio = tk.Radiobutton(
            position_row,
            text="Posicionamento salvo (recomendado)",
            value="position",
            variable=self.scope_var,
            command=self._update_summary,
            fg="#f5f3f7",
            bg="#241c31",
            selectcolor="#352a45",
            activebackground="#241c31",
            activeforeground="#f5f3f7",
        )
        self.position_radio.pack(anchor=tk.W)
        self.segment_var = tk.StringVar()
        self.segment_combo = ttk.Combobox(
            position_row,
            textvariable=self.segment_var,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.segment_combo.pack(fill=tk.X, padx=(24, 0), pady=(4, 0))
        self.segment_combo.bind("<<ComboboxSelected>>", self._update_summary)
        self._segment_by_label = {
            self._segment_label(segment): segment for segment in self.segments
        }
        self.segment_combo.configure(values=tuple(self._segment_by_label))
        if self.segments:
            selected = suggested_segment if suggested_segment in self.segments else self.segments[0]
            self.segment_var.set(self._segment_label(selected))
        else:
            self.position_radio.configure(state=tk.DISABLED)
            self.segment_combo.configure(state=tk.DISABLED)

        active_start, active_end = self.active_range
        tk.Radiobutton(
            panel,
            text=(
                f"Trecho de trabalho atual — frames {active_start + 1}–{active_end + 1}"
            ),
            value="active",
            variable=self.scope_var,
            command=self._update_summary,
            fg="#f5f3f7",
            bg="#241c31",
            selectcolor="#352a45",
            activebackground="#241c31",
            activeforeground="#f5f3f7",
        ).pack(anchor=tk.W, pady=(16, 4))

        useful_start, useful_end = self.useful_range
        tk.Radiobutton(
            panel,
            text=(
                f"Filme inteiro dentro do corte útil — frames "
                f"{useful_start + 1}–{useful_end + 1}"
            ),
            value="full",
            variable=self.scope_var,
            command=self._update_summary,
            fg="#f5f3f7",
            bg="#241c31",
            selectcolor="#352a45",
            activebackground="#241c31",
            activeforeground="#f5f3f7",
        ).pack(anchor=tk.W, pady=(12, 4))

        self.summary_var = tk.StringVar()
        tk.Label(
            panel,
            textvariable=self.summary_var,
            font=("Segoe UI", 11, "bold"),
            fg="#c084fc",
            bg="#241c31",
            wraplength=610,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(22, 0))
        self._update_summary()

        actions = tk.Frame(self.window, bg="#17131f")
        actions.pack(fill=tk.X, padx=24, pady=18)
        tk.Button(
            actions,
            text="Cancelar",
            command=self._cancel,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=16,
            pady=9,
        ).pack(side=tk.RIGHT)
        tk.Button(
            actions,
            text=f"Continuar com {operation_name.lower()}",
            command=self._confirm,
            bg="#a855f7",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=16,
            pady=9,
        ).pack(side=tk.RIGHT, padx=8)

        self.window.grab_set()
        self.window.focus_force()

    @staticmethod
    def _segment_label(segment):
        return f"{segment.name} — frames {segment.start + 1}–{segment.end + 1}"

    def _selected_scope(self):
        kind = self.scope_var.get()
        if kind == "position":
            segment = self._segment_by_label.get(self.segment_var.get())
            if segment is None:
                return None
            return OperationScope(
                kind,
                segment.start,
                segment.end,
                f"posicionamento {segment.name}",
                segment,
            )
        if kind == "full":
            start, end = self.useful_range
            return OperationScope(kind, start, end, "filme inteiro no corte útil")
        start, end = self.active_range
        return OperationScope(kind, start, end, "trecho de trabalho atual")

    def _update_summary(self, _event=None):
        scope = self._selected_scope()
        if scope is None:
            self.summary_var.set("Escolha um posicionamento salvo.")
            return
        count = scope.end - scope.start + 1
        self.summary_var.set(
            f"Será processado: {scope.label}, frames {scope.start + 1}–"
            f"{scope.end + 1} ({count} frames)."
        )

    def _confirm(self):
        scope = self._selected_scope()
        if scope is None:
            messagebox.showwarning(
                "Escolha o escopo",
                "Selecione um posicionamento ou outro intervalo.",
                parent=self.window,
            )
            return
        self.result = scope
        self.window.destroy()

    def _cancel(self):
        self.result = None
        self.window.destroy()

    def show(self):
        self.window.wait_window()
        return self.result
