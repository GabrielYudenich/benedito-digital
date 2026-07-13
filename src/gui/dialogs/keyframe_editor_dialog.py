"""Visual editor for clip keyframes."""

import tkinter as tk
from tkinter import messagebox, ttk


class KeyframeEditorDialog:
    PARAMETERS = ("x", "y", "scale", "rotation", "opacity", "volume")

    def __init__(self, parent, timeline, clip, changed_callback):
        self.timeline = timeline
        self.clip = clip
        self.changed_callback = changed_callback
        self.window = tk.Toplevel(parent)
        self.window.title(f"Keyframes — {clip.name}")
        self.window.geometry("650x470")
        self.window.transient(parent)
        self.window.configure(bg="#17131f")
        tk.Label(self.window, text="Animação por keyframes", font=("Segoe UI", 19, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=20, pady=(18, 10))

        controls = tk.Frame(self.window, bg="#241c31", padx=12, pady=12)
        controls.pack(fill=tk.X, padx=20)
        self.parameter_var = tk.StringVar(value="opacity")
        self.time_var = tk.StringVar(value="0")
        self.value_var = tk.StringVar(value="1")
        self.interpolation_var = tk.StringVar(value="linear")
        for column, (label, widget) in enumerate((
            ("Parâmetro", ttk.Combobox(controls, textvariable=self.parameter_var, values=self.PARAMETERS, state="readonly", width=13)),
            ("Tempo no clipe", ttk.Entry(controls, textvariable=self.time_var, width=12)),
            ("Valor", ttk.Entry(controls, textvariable=self.value_var, width=12)),
            ("Interpolação", ttk.Combobox(controls, textvariable=self.interpolation_var, values=("linear", "smooth", "step"), state="readonly", width=12)),
        )):
            tk.Label(controls, text=label, fg="#f5f3f7", bg="#241c31").grid(row=0, column=column, sticky="w", padx=4)
            widget.grid(row=1, column=column, padx=4, pady=(4, 0))
        ttk.Button(controls, text="Adicionar / atualizar", command=self._set).grid(row=1, column=4, padx=8)

        self.tree = ttk.Treeview(self.window, columns=("parameter", "time", "value", "interpolation"), show="headings", selectmode="browse")
        for column, title in (("parameter", "Parâmetro"), ("time", "Tempo"), ("value", "Valor"), ("interpolation", "Interpolação")):
            self.tree.heading(column, text=title)
        self.tree.pack(fill=tk.BOTH, expand=True, padx=20, pady=14)
        footer = tk.Frame(self.window, bg="#17131f")
        footer.pack(fill=tk.X, padx=20, pady=(0, 18))
        ttk.Button(footer, text="Remover selecionado", command=self._remove).pack(side=tk.LEFT)
        ttk.Button(footer, text="Fechar", command=self.window.destroy).pack(side=tk.RIGHT)
        self.refresh()

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for parameter, curve in sorted(self.clip.keyframes.items()):
            for keyframe in curve.keyframes:
                identifier = f"{parameter}:{keyframe.time}"
                self.tree.insert("", tk.END, iid=identifier, values=(parameter, f"{keyframe.time:.3f}", f"{keyframe.value:.4g}", keyframe.interpolation))

    def _set(self):
        try:
            time = float(self.time_var.get())
            value = float(self.value_var.get())
            if time > self.clip.duration:
                raise ValueError("O tempo ultrapassa a duração do clipe")
            self.timeline.set_keyframe(self.clip.id, self.parameter_var.get(), time, value, self.interpolation_var.get())
            self.changed_callback()
            self.refresh()
        except ValueError as error:
            messagebox.showerror("Keyframe", str(error), parent=self.window)

    def _remove(self):
        selection = self.tree.selection()
        if not selection:
            return
        parameter, time = selection[0].split(":", 1)
        curve = self.clip.keyframes.get(parameter)
        if curve and curve.remove(float(time)):
            self.changed_callback()
            self.refresh()
