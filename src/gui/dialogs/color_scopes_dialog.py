"""Tkinter viewer for professional color scopes."""

import tkinter as tk
from tkinter import ttk

import cv2
from PIL import Image, ImageTk

from core.color_scopes import ColorScopeGenerator


class ColorScopesDialog:
    def __init__(self, parent, frame_provider):
        self.frame_provider = frame_provider
        self.generator = ColorScopeGenerator(640, 320)
        self.images = []
        self.window = tk.Toplevel(parent)
        self.window.title("Scopes de cor")
        self.window.geometry("760x520")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")
        header = tk.Frame(self.window, bg="#17131f")
        header.pack(fill=tk.X, padx=18, pady=(16, 8))
        tk.Label(header, text="Scopes de cor", font=("Segoe UI", 19, "bold"), fg="#f5f3f7", bg="#17131f").pack(side=tk.LEFT)
        ttk.Button(header, text="Atualizar frame", command=self.refresh).pack(side=tk.RIGHT)
        self.stats_var = tk.StringVar()
        tk.Label(self.window, textvariable=self.stats_var, fg="#b8afc4", bg="#17131f").pack(anchor=tk.W, padx=18, pady=(0, 8))
        self.notebook = ttk.Notebook(self.window)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=18, pady=(0, 18))
        self.labels = {}
        for key, title in (("histogram", "Histograma RGB"), ("waveform", "Waveform Luma"), ("vectorscope", "Vectorscope")):
            page = tk.Frame(self.notebook, bg="#08080c")
            label = tk.Label(page, bg="#08080c")
            label.pack(fill=tk.BOTH, expand=True)
            self.notebook.add(page, text=title)
            self.labels[key] = label
        self.refresh()

    def refresh(self):
        frame = self.frame_provider()
        if frame is None:
            self.stats_var.set("Nenhum frame disponível")
            return
        result = self.generator.generate(frame)
        self.images.clear()
        for key in self.labels:
            rgb = cv2.cvtColor(result[key], cv2.COLOR_BGR2RGB)
            image = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.images.append(image)
            self.labels[key].configure(image=image)
        stats = result["statistics"]
        self.stats_var.set(f"Luma: {stats.luma_min}–{stats.luma_max} • média {stats.luma_mean:.1f} • preto recortado {stats.clipped_black * 100:.2f}% • branco recortado {stats.clipped_white * 100:.2f}%")
