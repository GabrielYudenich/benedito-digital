"""Visual catalog for native model weights and attribution."""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser


class ModelRegistryDialog:
    def __init__(self, parent, registry, add_callback):
        self.parent = parent
        self.registry = registry
        self.add_callback = add_callback
        self.records = []
        self.window = tk.Toplevel(parent)
        self.window.title("Modelos e créditos")
        self.window.geometry("940x560")
        self.window.minsize(760, 460)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Modelos instalados", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=22, pady=(20, 4))
        tk.Label(self.window, text="Pesos ficam locais. Licença, origem e autoria permanecem visíveis para cada família.", font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f").pack(anchor=tk.W, padx=22, pady=(0, 14))

        frame = tk.Frame(self.window, bg="#17131f")
        frame.pack(fill=tk.BOTH, expand=True, padx=22)
        self.tree = ttk.Treeview(frame, columns=("family", "task", "size", "license"), show="tree headings")
        self.tree.heading("#0", text="Peso")
        self.tree.heading("family", text="Família")
        self.tree.heading("task", text="Tarefa")
        self.tree.heading("size", text="Tamanho")
        self.tree.heading("license", text="Licença")
        self.tree.column("#0", width=270)
        self.tree.column("family", width=120)
        self.tree.column("task", width=150)
        self.tree.column("size", width=100)
        self.tree.column("license", width=130)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self._show_details)

        self.details_var = tk.StringVar(value="Selecione um peso para consultar origem e autoria.")
        tk.Label(self.window, textvariable=self.details_var, font=("Segoe UI", 9), fg="#b8afc4", bg="#17131f", wraplength=880, justify=tk.LEFT).pack(anchor=tk.W, padx=22, pady=(10, 4))

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, padx=22, pady=16)
        tk.Button(buttons, text="Adicionar peso local...", command=self._add, bg="#a855f7", fg="white", relief=tk.FLAT, padx=14, pady=8, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(buttons, text="Abrir página de origem", command=self._open_source, bg="#3b82f6", fg="white", relief=tk.FLAT, padx=14, pady=8).pack(side=tk.LEFT, padx=8)
        tk.Button(buttons, text="Atualizar lista", command=self.refresh, bg="#352a45", fg="white", relief=tk.FLAT, padx=14, pady=8).pack(side=tk.LEFT)
        tk.Button(buttons, text="Fechar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=14, pady=8).pack(side=tk.RIGHT)
        self.refresh()

    def refresh(self):
        self.records = self.registry.discover()
        self.tree.delete(*self.tree.get_children())
        for index, record in enumerate(self.records):
            size = self._format_size(record.size)
            self.tree.insert("", tk.END, iid=str(index), text=record.name, values=(record.family, record.task, size, record.license))
        if not self.records:
            self.details_var.set("Nenhum peso encontrado. O Benedito ainda pode usar filtros OpenCV sem IA.")

    def _show_details(self, _event=None):
        record = self._selected_record()
        if not record:
            return
        self.details_var.set(
            f"Autoria: {record.attribution}  •  Origem: {record.source}  •  Caminho local: {record.path}"
        )

    def _add(self):
        path = filedialog.askopenfilename(
            parent=self.window,
            filetypes=[("Pesos de modelo", "*.pth *.pt *.ckpt *.onnx *.safetensors *.mat")],
        )
        if not path:
            return
        families = list(self.registry.families)
        family = simpledialog.askstring(
            "Família do modelo",
            "Informe uma família:\n" + "\n".join(families),
            parent=self.window,
        )
        if not family:
            return
        if family not in self.registry.families:
            messagebox.showerror("Família inválida", "Escolha uma família listada.", parent=self.window)
            return
        self.window.destroy()
        self.add_callback(path, family)

    def _open_source(self):
        record = self._selected_record()
        if record and record.source.startswith("http"):
            webbrowser.open(record.source)

    def _selected_record(self):
        selection = self.tree.selection()
        if not selection:
            return None
        return self.records[int(selection[0])]

    @staticmethod
    def _format_size(size):
        value = float(size)
        for unit in ("B", "KB", "MB", "GB"):
            if value < 1024 or unit == "GB":
                return f"{value:.1f} {unit}"
            value /= 1024
