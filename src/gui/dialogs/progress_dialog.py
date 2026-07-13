"""Accessible progress center for long-running Benedito tasks."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk

from core.jobs import JobState


class TaskProgressDialog:
    def __init__(self, parent, task_name, cancel_callback):
        self.parent = parent
        self.cancel_callback = cancel_callback
        self.started_monotonic = time.monotonic()
        self.last_snapshot = None

        self.window = tk.Toplevel(parent)
        self.window.title(f"Progresso — {task_name}")
        self.window.geometry("620x430")
        self.window.minsize(520, 360)
        self.window.transient(parent)
        self.window.protocol("WM_DELETE_WINDOW", self.hide)

        background = "#17131f"
        panel = "#241c31"
        text = "#f5f3f7"
        muted = "#b8afc4"
        accent = "#a855f7"
        self.colors = {
            "background": background,
            "panel": panel,
            "text": text,
            "muted": muted,
            "accent": accent,
            "success": "#22c55e",
            "error": "#f43f5e",
            "warning": "#fbbf24",
        }
        self.window.configure(bg=background)

        container = tk.Frame(self.window, bg=background)
        container.pack(fill=tk.BOTH, expand=True, padx=24, pady=20)

        tk.Label(
            container,
            text="CENTRAL DE PROGRESSO",
            font=("Segoe UI", 9, "bold"),
            fg=accent,
            bg=background,
        ).pack(anchor=tk.W)

        self.title_var = tk.StringVar(value=task_name)
        tk.Label(
            container,
            textvariable=self.title_var,
            font=("Segoe UI", 19, "bold"),
            fg=text,
            bg=background,
        ).pack(anchor=tk.W, pady=(5, 4))

        self.stage_var = tk.StringVar(value="Preparando a tarefa...")
        tk.Label(
            container,
            textvariable=self.stage_var,
            font=("Segoe UI", 11),
            fg=muted,
            bg=background,
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(0, 16))

        progress_panel = tk.Frame(container, bg=panel, padx=18, pady=16)
        progress_panel.pack(fill=tk.X)

        self.percent_var = tk.StringVar(value="0%")
        tk.Label(
            progress_panel,
            textvariable=self.percent_var,
            font=("Segoe UI", 28, "bold"),
            fg=text,
            bg=panel,
        ).pack(anchor=tk.W)

        self.progress = ttk.Progressbar(progress_panel, maximum=100, mode="determinate")
        self.progress.pack(fill=tk.X, pady=(8, 12))

        time_row = tk.Frame(progress_panel, bg=panel)
        time_row.pack(fill=tk.X)
        self.elapsed_var = tk.StringVar(value="Decorrido: 0 s")
        self.eta_var = tk.StringVar(value="Restante: calculando...")
        tk.Label(time_row, textvariable=self.elapsed_var, fg=muted, bg=panel, font=("Segoe UI", 10)).pack(side=tk.LEFT)
        tk.Label(time_row, textvariable=self.eta_var, fg=muted, bg=panel, font=("Segoe UI", 10)).pack(side=tk.RIGHT)

        self.explanation_var = tk.StringVar(
            value="O Benedito continua trabalhando. Você pode acompanhar ou ocultar esta janela."
        )
        tk.Label(
            container,
            textvariable=self.explanation_var,
            font=("Segoe UI", 10),
            fg=muted,
            bg=background,
            wraplength=560,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, pady=(16, 10))

        self.details = tk.Text(
            container,
            height=5,
            bg="#100d16",
            fg=muted,
            insertbackground=text,
            relief=tk.FLAT,
            font=("Consolas", 9),
            state=tk.DISABLED,
        )

        buttons = tk.Frame(container, bg=background)
        buttons.pack(fill=tk.X, side=tk.BOTTOM, pady=(12, 0))
        self.details_button = tk.Button(
            buttons,
            text="Mostrar detalhes",
            command=self.toggle_details,
            bg=panel,
            fg=text,
            relief=tk.FLAT,
            padx=14,
            pady=8,
        )
        self.details_button.pack(side=tk.LEFT)
        self.hide_button = tk.Button(
            buttons,
            text="Continuar em segundo plano",
            command=self.hide,
            bg=panel,
            fg=text,
            relief=tk.FLAT,
            padx=14,
            pady=8,
        )
        self.hide_button.pack(side=tk.RIGHT, padx=(8, 0))
        self.cancel_button = tk.Button(
            buttons,
            text="Cancelar tarefa",
            command=self.cancel,
            bg=self.colors["error"],
            fg="white",
            relief=tk.FLAT,
            padx=14,
            pady=8,
        )
        self.cancel_button.pack(side=tk.RIGHT)

        self._center()

    def update(self, snapshot):
        if not self.window.winfo_exists():
            return
        self.last_snapshot = snapshot
        progress = max(0.0, min(100.0, float(snapshot.progress)))
        self.progress["value"] = progress
        self.percent_var.set(f"{progress:.0f}%")
        self.title_var.set(snapshot.name)
        self.stage_var.set(snapshot.message or self._state_label(snapshot.state))
        elapsed = max(0.0, time.monotonic() - self.started_monotonic)
        self.elapsed_var.set(f"Decorrido: {self.format_seconds(elapsed)}")
        if 0 < progress < 100:
            remaining = elapsed * (100.0 - progress) / progress
            self.eta_var.set(f"Restante estimado: {self.format_seconds(remaining)}")
        elif progress >= 100:
            self.eta_var.set("Restante: concluído")
        else:
            self.eta_var.set("Restante: calculando...")
        self._update_details(snapshot)

        if snapshot.state == JobState.COMPLETED:
            self.explanation_var.set("Tarefa concluída com sucesso. O resultado já está disponível no projeto.")
            self.cancel_button.config(text="Fechar", command=self.close, bg=self.colors["success"], state=tk.NORMAL)
            self.hide_button.pack_forget()
        elif snapshot.state == JobState.CANCELLED:
            self.explanation_var.set("A tarefa foi cancelada com segurança. Resultados confirmados permanecem salvos.")
            self.cancel_button.config(text="Fechar", command=self.close, bg=self.colors["warning"], state=tk.NORMAL)
            self.hide_button.pack_forget()
        elif snapshot.state == JobState.FAILED:
            self.explanation_var.set("A tarefa encontrou um problema. Abra os detalhes para consultar a mensagem.")
            self.cancel_button.config(text="Fechar", command=self.close, bg=self.colors["error"], state=tk.NORMAL)
            self.hide_button.pack_forget()

    def cancel(self):
        self.cancel_button.config(text="Cancelando...", state=tk.DISABLED)
        self.explanation_var.set("Finalizando o ponto atual e salvando o que já foi confirmado...")
        self.cancel_callback()

    def show(self):
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def hide(self):
        self.window.withdraw()

    def close(self):
        if self.window.winfo_exists():
            self.window.destroy()

    def toggle_details(self):
        if self.details.winfo_manager():
            self.details.pack_forget()
            self.details_button.config(text="Mostrar detalhes")
        else:
            self.details.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
            self.details_button.config(text="Ocultar detalhes")

    def _update_details(self, snapshot):
        lines = [
            f"Identificador: {snapshot.id}",
            f"Estado: {snapshot.state.value}",
            f"Progresso: {snapshot.progress:.2f}%",
            f"Criada em: {snapshot.created_at}",
        ]
        if snapshot.started_at:
            lines.append(f"Iniciada em: {snapshot.started_at}")
        if snapshot.error:
            lines.append(f"Erro: {snapshot.error}")
        self.details.config(state=tk.NORMAL)
        self.details.delete("1.0", tk.END)
        self.details.insert("1.0", "\n".join(lines))
        self.details.config(state=tk.DISABLED)

    def _center(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = self.parent.winfo_rootx() + max(0, (self.parent.winfo_width() - width) // 2)
        y = self.parent.winfo_rooty() + max(0, (self.parent.winfo_height() - height) // 2)
        self.window.geometry(f"+{x}+{y}")

    @staticmethod
    def _state_label(state):
        return {
            JobState.QUEUED: "Aguardando início...",
            JobState.RUNNING: "Processando...",
            JobState.COMPLETED: "Concluído",
            JobState.CANCELLED: "Cancelado",
            JobState.FAILED: "Falha",
        }.get(state, str(state))

    @staticmethod
    def format_seconds(seconds):
        seconds = max(0, int(round(seconds)))
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours} h {minutes:02d} min"
        if minutes:
            return f"{minutes} min {seconds:02d} s"
        return f"{seconds} s"
