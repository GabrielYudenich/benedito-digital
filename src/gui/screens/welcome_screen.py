"""
Welcome Screen for Benedito Digital
Professional welcome screen with project creation
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import os
from datetime import datetime
import shutil

from gui.themes.dark_theme import DarkTheme
from gui.modules.project_manager_gui import ProjectManagerGUI
from core.app_info import get_app_info

class WelcomeScreen:
    def __init__(self, root):
        self.root = root
        self.app_info = get_app_info()
        self.project_manager = ProjectManagerGUI()
        self.setup_ui()

    def setup_ui(self):
        # Configure dark theme
        DarkTheme.configure_tkinter(self.root)

        # Main container
        main_frame = DarkTheme.create_custom_frame(self.root, 'Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Create gradient header
        self.create_header(main_frame)

        # Main content area
        content_frame = DarkTheme.create_custom_frame(main_frame, 'Dark.TFrame')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=40, pady=20)

        # Left side - Welcome and project creation
        self.create_welcome_section(content_frame)

        # Right side - Recent projects
        self.create_recent_projects_section(content_frame)

        # Footer
        self.create_footer(main_frame)

    def create_header(self, parent):
        """Create header with logo and title"""
        header_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        header_frame.pack(fill=tk.X, pady=(0, 20))

        # Logo area (simulated with text)
        logo_frame = DarkTheme.create_custom_frame(header_frame, 'DarkSecondary.TFrame')
        logo_frame.pack(side=tk.LEFT, padx=20, pady=15)

        # Logo text with accent color
        logo_label = tk.Label(
            logo_frame,
            text="🎬",
            font=('Arial', 32),
            fg=DarkTheme.COLORS['accent_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        logo_label.pack(side=tk.LEFT, padx=(0, 10))

        # Title
        title_label = tk.Label(
            logo_frame,
            text="Benedito Digital",
            font=('Arial', 24, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        title_label.pack(side=tk.LEFT)

        subtitle_label = tk.Label(
            logo_frame,
            text="Restauração Profissional de Mídias",
            font=('Arial', 12),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        subtitle_label.pack(side=tk.LEFT, padx=(20, 0))

        # Version info
        version_label = tk.Label(
            header_frame,
            text=f"v{self.app_info.version}",
            font=('Arial', 10),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        version_label.pack(side=tk.RIGHT, padx=20, pady=15)

    def create_welcome_section(self, parent):
        """Create welcome and project creation section"""
        welcome_frame = DarkTheme.create_custom_frame(parent, 'Dark.TFrame')
        welcome_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 20))

        # Welcome title
        welcome_title = tk.Label(
            welcome_frame,
            text="Bem-vindo ao Benedito Digital",
            font=('Arial', 20, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        welcome_title.pack(anchor=tk.W, pady=(0, 10))

        welcome_desc = tk.Label(
            welcome_frame,
            text="Seu Benedito dá um jeito! Comece criando um novo projeto ou abra um existente.",
            font=('Arial', 12),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_primary'],
            wraplength=400
        )
        welcome_desc.pack(anchor=tk.W, pady=(0, 30))

        # Project creation card
        create_card = DarkTheme.create_custom_frame(welcome_frame, 'DarkSecondary.TFrame')
        create_card.pack(fill=tk.X, pady=(0, 20))

        # Card header
        card_header = tk.Frame(
            create_card,
            bg=DarkTheme.COLORS['accent_primary'],
            height=4
        )
        card_header.pack(fill=tk.X)

        card_title = tk.Label(
            create_card,
            text="📁 Criar Novo Projeto",
            font=('Arial', 16, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        card_title.pack(anchor=tk.W, padx=20, pady=(15, 10))

        # Form fields
        form_frame = DarkTheme.create_custom_frame(create_card, 'DarkSecondary.TFrame')
        form_frame.pack(fill=tk.X, padx=20, pady=(0, 20))

        # Project name
        name_label = tk.Label(
            form_frame,
            text="Nome do Projeto:",
            font=('Arial', 11),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        name_label.pack(anchor=tk.W, pady=(0, 5))

        self.project_name_entry = tk.Entry(
            form_frame,
            font=('Arial', 11),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            insertbackground=DarkTheme.COLORS['accent_primary'],
            relief=tk.FLAT,
            bd=5
        )
        self.project_name_entry.pack(fill=tk.X, pady=(0, 15))
        self.project_name_entry.bind('<Return>', lambda e: self.create_project())

        # Author
        author_label = tk.Label(
            form_frame,
            text="Autor:",
            font=('Arial', 11),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        author_label.pack(anchor=tk.W, pady=(0, 5))

        self.author_entry = tk.Entry(
            form_frame,
            font=('Arial', 11),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            insertbackground=DarkTheme.COLORS['accent_primary'],
            relief=tk.FLAT,
            bd=5
        )
        self.author_entry.pack(fill=tk.X, pady=(0, 15))

        # Description
        desc_label = tk.Label(
            form_frame,
            text="Descrição (opcional):",
            font=('Arial', 11),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        desc_label.pack(anchor=tk.W, pady=(0, 5))

        self.desc_entry = tk.Entry(
            form_frame,
            font=('Arial', 11),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            insertbackground=DarkTheme.COLORS['accent_primary'],
            relief=tk.FLAT,
            bd=5
        )
        self.desc_entry.pack(fill=tk.X, pady=(0, 20))

        experience_label = tk.Label(
            form_frame,
            text="Como você prefere começar?",
            font=('Arial', 11),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        experience_label.pack(anchor=tk.W, pady=(0, 5))

        self.experience_var = tk.StringVar(value="guided")
        experience_frame = tk.Frame(form_frame, bg=DarkTheme.COLORS['bg_secondary'])
        experience_frame.pack(fill=tk.X, pady=(0, 6))
        for text, value in (
            ("Guiado", "guided"),
            ("Intermediário", "intermediate"),
            ("Avançado", "advanced"),
        ):
            tk.Radiobutton(
                experience_frame,
                text=text,
                variable=self.experience_var,
                value=value,
                font=('Arial', 10),
                fg=DarkTheme.COLORS['text_primary'],
                bg=DarkTheme.COLORS['bg_secondary'],
                selectcolor=DarkTheme.COLORS['bg_tertiary'],
                activebackground=DarkTheme.COLORS['bg_secondary'],
                activeforeground=DarkTheme.COLORS['text_primary'],
            ).pack(side=tk.LEFT, padx=(0, 14))

        tk.Label(
            form_frame,
            text="O modo Guiado explica cada etapa. Você poderá mudar isso depois.",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary'],
        ).pack(anchor=tk.W, pady=(0, 16))

        # Create button
        create_btn = tk.Button(
            form_frame,
            text="🚀 Criar Projeto",
            font=('Arial', 12, 'bold'),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=20,
            pady=10,
            cursor='hand2',
            command=self.create_project
        )
        create_btn.pack(fill=tk.X)

        # Quick actions
        quick_frame = DarkTheme.create_custom_frame(welcome_frame, 'Dark.TFrame')
        quick_frame.pack(fill=tk.X, pady=(20, 0))

        quick_label = tk.Label(
            quick_frame,
            text="Ações Rápidas:",
            font=('Arial', 12, 'bold'),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        quick_label.pack(anchor=tk.W, pady=(0, 10))

        # Quick action buttons
        quick_btn_frame = DarkTheme.create_custom_frame(quick_frame, 'Dark.TFrame')
        quick_btn_frame.pack(fill=tk.X)

        import_btn = tk.Button(
            quick_btn_frame,
            text="📂 Importar Projeto",
            font=('Arial', 10),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=1,
            cursor='hand2',
            command=self.import_project
        )
        import_btn.pack(side=tk.LEFT, padx=(0, 10))

        settings_btn = tk.Button(
            quick_btn_frame,
            text="⚙️ Configurações",
            font=('Arial', 10),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=1,
            cursor='hand2',
            command=self.open_settings
        )
        settings_btn.pack(side=tk.LEFT)

    def create_recent_projects_section(self, parent):
        """Create recent projects section"""
        recent_frame = DarkTheme.create_custom_frame(parent, 'Dark.TFrame')
        recent_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Section title
        recent_title = tk.Label(
            recent_frame,
            text="📚 Projetos Recentes",
            font=('Arial', 16, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        recent_title.pack(anchor=tk.W, pady=(0, 15))

        # Projects list
        self.projects_list_frame = DarkTheme.create_custom_frame(recent_frame, 'DarkSecondary.TFrame')
        self.projects_list_frame.pack(fill=tk.BOTH, expand=True)

        # Load and display projects
        self.load_recent_projects()

    def load_recent_projects(self):
        """Load and display recent projects"""
        # Clear existing projects
        for widget in self.projects_list_frame.winfo_children():
            widget.destroy()

        try:
            projects = self.project_manager.list_projects_in_path()

            if not projects:
                # No projects message
                no_projects = tk.Label(
                    self.projects_list_frame,
                    text="Nenhum projeto encontrado.\nCrie seu primeiro projeto!",
                    font=('Arial', 12),
                    fg=DarkTheme.COLORS['text_muted'],
                    bg=DarkTheme.COLORS['bg_secondary'],
                    justify=tk.CENTER
                )
                no_projects.pack(expand=True, pady=40)
                return

            # Display projects
            for i, project in enumerate(projects[:5]):  # Show max 5 recent projects
                self.create_project_item(self.projects_list_frame, project, i)

        except Exception as e:
            error_label = tk.Label(
                self.projects_list_frame,
                text=f"Erro ao carregar projetos: {str(e)}",
                font=('Arial', 11),
                fg=DarkTheme.COLORS['accent_error'],
                bg=DarkTheme.COLORS['bg_secondary']
            )
            error_label.pack(pady=20)

    def create_project_item(self, parent, project, index):
        """Create a project item widget"""
        item_frame = tk.Frame(parent, bg=DarkTheme.COLORS['bg_secondary'], relief=tk.FLAT, bd=1)
        item_frame.pack(fill=tk.X, padx=15, pady=(10 if index == 0 else 5))

        # Project info
        info_frame = tk.Frame(item_frame, bg=DarkTheme.COLORS['bg_secondary'])
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=12)

        # Project name
        name_label = tk.Label(
            info_frame,
            text=project['project_name'],
            font=('Arial', 12, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        name_label.pack(anchor=tk.W)

        # Project details
        details_text = f"por {project['creator']} • {project['created_at'][:10]}"
        details_label = tk.Label(
            info_frame,
            text=details_text,
            font=('Arial', 10),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        details_label.pack(anchor=tk.W, pady=(2, 0))

        # Open button
        open_btn = tk.Button(
            item_frame,
            text="Abrir",
            font=('Arial', 10),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=5,
            cursor='hand2',
            command=lambda p=project: self.open_project(p)
        )
        open_btn.pack(side=tk.RIGHT, padx=15, pady=12)

        # Hover effect
        def on_enter(e):
            item_frame.configure(bg=DarkTheme.COLORS['bg_hover'])
            info_frame.configure(bg=DarkTheme.COLORS['bg_hover'])
            name_label.configure(bg=DarkTheme.COLORS['bg_hover'])
            details_label.configure(bg=DarkTheme.COLORS['bg_hover'])

        def on_leave(e):
            item_frame.configure(bg=DarkTheme.COLORS['bg_secondary'])
            info_frame.configure(bg=DarkTheme.COLORS['bg_secondary'])
            name_label.configure(bg=DarkTheme.COLORS['bg_secondary'])
            details_label.configure(bg=DarkTheme.COLORS['bg_secondary'])

        item_frame.bind('<Enter>', on_enter)
        info_frame.bind('<Enter>', on_enter)
        name_label.bind('<Enter>', on_enter)
        details_label.bind('<Enter>', on_enter)

        item_frame.bind('<Leave>', on_leave)
        info_frame.bind('<Leave>', on_leave)
        name_label.bind('<Leave>', on_leave)
        details_label.bind('<Leave>', on_leave)

    def create_footer(self, parent):
        """Create footer with info"""
        footer_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        # GPU status
        gpu_status = self.get_gpu_status()
        gpu_label = tk.Label(
            footer_frame,
            text=f"🚀 {gpu_status}",
            font=('Arial', 10),
            fg=DarkTheme.COLORS['accent_success'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        gpu_label.pack(side=tk.LEFT, padx=20, pady=10)

        # Copyright
        copyright_label = tk.Label(
            footer_frame,
            text=f"© {datetime.now().year} {self.app_info.name} - Software Brasileiro de Restauração de Mídias",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        copyright_label.pack(side=tk.RIGHT, padx=20, pady=10)

    def get_gpu_status(self):
        """Get GPU acceleration status"""
        try:
            import cv2
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                return f"CUDA GPU Ativada ({cv2.cuda.getCudaEnabledDeviceCount()} dispositivos)"
            elif cv2.ocl.haveOpenCL():
                return "OpenCL Acelerado"
            else:
                return "CPU Only"
        except:
            return "Verificando GPU..."

    def create_project(self):
        """Create new project"""
        name = self.project_name_entry.get().strip()
        author = self.author_entry.get().strip() or 'Anonymous'
        description = self.desc_entry.get().strip()

        if not name:
            messagebox.showerror("Erro", "Por favor, insira um nome para o projeto.")
            return

        try:
            settings = {
                'gpu_acceleration': True,
                'video_quality': 'high',
                'output_resolution': 'original',
                'experience_level': self.experience_var.get(),
                'interface_scale': 1.0,
            }

            success = self.project_manager.create_project_advanced(name, author, description, settings)
            if success:
                messagebox.showinfo("Sucesso", f"Projeto '{name}' criado com sucesso!")
                self.open_project({'project_name': name, 'project_path': name})
            else:
                messagebox.showerror("Erro", "Falha ao criar o projeto.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao criar projeto: {str(e)}")

    def open_project(self, project):
        """Open project and switch to editor"""
        try:
            reference = project.get('project_path') if project.get('external') else project['project_name']
            loaded_project = self.project_manager.load_project(reference)
            if loaded_project:
                # Switch to editor screen
                self.launch_editor(loaded_project, self.project_manager)
            else:
                messagebox.showerror("Erro", "Falha ao abrir o projeto.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao abrir projeto: {str(e)}")

    def launch_editor(self, project, project_manager):
        """Launch the editor screen"""
        try:
            from gui.screens.editor_screen import EditorScreen

            splash = tk.Toplevel(self.root)
            splash.title("Carregando...")
            splash.geometry("420x180")
            splash.resizable(False, False)
            DarkTheme.configure_tkinter(splash)
            msg = tk.Label(
                splash,
                text="Carregando projeto...",
                font=('Arial', 14, 'bold'),
                fg=DarkTheme.COLORS['text_primary'],
                bg=DarkTheme.COLORS['bg_primary']
            )
            msg.pack(pady=(30, 10))
            bar = ttk.Progressbar(splash, mode="indeterminate", length=300)
            bar.pack(pady=(0, 20))
            bar.start(10)
            splash.update_idletasks()

            # Clear welcome widgets and reuse the same root
            for widget in self.root.winfo_children():
                widget.destroy()
            self.root.title(f"Benedito Digital - {project['name']}")
            self.root.geometry("1600x900")

            editor = EditorScreen(self.root, project, project_manager)
            try:
                bar.stop()
            except Exception:
                pass
            try:
                splash.destroy()
            except Exception:
                pass

        except Exception as e:
            print(f"Erro ao carregar editor: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Erro", f"Não foi possível carregar o editor: {e}")

    def import_project(self):
        """Register an existing project folder without copying its media."""
        project_folder = filedialog.askdirectory(
            title="Escolha a pasta do projeto Benedito Digital",
            mustexist=True,
        )
        if not project_folder:
            return
        loaded_project = self.project_manager.register_external_project(project_folder)
        if loaded_project is None:
            messagebox.showerror(
                "Projeto inválido",
                "A pasta escolhida não contém metadata/project.json válido.",
            )
            return
        messagebox.showinfo(
            "Projeto registrado",
            "O projeto será aberto no local original, sem copiar vídeos ou frames.",
        )
        self.launch_editor(loaded_project, self.project_manager)

    def open_settings(self):
        """Open settings dialog"""
        if hasattr(self, "_settings_window") and self._settings_window.winfo_exists():
            self._settings_window.lift()
            return

        settings_win = tk.Toplevel(self.root)
        settings_win.title("Configurações")
        settings_win.geometry("900x600")
        settings_win.minsize(720, 480)
        DarkTheme.configure_tkinter(settings_win)
        self._settings_window = settings_win

        container = DarkTheme.create_custom_frame(settings_win, 'Dark.TFrame')
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        notebook = ttk.Notebook(container, style='Dark.TNotebook')
        notebook.pack(fill=tk.BOTH, expand=True)

        models_tab = DarkTheme.create_custom_frame(notebook, 'Dark.TFrame')
        notebook.add(models_tab, text="Modelos")

        header = tk.Label(
            models_tab,
            text="Gerenciador de Modelos (pesos custom)",
            font=('Arial', 14, 'bold'),
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        header.pack(anchor=tk.W, padx=10, pady=(10, 6))

        desc = tk.Label(
            models_tab,
            text="Adicione ou remova pesos custom. Eles ficam em models/weights/custom/<tipo>.",
            font=('Arial', 10),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        desc.pack(anchor=tk.W, padx=10, pady=(0, 10))

        action_frame = DarkTheme.create_custom_frame(models_tab, 'DarkSecondary.TFrame')
        action_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self._settings_weight_type_var = tk.StringVar(value="SwinIR")
        type_combo = ttk.Combobox(
            action_frame,
            textvariable=self._settings_weight_type_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["SwinIR", "Restormer", "DnCNN", "RRDB (BSRGAN/ESRGAN)"]
        )
        type_combo.pack(side=tk.LEFT, padx=(10, 10), pady=10)

        add_btn = tk.Button(
            action_frame,
            text="Adicionar peso (.pth)",
            font=('Arial', 10),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor='hand2',
            command=self._add_custom_weight_from_settings
        )
        add_btn.pack(side=tk.LEFT, padx=(0, 10), pady=10)

        remove_btn = tk.Button(
            action_frame,
            text="Remover selecionado",
            font=('Arial', 10),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=12,
            pady=6,
            cursor='hand2',
            command=self._remove_selected_custom_weights
        )
        remove_btn.pack(side=tk.LEFT, padx=(0, 10), pady=10)

        list_frame = DarkTheme.create_custom_frame(models_tab, 'DarkSecondary.TFrame')
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        columns = ("type", "name", "path")
        tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=12)
        tree.heading("type", text="Tipo")
        tree.heading("name", text="Arquivo")
        tree.heading("path", text="Local")
        tree.column("type", width=120, anchor=tk.W)
        tree.column("name", width=260, anchor=tk.W)
        tree.column("path", width=360, anchor=tk.W)
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 0), pady=10)

        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, padx=10, pady=10)

        self._settings_models_tree = tree
        self._refresh_custom_models_tree()

    def _settings_repo_root(self):
        return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    def _custom_weight_mapping(self, label: str) -> dict:
        value = (label or "").strip().lower()
        if "swinir" in value:
            return {"prefix": "swinir_", "folder": "swinir"}
        if "restormer" in value:
            return {"prefix": "restormer_", "folder": "restormer"}
        if "dncnn" in value:
            return {"prefix": "dncnn_", "folder": "dncnn"}
        return {"prefix": "rrdb_", "folder": "rrdb"}

    def _iter_custom_weight_roots(self):
        repo_root = self._settings_repo_root()
        roots = [
            os.path.join(repo_root, "models", "weights", "custom"),
            os.path.join(repo_root, "src", "models", "custom"),
            os.path.join(repo_root, "models", "custom"),
        ]
        return [r for r in roots if os.path.isdir(r)]

    def _refresh_custom_models_tree(self):
        tree = getattr(self, "_settings_models_tree", None)
        if tree is None:
            return
        for item in tree.get_children():
            tree.delete(item)
        repo_root = self._settings_repo_root()
        roots = self._iter_custom_weight_roots()
        if not roots:
            return
        for root in roots:
            for dirpath, _dirnames, filenames in os.walk(root):
                for filename in filenames:
                    lower = filename.lower()
                    if not lower.endswith((".pth", ".pt")):
                        continue
                    full_path = os.path.join(dirpath, filename)
                    rel_path = os.path.relpath(full_path, repo_root)
                    folder = os.path.basename(os.path.dirname(full_path)).lower()
                    if folder in ("swinir", "restormer", "dncnn", "rrdb"):
                        model_type = folder.upper() if folder != "rrdb" else "RRDB"
                    elif filename.lower().startswith("swinir_"):
                        model_type = "SwinIR"
                    elif filename.lower().startswith("restormer_"):
                        model_type = "Restormer"
                    elif filename.lower().startswith("dncnn_"):
                        model_type = "DnCNN"
                    elif filename.lower().startswith("rrdb_"):
                        model_type = "RRDB"
                    else:
                        model_type = "Custom"
                    tree.insert("", tk.END, values=(model_type, filename, rel_path))

    def _add_custom_weight_from_settings(self):
        file_path = filedialog.askopenfilename(
            title="Selecionar peso (.pth/.pt)",
            filetypes=[("Weights", "*.pth *.pt"), ("All files", "*.*")]
        )
        if not file_path:
            return
        if not file_path.lower().endswith((".pth", ".pt")):
            messagebox.showwarning("Aviso", "Selecione um arquivo .pth ou .pt.")
            return

        try:
            mapping = self._custom_weight_mapping(self._settings_weight_type_var.get())
            prefix = mapping["prefix"]
            folder = mapping["folder"]
            repo_root = self._settings_repo_root()
            dest_root = os.path.join(repo_root, "models", "weights", "custom", folder)
            os.makedirs(dest_root, exist_ok=True)

            base = os.path.basename(file_path)
            if not base.lower().startswith(prefix):
                base = prefix + base
            name, ext = os.path.splitext(base)
            dest_path = os.path.join(dest_root, base)
            idx = 1
            while os.path.exists(dest_path):
                dest_path = os.path.join(dest_root, f"{name}_{idx}{ext}")
                idx += 1

            shutil.copy2(file_path, dest_path)
            messagebox.showinfo("Sucesso", f"Peso adicionado: {os.path.basename(dest_path)}")
            self._refresh_custom_models_tree()
        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel adicionar o peso: {e}")

    def _remove_selected_custom_weights(self):
        tree = getattr(self, "_settings_models_tree", None)
        if tree is None:
            return
        selected = tree.selection()
        if not selected:
            messagebox.showinfo("Aviso", "Selecione um item para remover.")
            return
        if not messagebox.askyesno("Confirmar", "Remover os pesos selecionados?"):
            return
        repo_root = self._settings_repo_root()
        allowed_roots = self._iter_custom_weight_roots()
        removed = 0
        for item in selected:
            values = tree.item(item, "values")
            if not values or len(values) < 3:
                continue
            rel_path = values[2]
            full_path = os.path.abspath(os.path.join(repo_root, rel_path))
            if not any(full_path.startswith(os.path.abspath(r)) for r in allowed_roots):
                continue
            try:
                os.remove(full_path)
                removed += 1
            except Exception:
                continue
        if removed:
            messagebox.showinfo("Sucesso", f"{removed} peso(s) removido(s).")
        self._refresh_custom_models_tree()
