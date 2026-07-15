"""Visual frame-level branch conflict resolution."""

import tkinter as tk
from tkinter import messagebox, ttk

from PIL import Image, ImageChops, ImageEnhance, ImageOps, ImageTk


class BranchMergeDialog:
    def __init__(self, parent, workspace, target_branch, source_branch, on_merge):
        self.workspace = workspace
        self.target_branch = target_branch
        self.source_branch = source_branch
        self.on_merge = on_merge
        self.comparison = workspace.compare_branches(target_branch, source_branch)
        self.resolutions = {}

        self.window = tk.Toplevel(parent)
        self.window.title("Comparar trabalhos")
        self.window.geometry("1040x760")
        self.window.minsize(840, 650)
        self.window.transient(parent)
        self.window.grab_set()

        container = ttk.Frame(self.window, padding=20)
        container.pack(fill=tk.BOTH, expand=True)
        ttk.Label(container, text="Mesclar alterações por frame", font=("Segoe UI", 17, "bold")).pack(anchor=tk.W)
        ttk.Label(
            container,
            text=f"Destino: {target_branch}   ←   Trabalho recebido: {source_branch}",
        ).pack(anchor=tk.W, pady=(4, 4))
        ttk.Label(
            container,
            text="Frames alterados somente pelo colega entram automaticamente. Nos conflitos, escolha qual versão deve prevalecer.",
            wraplength=800,
        ).pack(anchor=tk.W, pady=(0, 14))

        self.summary_var = tk.StringVar()
        ttk.Label(container, textvariable=self.summary_var, font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 8))

        preview = ttk.LabelFrame(container, text="Comparação visual do frame selecionado", padding=10)
        preview.pack(fill=tk.X, pady=(0, 12))
        self.preview_labels = []
        for column, title in enumerate((f"Atual — {target_branch}", f"Colega — {source_branch}", "Diferença realçada")):
            panel = ttk.Frame(preview)
            panel.grid(row=0, column=column, sticky="nsew", padx=5)
            ttk.Label(panel, text=title, font=("Segoe UI", 10, "bold")).pack()
            label = ttk.Label(panel, text="Selecione um conflito", anchor=tk.CENTER)
            label.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
            self.preview_labels.append(label)
            preview.columnconfigure(column, weight=1)

        table_frame = ttk.Frame(container)
        table_frame.pack(fill=tk.BOTH, expand=True)
        self.tree = ttk.Treeview(
            table_frame,
            columns=("current", "incoming", "choice"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Frame")
        self.tree.heading("current", text=f"{target_branch} (atual)")
        self.tree.heading("incoming", text=f"{source_branch} (colega)")
        self.tree.heading("choice", text="Escolha")
        self.tree.column("#0", width=90, anchor=tk.CENTER)
        self.tree.column("current", width=250)
        self.tree.column("incoming", width=250)
        self.tree.column("choice", width=150)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_selected_preview)

        choices = ttk.Frame(container)
        choices.pack(fill=tk.X, pady=(12, 4))
        ttk.Button(choices, text="Manter versão atual", command=lambda: self._choose("target")).pack(side=tk.LEFT)
        ttk.Button(choices, text="Usar versão do colega", command=lambda: self._choose("source")).pack(side=tk.LEFT, padx=8)
        ttk.Button(choices, text="Atual em todos", command=lambda: self._choose_all("target")).pack(side=tk.LEFT, padx=(18, 8))
        ttk.Button(choices, text="Colega em todos", command=lambda: self._choose_all("source")).pack(side=tk.LEFT)

        footer = ttk.Frame(container)
        footer.pack(fill=tk.X, pady=(14, 0))
        ttk.Button(footer, text="Cancelar", command=self.window.destroy).pack(side=tk.RIGHT, padx=(8, 0))
        self.merge_button = ttk.Button(footer, text="Confirmar mesclagem", command=self._confirm)
        self.merge_button.pack(side=tk.RIGHT)

        for conflict in self.comparison["conflicts"]:
            frame_number = conflict["frame_number"]
            self.tree.insert(
                "", tk.END, iid=str(frame_number), text=str(frame_number + 1),
                values=(conflict["target_summary"], conflict["source_summary"], "Escolha necessária"),
            )
        if self.tree.get_children():
            first = self.tree.get_children()[0]
            self.tree.selection_set(first)
            self.tree.focus(first)
            self._show_selected_preview()
        self._refresh_summary()

    def _show_selected_preview(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        frame_number = int(selection[0])
        target_image, target_kind = self._load_branch_frame(frame_number, self.target_branch)
        source_image, source_kind = self._load_branch_frame(frame_number, self.source_branch)
        if target_image is None or source_image is None:
            for label in self.preview_labels:
                label.configure(image="", text="Imagem indisponível para este frame")
                label.image = None
            return
        source_for_difference = source_image.resize(target_image.size, Image.Resampling.LANCZOS)
        difference = ImageChops.difference(target_image, source_for_difference)
        difference = ImageEnhance.Contrast(difference).enhance(2.5)
        self._set_preview(self.preview_labels[0], target_image, target_kind)
        self._set_preview(self.preview_labels[1], source_image, source_kind)
        self._set_preview(self.preview_labels[2], difference, "pixels diferentes")

    def _load_branch_frame(self, frame_number, branch_name):
        resolved = self.workspace.resolve_frame_source(frame_number, branch_name)
        if not resolved:
            return None, "indisponível"
        try:
            with Image.open(resolved["path"]) as image:
                return image.convert("RGB"), resolved["kind"]
        except Exception:
            return None, "indisponível"

    @staticmethod
    def _set_preview(label, image, description):
        preview = ImageOps.contain(image, (300, 190), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(preview)
        label.configure(image=photo, text=description, compound=tk.TOP)
        label.image = photo

    def _choose(self, choice):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Selecione um frame", "Escolha um conflito na tabela.", parent=self.window)
            return
        self._set_choice(int(selection[0]), choice)

    def _choose_all(self, choice):
        for item in self.tree.get_children():
            self._set_choice(int(item), choice)

    def _set_choice(self, frame_number, choice):
        self.resolutions[frame_number] = choice
        values = list(self.tree.item(str(frame_number), "values"))
        values[2] = "Manter atual" if choice == "target" else "Usar colega"
        self.tree.item(str(frame_number), values=values)
        self._refresh_summary()

    def _refresh_summary(self):
        total = len(self.comparison["conflicts"])
        pending = total - len(self.resolutions)
        automatic = len(self.comparison["source_only_frames"])
        self.summary_var.set(
            f"{total} conflito(s) • {pending} pendente(s) • {automatic} frame(s) recebido(s) sem conflito"
        )
        self.merge_button.configure(state=tk.NORMAL if pending == 0 else tk.DISABLED)

    def _confirm(self):
        if len(self.resolutions) != len(self.comparison["conflicts"]):
            return
        self.window.destroy()
        self.on_merge(self.source_branch, self.target_branch, dict(self.resolutions))
