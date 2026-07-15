"""Visual local branch manager."""

import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk


class BranchManagerDialog:
    def __init__(self, parent, workspace, on_checkout, export_callback=None, import_callback=None, merge_callback=None):
        self.parent = parent
        self.workspace = workspace
        self.on_checkout = on_checkout
        self.export_callback = export_callback
        self.import_callback = import_callback
        self.merge_callback = merge_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Branches locais do projeto")
        self.window.geometry("980x480")
        self.window.minsize(820, 400)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        header = tk.Frame(self.window, bg="#17131f")
        header.pack(fill=tk.X, padx=22, pady=(20, 12))
        tk.Label(header, text="Versões locais", font=("Segoe UI", 20, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W)
        tk.Label(
            header,
            text="Branches separam trabalhos sem duplicar o vídeo original.",
            font=("Segoe UI", 10),
            fg="#b8afc4",
            bg="#17131f",
        ).pack(anchor=tk.W, pady=(3, 0))

        table_frame = tk.Frame(self.window, bg="#17131f")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=22)
        self.tree = ttk.Treeview(
            table_frame,
            columns=("status", "head", "created"),
            show="tree headings",
            selectmode="browse",
        )
        self.tree.heading("#0", text="Branch")
        self.tree.heading("status", text="Estado")
        self.tree.heading("head", text="Última operação")
        self.tree.heading("created", text="Criada em")
        self.tree.column("#0", width=180)
        self.tree.column("status", width=100)
        self.tree.column("head", width=150)
        self.tree.column("created", width=210)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scrollbar.set)
        self.tree.bind("<Double-1>", lambda _event: self.checkout_selected())

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, padx=22, pady=18)
        self._button(buttons, "Criar nova branch", self.create_branch, "#a855f7").pack(side=tk.LEFT)
        self._button(buttons, "Ativar selecionada", self.checkout_selected, "#3b82f6").pack(side=tk.LEFT, padx=8)
        self._button(buttons, "Exportar .bdpack", self.export_selected, "#0f766e").pack(side=tk.LEFT, padx=8)
        self._button(buttons, "Importar .bdpack", self.import_package, "#7c3aed").pack(side=tk.LEFT, padx=8)
        self._button(buttons, "Mesclar na ativa", self.merge_selected, "#b45309").pack(side=tk.LEFT, padx=8)
        self._button(buttons, "Fechar", self.window.destroy, "#352a45").pack(side=tk.RIGHT)
        self.refresh()

    def _button(self, parent, text, command, color):
        return tk.Button(parent, text=text, command=command, bg=color, fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold"))

    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for branch in self.workspace.list_branches():
            head = branch.get("head") or "Sem operações"
            if len(head) > 14:
                head = head[:14] + "…"
            self.tree.insert(
                "",
                tk.END,
                iid=branch["name"],
                text=branch["name"],
                values=("Ativa" if branch["active"] else "Disponível", head, branch.get("created_at", "")),
            )
        if self.workspace.active_branch in self.tree.get_children():
            self.tree.selection_set(self.workspace.active_branch)
            self.tree.focus(self.workspace.active_branch)

    def create_branch(self):
        name = simpledialog.askstring("Nova branch", "Nome curto, como rolo-1 ou limpeza-final:", parent=self.window)
        if not name:
            return
        try:
            self.workspace.create_branch(name.strip())
            self.workspace.checkout(name.strip())
            self.on_checkout()
            self.refresh()
        except Exception as error:
            messagebox.showerror("Não foi possível criar", str(error), parent=self.window)

    def checkout_selected(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Escolha uma branch", "Selecione uma branch na lista.", parent=self.window)
            return
        try:
            self.workspace.checkout(selection[0])
            self.on_checkout()
            self.refresh()
        except Exception as error:
            messagebox.showerror("Não foi possível trocar", str(error), parent=self.window)

    def export_selected(self):
        selection = self.tree.selection()
        if not selection or not self.export_callback:
            messagebox.showinfo("Escolha uma branch", "Selecione a branch que deseja exportar.", parent=self.window)
            return
        path = filedialog.asksaveasfilename(
            parent=self.window,
            defaultextension=".bdpack",
            filetypes=[("Pacote Benedito", "*.bdpack")],
            initialfile=f"{selection[0]}.bdpack",
        )
        if path:
            self.window.destroy()
            self.export_callback(selection[0], path)

    def import_package(self):
        if not self.import_callback:
            return
        path = filedialog.askopenfilename(
            parent=self.window,
            filetypes=[("Pacote Benedito", "*.bdpack")],
        )
        if path:
            self.window.destroy()
            self.import_callback(path)

    def merge_selected(self):
        selection = self.tree.selection()
        if not selection or not self.merge_callback:
            messagebox.showinfo("Escolha uma branch", "Selecione o trabalho que deseja mesclar.", parent=self.window)
            return
        source_branch = selection[0]
        if source_branch == self.workspace.active_branch:
            messagebox.showinfo("Escolha outra branch", "A branch selecionada já é a branch ativa.", parent=self.window)
            return
        target_branch = self.workspace.active_branch
        self.window.destroy()
        self.merge_callback(source_branch, target_branch)
