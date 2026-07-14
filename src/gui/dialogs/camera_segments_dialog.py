"""GUI for reusable camera/shot frame ranges."""

import tkinter as tk
from tkinter import messagebox, simpledialog, ttk


class CameraSegmentsDialog:
    def __init__(
        self,
        parent,
        segments,
        current_range,
        detect_callback,
        add_callback,
        delete_callback,
        apply_callback,
    ):
        self.detect_callback = detect_callback
        self.add_callback = add_callback
        self.delete_callback = delete_callback
        self.apply_callback = apply_callback
        self.current_range = current_range
        self.segments = []
        self.window = tk.Toplevel(parent)
        self.window.title("Cenas e posições de câmera")
        self.window.geometry("760x560")
        self.window.minsize(620, 430)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(
            self.window,
            text="Separar por cena ou posição de câmera",
            font=("Segoe UI", 20, "bold"),
            fg="#f5f3f7",
            bg="#17131f",
        ).pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text=(
                "Cada segmento reutiliza o mesmo intervalo nas ferramentas de estabilização, "
                "limpeza, restauração e placa limpa. A detecção automática sugere cortes; "
                "você continua no controle."
            ),
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
            wraplength=700,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        table = tk.Frame(self.window, bg="#241c31")
        table.pack(fill=tk.BOTH, expand=True, padx=24)
        self.tree = ttk.Treeview(
            table,
            columns=("start", "end", "length"),
            show="tree headings",
            style="Dark.Treeview",
        )
        self.tree.heading("#0", text="Cena / câmera")
        self.tree.heading("start", text="Início")
        self.tree.heading("end", text="Final")
        self.tree.heading("length", text="Frames")
        self.tree.column("#0", width=300)
        for column in ("start", "end", "length"):
            self.tree.column(column, width=100, anchor=tk.CENTER)
        scrollbar = ttk.Scrollbar(table, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(8, 0), pady=8)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 8), pady=8)
        self.tree.bind("<Double-1>", lambda _event: self._apply())

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, padx=24, pady=18)
        self.detect_button = tk.Button(
            buttons,
            text="Detectar câmeras automaticamente",
            command=lambda: self.detect_callback(self),
            bg="#a855f7",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        )
        self.detect_button.pack(side=tk.LEFT)
        tk.Button(
            buttons,
            text=f"Salvar intervalo {current_range[0]}–{current_range[1]}",
            command=self._add,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.LEFT, padx=6)
        tk.Button(
            buttons,
            text="Excluir",
            command=self._delete,
            bg="#352a45",
            fg="white",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.LEFT)
        tk.Button(
            buttons,
            text="Usar intervalo selecionado",
            command=self._apply,
            bg="#c084fc",
            fg="#0b0712",
            relief=tk.FLAT,
            padx=12,
            pady=8,
        ).pack(side=tk.RIGHT)
        self.set_segments(segments)

    def set_segments(self, segments):
        self.segments = list(segments)
        for item in self.tree.get_children(""):
            self.tree.delete(item)
        for segment in self.segments:
            self.tree.insert(
                "",
                tk.END,
                iid=segment.id,
                text=segment.name,
                values=(segment.start + 1, segment.end + 1, segment.end - segment.start + 1),
            )

    def set_detecting(self, active):
        self.detect_button.config(
            state=tk.DISABLED if active else tk.NORMAL,
            text="Detectando..." if active else "Detectar câmeras automaticamente",
        )

    def _selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Escolha uma cena", "Selecione uma cena ou câmera primeiro.", parent=self.window)
            return None
        return next((item for item in self.segments if item.id == selection[0]), None)

    def _add(self):
        name = simpledialog.askstring(
            "Nome da cena", "Nome ou posição da câmera:", parent=self.window
        )
        if name:
            self.add_callback(name, self.current_range[0], self.current_range[1], self)

    def _delete(self):
        segment = self._selected()
        if segment:
            self.delete_callback(segment, self)

    def _apply(self):
        segment = self._selected()
        if segment:
            self.apply_callback(segment)
            self.window.destroy()
