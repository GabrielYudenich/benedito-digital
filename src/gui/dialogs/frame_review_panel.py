"""Floating frame review panel kept separate from the restoration canvas."""

import tkinter as tk
from tkinter import ttk


class FrameReviewPanel:
    def __init__(
        self,
        parent,
        status_labels,
        apply_callback,
        clear_callback,
        previous_callback,
        next_callback,
        analyze_callback,
    ):
        self.apply_callback = apply_callback
        self.clear_callback = clear_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Revisão e estado do frame")
        self.window.geometry("500x400")
        self.window.minsize(440, 370)
        self.window.configure(bg="#17131f")
        self.window.protocol("WM_DELETE_WINDOW", self.window.withdraw)

        header = tk.Frame(self.window, bg="#17131f")
        header.pack(fill=tk.X, padx=20, pady=(18, 10))
        self.frame_label = tk.Label(
            header,
            text="Frame —",
            font=("Segoe UI", 18, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        )
        self.frame_label.pack(side=tk.LEFT)
        self.topmost_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            header,
            text="Manter sobre o editor",
            variable=self.topmost_var,
            command=self._update_topmost,
            fg="#b8afc4",
            bg="#17131f",
            selectcolor="#352a45",
            activebackground="#17131f",
            activeforeground="#f5f3f7",
        ).pack(side=tk.RIGHT)

        form = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        form.pack(fill=tk.BOTH, expand=True, padx=20)
        tk.Label(
            form,
            text="Estado do frame",
            font=("Segoe UI", 10, "bold"),
            fg="#f5f3f7",
            bg="#241c31",
        ).pack(anchor=tk.W)
        self.status_var = tk.StringVar(value=status_labels[0])
        self.status_combo = ttk.Combobox(
            form,
            textvariable=self.status_var,
            values=status_labels,
            state="readonly",
            style="Dark.TCombobox",
        )
        self.status_combo.pack(fill=tk.X, pady=(5, 12))
        tk.Label(
            form,
            text="Observação opcional",
            font=("Segoe UI", 10, "bold"),
            fg="#f5f3f7",
            bg="#241c31",
        ).pack(anchor=tk.W)
        self.note_text = tk.Text(
            form,
            height=4,
            wrap=tk.WORD,
            bg="#100c17",
            fg="#f5f3f7",
            insertbackground="#c084fc",
            relief=tk.FLAT,
            padx=8,
            pady=6,
        )
        self.note_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        actions = tk.Frame(self.window, bg="#17131f")
        actions.pack(fill=tk.X, padx=20, pady=(14, 6))
        tk.Button(
            actions,
            text="Sinalizar frame",
            command=self._apply,
            bg="#a855f7",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=12,
            pady=7,
        ).pack(side=tk.LEFT)
        tk.Button(
            actions,
            text="Limpar estado",
            command=self.clear_callback,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            pady=7,
        ).pack(side=tk.LEFT, padx=5)
        tk.Button(
            actions,
            text="Analisar danos...",
            command=analyze_callback,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=10,
            pady=7,
        ).pack(side=tk.LEFT)
        navigation = tk.Frame(self.window, bg="#17131f")
        navigation.pack(fill=tk.X, padx=20, pady=(0, 14))
        tk.Button(
            navigation,
            text="← Sinalizado anterior",
            command=previous_callback,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=9,
            pady=7,
        ).pack(side=tk.LEFT)
        tk.Button(
            navigation,
            text="Próximo sinalizado →",
            command=next_callback,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=9,
            pady=7,
        ).pack(side=tk.RIGHT)
        self._update_topmost()

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def update_frame(self, frame_number, status_label, note=""):
        self.frame_label.config(text=f"Frame {frame_number}")
        self.status_var.set(status_label)
        self.note_text.delete("1.0", tk.END)
        self.note_text.insert("1.0", note or "")

    def _apply(self):
        self.apply_callback(
            self.status_var.get(), self.note_text.get("1.0", tk.END).strip()
        )

    def _update_topmost(self):
        self.window.attributes("-topmost", bool(self.topmost_var.get()))
