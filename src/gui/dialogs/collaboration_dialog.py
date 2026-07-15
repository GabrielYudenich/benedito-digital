"""Shared-folder collaboration interface."""

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from core.collaboration import FolderCollaborationRemote


class CollaborationDialog:
    def __init__(self, parent, workspace, initial_remote, push_callback, pull_callback):
        self.workspace = workspace
        self.push_callback = push_callback
        self.pull_callback = pull_callback
        self.window = tk.Toplevel(parent)
        self.window.title("Colaboração da equipe")
        self.window.geometry("900x580")
        self.window.minsize(760, 500)
        self.window.transient(parent)
        self.window.configure(bg="#17131f")

        tk.Label(self.window, text="Colaboração sem servidor", font=("Segoe UI", 21, "bold"), fg="#f5f3f7", bg="#17131f").pack(anchor=tk.W, padx=24, pady=(22, 4))
        tk.Label(
            self.window,
            text="Escolha uma pasta local, NAS ou sincronizada. Somente operações e pixels alterados são enviados; o original nunca é copiado.",
            font=("Segoe UI", 10), fg="#b8afc4", bg="#17131f", wraplength=820, justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=24, pady=(0, 16))

        remote_row = tk.Frame(self.window, bg="#17131f")
        remote_row.pack(fill=tk.X, padx=24)
        self.remote_var = tk.StringVar(value=initial_remote or "")
        ttk.Entry(remote_row, textvariable=self.remote_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(remote_row, text="Escolher pasta", command=self._browse).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Button(remote_row, text="Atualizar", command=self.refresh).pack(side=tk.LEFT, padx=(8, 0))

        local_row = tk.Frame(self.window, bg="#17131f")
        local_row.pack(fill=tk.X, padx=24, pady=(14, 10))
        tk.Label(local_row, text="Enviar branch local:", fg="#f5f3f7", bg="#17131f").pack(side=tk.LEFT)
        self.local_branch_var = tk.StringVar(value=workspace.active_branch)
        ttk.Combobox(
            local_row,
            textvariable=self.local_branch_var,
            values=[item["name"] for item in workspace.list_branches()],
            state="readonly",
            width=28,
        ).pack(side=tk.LEFT, padx=8)
        tk.Button(local_row, text="Push — enviar alterações", command=self._push, bg="#0f766e", fg="white", relief=tk.FLAT, padx=14, pady=7).pack(side=tk.LEFT)

        table_frame = tk.Frame(self.window, bg="#17131f")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=(4, 0))
        self.tree = ttk.Treeview(table_frame, columns=("head", "operations", "objects", "date"), show="tree headings", selectmode="browse")
        self.tree.heading("#0", text="Branch remota")
        self.tree.heading("head", text="Head")
        self.tree.heading("operations", text="Operações")
        self.tree.heading("objects", text="Objetos")
        self.tree.heading("date", text="Publicada em")
        self.tree.column("#0", width=180)
        self.tree.column("head", width=140)
        self.tree.column("operations", width=80, anchor=tk.CENTER)
        self.tree.column("objects", width=80, anchor=tk.CENTER)
        self.tree.column("date", width=210)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = ttk.Scrollbar(table_frame, command=self.tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.config(yscrollcommand=scrollbar.set)

        buttons = tk.Frame(self.window, bg="#17131f")
        buttons.pack(fill=tk.X, padx=24, pady=18)
        tk.Button(buttons, text="Pull — trazer branch selecionada", command=self._pull, bg="#7c3aed", fg="white", relief=tk.FLAT, padx=16, pady=9, font=("Segoe UI", 10, "bold")).pack(side=tk.LEFT)
        tk.Button(buttons, text="Fechar", command=self.window.destroy, bg="#352a45", fg="white", relief=tk.FLAT, padx=16, pady=9).pack(side=tk.RIGHT)
        if initial_remote:
            self.refresh(silent=True)

    def _browse(self):
        path = filedialog.askdirectory(parent=self.window, title="Pasta compartilhada da equipe")
        if path:
            self.remote_var.set(path)
            self.refresh()

    def refresh(self, silent=False):
        path = self.remote_var.get().strip()
        if not path:
            if not silent:
                messagebox.showinfo("Colaboração", "Escolha uma pasta compartilhada.", parent=self.window)
            return
        try:
            remote = FolderCollaborationRemote(path)
            remote.initialize()
            branches = remote.list_branches(self.workspace)
            self.tree.delete(*self.tree.get_children())
            for branch in branches:
                head = branch.get("head") or "Sem operações"
                self.tree.insert("", tk.END, iid=branch["name"], text=branch["name"], values=(head[:14], branch.get("operations", 0), branch.get("objects", 0), branch.get("published_at", "")))
        except Exception as error:
            if not silent:
                messagebox.showerror("Colaboração", str(error), parent=self.window)

    def _push(self):
        path = self.remote_var.get().strip()
        branch = self.local_branch_var.get().strip()
        if not path or not branch:
            messagebox.showinfo("Colaboração", "Escolha a pasta e a branch.", parent=self.window)
            return
        self.window.destroy()
        self.push_callback(path, branch)

    def _pull(self):
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Colaboração", "Selecione uma branch remota.", parent=self.window)
            return
        path = self.remote_var.get().strip()
        self.window.destroy()
        self.pull_callback(path, selection[0])
