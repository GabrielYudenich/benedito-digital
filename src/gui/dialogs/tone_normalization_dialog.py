"""Guided temporal light and contrast normalization."""

from __future__ import annotations

from dataclasses import dataclass
import tkinter as tk
from tkinter import ttk


@dataclass(frozen=True)
class ToneNormalizationSettings:
    reference: str
    strength: float


class ToneNormalizationDialog:
    def __init__(self, parent, start_frame, end_frame, current_frame):
        self.result = None
        self.window = tk.Toplevel(parent)
        self.window.title("Normalizar luz e contraste")
        self.window.geometry("700x500")
        self.window.minsize(640, 460)
        self.window.transient(parent)
        self.window.grab_set()

        container = ttk.Frame(self.window, padding=22)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(
            container,
            text="Uniformizar o posicionamento",
            font=("Segoe UI", 18, "bold"),
        ).pack(anchor=tk.W)
        ttk.Label(
            container,
            text=(
                f"Frames {start_frame}–{end_frame}. O Benedito cria uma referência tonal "
                "única e suaviza as medições no tempo para evitar pulsação de brilho."
            ),
            wraplength=640,
        ).pack(anchor=tk.W, pady=(4, 16))

        reference = ttk.LabelFrame(container, text="Referência de luz e contraste", padding=12)
        reference.pack(fill=tk.X)
        self.reference_var = tk.StringVar(value="median")
        ttk.Radiobutton(
            reference,
            text="Mediana do posicionamento — mais estável (recomendado)",
            variable=self.reference_var,
            value="median",
        ).pack(anchor=tk.W)
        ttk.Radiobutton(
            reference,
            text=f"Frame atual — frame {current_frame}",
            variable=self.reference_var,
            value="current",
        ).pack(anchor=tk.W, pady=(5, 0))
        ttk.Radiobutton(
            reference,
            text=f"Primeiro frame — frame {start_frame}",
            variable=self.reference_var,
            value="first",
        ).pack(anchor=tk.W, pady=(5, 0))

        strength = ttk.LabelFrame(container, text="Intensidade", padding=12)
        strength.pack(fill=tk.X, pady=(14, 0))
        self.strength_var = tk.DoubleVar(value=85.0)
        row = ttk.Frame(strength)
        row.pack(fill=tk.X)
        ttk.Scale(
            row,
            from_=0,
            to=100,
            variable=self.strength_var,
            command=self._update_strength,
        ).pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.strength_label = ttk.Label(row, text="85%", width=6)
        self.strength_label.pack(side=tk.LEFT, padx=(12, 0))
        ttk.Label(
            strength,
            text="Comece em 85%. Valores menores preservam mais da exposição original.",
        ).pack(anchor=tk.W, pady=(7, 0))

        ttk.Label(
            container,
            text=(
                "O resultado é salvo como uma camada derivada. Os frames originais, a "
                "estabilização e a placa limpa permanecem preservados."
            ),
            wraplength=640,
        ).pack(anchor=tk.W, pady=(16, 0))

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, side=tk.BOTTOM, pady=(18, 0))
        ttk.Button(footer, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT)
        ttk.Button(
            footer,
            text="Normalizar trecho",
            command=self._confirm,
        ).pack(side=tk.RIGHT, padx=8)

    def _update_strength(self, _value=None):
        self.strength_label.config(text=f"{self.strength_var.get():.0f}%")

    def _confirm(self):
        self.result = ToneNormalizationSettings(
            reference=self.reference_var.get(),
            strength=float(self.strength_var.get()) / 100.0,
        )
        self.window.destroy()

    def show(self):
        self.window.wait_window()
        return self.result
