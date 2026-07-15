"""Friendly frame extraction preparation dialog."""

import tkinter as tk
from tkinter import ttk

from core.storage import estimate_lossless_frames_bytes, format_bytes, storage_preflight


class ExtractionDialog:
    def __init__(self, parent, video_info, current_value, start_callback, destination_dir=None):
        self.video_info = video_info or {}
        self.start_callback = start_callback
        self.destination_dir = destination_dir
        self.window = tk.Toplevel(parent)
        self.window.title("Preparar extração de frames")
        self.window.geometry("620x520")
        self.window.minsize(540, 460)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Preparar os frames", font=("Segoe UI", 22, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text="O vídeo original não será alterado. O Benedito criará imagens PNG sem perda para o trabalho quadro a quadro.",
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=560, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        info_panel = tk.Frame(self.window, bg="#241c31", padx=16, pady=14)
        info_panel.pack(fill=tk.X, padx=24)
        duration = float(self.video_info.get("duration", 0) or 0)
        fps = float(self.video_info.get("fps", 0) or 0)
        width = int(self.video_info.get("width", 0) or 0)
        height = int(self.video_info.get("height", 0) or 0)
        info_text = (
            f"Duração: {self._format_duration(duration)}\n"
            f"Imagem: {width} × {height}\n"
            f"FPS detectado: {fps:.3f}" if fps else f"Duração: {self._format_duration(duration)}\nImagem: {width} × {height}\nFPS detectado: indisponível"
        )
        tk.Label(info_panel, text=info_text, font=("Segoe UI", 11), fg="#f5f3f7", bg="#241c31", justify=tk.LEFT).pack(anchor=tk.W)

        controls = tk.Frame(self.window, bg="#17131f")
        controls.pack(fill=tk.X, padx=24, pady=(18, 0))
        tk.Label(controls, text="Frames por segundo", font=("Segoe UI", 11, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        self.fps_var = tk.StringVar(value=current_value or "Original")
        self.fps_combo = ttk.Combobox(
            controls,
            textvariable=self.fps_var,
            values=("Original", "1", "12", "16", "18", "23.976", "24", "25", "29.97", "30", "50", "60"),
            state="normal",
            font=("Segoe UI", 11),
        )
        self.fps_combo.pack(fill=tk.X, pady=(6, 5))
        self.fps_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_estimate())
        self.fps_combo.bind("<KeyRelease>", lambda _event: self._refresh_estimate())

        self.estimate_var = tk.StringVar()
        tk.Label(controls, textvariable=self.estimate_var, font=("Segoe UI", 10), fg="#c084fc", bg="#17131f").pack(anchor=tk.W, pady=(2, 12))

        warning = tk.Frame(self.window, bg="#332711", padx=14, pady=12)
        warning.pack(fill=tk.X, padx=24)
        tk.Label(
            warning,
            text="Atenção ao espaço em disco",
            font=("Segoe UI", 11, "bold"), fg="#fbbf24", bg="#332711",
        ).pack(anchor=tk.W)
        tk.Label(
            warning,
            text="PNG preserva a imagem, mas uma sequência longa pode ocupar muitas vezes o tamanho do vídeo comprimido. A janela de progresso mostrará cada etapa.",
            font=("Segoe UI", 10), fg="#f5f3f7", bg="#332711", wraplength=530, justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(3, 0))
        self.space_var = tk.StringVar()
        self.space_label = tk.Label(
            warning,
            textvariable=self.space_var,
            font=("Segoe UI", 10, "bold"),
            fg="#fde68a",
            bg="#332711",
            wraplength=530,
            justify=tk.LEFT,
        )
        self.space_label.pack(anchor=tk.W, pady=(6, 0))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, side=tk.BOTTOM, padx=24, pady=20)
        tk.Button(buttons, text="Voltar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        tk.Button(buttons, text="Iniciar extração", command=self._start, bg="#a855f7", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=8)
        self._refresh_estimate()

    def _refresh_estimate(self):
        duration = float(self.video_info.get("duration", 0) or 0)
        source_fps = float(self.video_info.get("fps", 0) or 0)
        count = self.estimate_frame_count(duration, self.fps_var.get(), source_fps)
        if count is None:
            self.estimate_var.set("Quantidade estimada: aguardando um FPS válido")
            self.space_var.set("Informe um FPS válido para calcular o espaço.")
        else:
            self.estimate_var.set(f"Quantidade estimada: {count:,} frames".replace(",", "."))
            fps_value = source_fps if self.fps_var.get().strip().lower() in {"original", "orig", "fonte"} else float(self.fps_var.get())
            estimated = estimate_lossless_frames_bytes(
                duration,
                fps_value,
                int(self.video_info.get("width", 0) or 0),
                int(self.video_info.get("height", 0) or 0),
            )
            if self.destination_dir:
                preflight = storage_preflight(self.destination_dir, estimated)
                status = "espaço suficiente" if preflight.enough else "espaço insuficiente"
                self.space_var.set(
                    f"Estimativa conservadora: {format_bytes(estimated)} • "
                    f"livre: {format_bytes(preflight.available_bytes)} • {status}"
                )
                self.space_label.config(fg="#86efac" if preflight.enough else "#fca5a5")
            else:
                self.space_var.set(f"Estimativa conservadora: {format_bytes(estimated)}")

    def _start(self):
        value = self.fps_var.get().strip() or "Original"
        self.window.destroy()
        self.start_callback(value)

    @staticmethod
    def estimate_frame_count(duration, fps_value, source_fps):
        try:
            if str(fps_value).strip().lower() in {"original", "orig", "fonte"}:
                fps = float(source_fps)
            else:
                fps = float(fps_value)
            if duration <= 0 or fps <= 0:
                return None
            return round(float(duration) * fps)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _format_duration(seconds):
        seconds = max(0, int(round(seconds)))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
