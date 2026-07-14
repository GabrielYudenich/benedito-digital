"""
Editor Screen for Benedito Digital
Professional video editor interface with dark theme
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import simpledialog
import os
import hashlib
import json
import cv2
import numpy as np
import shutil
import threading
import queue
from pathlib import Path

from gui.themes.dark_theme import DarkTheme
from gui.modules.video_player import VideoPlayer
from gui.modules.video_processor import ProcessingCancelled, VideoProcessor
from gui.modules.frame_manager import FrameManager
from lib.modules.frame.restoration.restorer import TemporalRestorer, RestorerConfig
from lib.modules.frame.restoration.manual_editor import open_manual_editor
from lib.modules.frame.restoration.model_pipeline import ModelPipeline
from lib.modules.project.state.project_state import ProjectStateManager
from lib.modules.frame.mask.mask_generator import MaskGenerator
from lib.modules.video.renderer.video_renderer import VideoRenderer
from lib.utils.presets import get_global_preset_settings
from lib.utils.logger import get_logger
from core.chunks import ChunkedFrameRunner
from core.damage_analysis import FrameDamageAnalyzer
from core.jobs import JobManager, JobState
from core.model_registry import ModelRegistry
from core.paths import default_models_dir, resource_root
from core.media_browser import paginate_frame_files
from core.selections import polygon_mask, rectangle_mask, selection_bounds
from core.storage import estimate_lossless_frames_bytes, require_free_space
from core.accessibility import AccessibilityPreferences
from core.camera_segments import CameraSegment, CameraSegmentStore, detect_camera_segments
from core.clean_plate import apply_clean_plate, build_clean_plate, detect_transient_defects
from gui.controllers.frame_retouch_controller import FrameRetouchController
from gui.controllers.film_registration_controller import FilmRegistrationController
from gui.controllers.collaboration_controller import CollaborationController
from gui.controllers.timeline_controller import TimelineController
from gui.controllers.color_scopes_controller import ColorScopesController
from gui.controllers.update_controller import UpdateController
from gui.controllers.project_version_controller import ProjectVersionController
from gui.dialogs.accessibility_dialog import AccessibilityDialog
from gui.dialogs.camera_segments_dialog import CameraSegmentsDialog
from gui.dialogs.clean_plate_dialog import CleanPlateDialog
from gui.dialogs.damage_analysis_dialog import DamageAnalysisDialog
from gui.dialogs.extraction_dialog import ExtractionDialog
from gui.dialogs.import_video_dialog import ImportModeDialog, ImportVideoDialog
from gui.dialogs.export_dialog import ExportDialog
from gui.dialogs.ffmpeg_config import FFmpegConfigDialog
from gui.dialogs.model_registry_dialog import ModelRegistryDialog
from gui.dialogs.progress_dialog import TaskProgressDialog
from gui.dialogs.proxy_dialog import ProxyDialog
from gui.dialogs.restoration_workflow_dialog import RestorationWorkflowDialog, VHSProcessingDialog
from gui.dialogs.workflow_assistant import WorkflowAssistant
from gui.mousewheel import scroll_canvas_if_within
from gui.frame_view import anchored_zoom_pan, clamp_view_pan, filmstrip_window_indices

class EditorScreen:
    FRAME_STATUS_LABELS = {
        "Sem marcação": "unmarked",
        "Revisar": "review",
        "Poeira / sujeira": "dust",
        "Risco": "scratch",
        "Mancha / degradação": "stain",
        "Frame ausente / inválido": "missing",
        "Perfuração / registro": "perforation",
        "Aprovado": "approved",
    }
    FRAME_STATUS_COLORS = {
        "review": "#fbbf24",
        "dust": "#f97316",
        "scratch": "#ef4444",
        "stain": "#a855f7",
        "missing": "#111827",
        "perforation": "#f97316",
        "approved": "#22c55e",
    }

    def __init__(self, root, project, project_manager):
        self.root = root
        self.project = project
        self.project_manager = project_manager
        self.workspace = getattr(project_manager, "workspace", None)

        # Initialize logger
        self.logger = get_logger()
        self.logger.log_project_action("OPENED", project['name'])

        # Initialize managers
        self.video_player = VideoPlayer(use_gpu=True)
        self.video_processor = VideoProcessor(use_gpu=True)
        self.job_manager = JobManager()
        self.chunk_runner = ChunkedFrameRunner(chunk_size=24)
        self._active_job_id = None
        self._active_job_callbacks = {}
        self.progress_dialog = None
        self._base_tk_scaling = float(self.root.tk.call("tk", "scaling"))
        project_settings = self.project_manager.get_project_settings()
        self.accessibility_preferences = AccessibilityPreferences.from_dict(
            project_settings.get("accessibility", {"interface_scale": project_settings.get("interface_scale", 1.0)})
        )
        self.interface_scale = self.accessibility_preferences.scale
        self.reduced_motion = self.accessibility_preferences.reduced_motion
        self.root.tk.call("tk", "scaling", self._base_tk_scaling * self.interface_scale)
        # Initialize frame manager from project path
        self.frame_manager = FrameManager(self.project_manager.current_project_path)
        self.restorer = TemporalRestorer(RestorerConfig())
        self.restored_dir = os.path.join(self.project_manager.current_project_path, "restored")
        self.manual_stab_dir = os.path.join(self.project_manager.current_project_path, "stabilized_manual")
        self.auto_stab_dir = os.path.join(self.project_manager.current_project_path, "stabilized_auto")
        self.upscaled_dir = os.path.join(self.project_manager.current_project_path, "upscaled")
        self.view_mode = "original"
        repo_root = str(resource_root())
        self.repo_root = repo_root
        models_roots = []
        candidate_src = os.path.join(repo_root, "src", "models")
        candidate_root = os.path.join(repo_root, "models")
        bundled_weights_root = os.path.join(candidate_root, "weights")
        self.native_weights_root = str(default_models_dir())
        os.makedirs(self.native_weights_root, exist_ok=True)
        if os.path.isdir(candidate_src):
            models_roots.append(candidate_src)
        if self.native_weights_root not in models_roots:
            models_roots.append(self.native_weights_root)
        if os.path.isdir(bundled_weights_root):
            models_roots.append(bundled_weights_root)
        if os.path.isdir(candidate_root) and candidate_root not in models_roots:
            models_roots.append(candidate_root)
        self.model_roots = models_roots or [candidate_root]
        self.model_pipeline = ModelPipeline(self.model_roots)
        self.model_registry = ModelRegistry(
            os.path.join(candidate_root, "registry.json"),
            [candidate_src, self.native_weights_root, candidate_root],
        )
        self.masks_dir = os.path.join(self.project_manager.current_project_path, "masks")
        self.auto_masks_dir = os.path.join(self.project_manager.current_project_path, "masks_auto")
        self._configure_branch_paths()
        self.camera_segment_store = CameraSegmentStore(
            self.project_manager.current_project_path
        )
        self.brush_size = 12
        self.frame_zoom = 1.0
        self.frame_pan = (0.0, 0.0)
        self._zoom_redraw_job = None
        self._slider_navigation_job = None
        self._filmstrip_update_job = None
        self._secondary_pan_start = None
        self._secondary_pan_origin = (0.0, 0.0)
        self._secondary_dragged = False
        self.show_mask_overlay = True
        self.show_auto_mask = False
        self.double_pass_var = tk.BooleanVar(value=False)
        self._current_mask = None
        self._current_mask_path = None
        self._selection_mask = None
        self._selection_frame_path = None
        self._selection_start = None
        self._selection_points = []
        self._selection_canvas_item = None
        self.retouch_controller = FrameRetouchController(self)
        self.version_controller = ProjectVersionController(self)
        self.film_registration_controller = FilmRegistrationController(self)
        self.collaboration_controller = CollaborationController(self)
        self.timeline_controller = TimelineController(self)
        self.color_scopes_controller = ColorScopesController(self)
        self.update_controller = UpdateController(self)
        self._view_scale = 1.0
        self._view_offset = (0, 0)
        self._filmstrip_images = []
        self._filmstrip_map = {}
        self._filmstrip_positions = {}
        self._filmstrip_signature = None
        self._thumb_cache = {}
        self._thumb_cache_order = []
        self._thumb_cache_max = 96
        self._filmstrip_placeholder_cache = {}
        self._thumb_generation_queue = queue.Queue()
        self._thumb_ready_queue = queue.Queue()
        self._thumb_generation_pending = set()
        self._thumb_generation_lock = threading.Lock()
        self._thumb_worker_stop = threading.Event()
        self._thumb_worker = None
        self._thumb_ready_job = None
        self._frame_image_cache = {}
        self._frame_image_cache_order = []
        self._frame_image_cache_max = 8
        self._current_display_image = None
        self._detached_viewer = None
        self._detached_canvas = None
        self._detached_render_job = None
        self._frame_bottom_visible = True
        self._updating_frame_slider = False
        self.undo_stack = []
        self.redo_stack = []
        self._play_pulse_job = None
        self._play_pulse_state = False
        self._playback_ui_lock = threading.Lock()
        self._pending_playback_frame = None
        self._pending_playback_progress = None
        self._pending_playback_finished = False
        self._playback_ui_job = None
        self._models_last_mtime = 0
        self._status_anim_job = None
        self._status_anim_phase = 0
        cache_root = str(self.workspace.cache_dir) if self.workspace else os.path.join(self.project_manager.current_project_path, "cache")
        self.thumb_cache_root = os.path.join(cache_root, "thumbnails", "filmstrip")
        self._thumb_worker = threading.Thread(
            target=self._filmstrip_thumb_worker,
            name="benedito-filmstrip-thumbs",
            daemon=True,
        )
        self._thumb_worker.start()

        # Initialize new components
        self.project_state = ProjectStateManager(self.project_manager.current_project_path)
        self.mask_generator = MaskGenerator()
        self.video_renderer = VideoRenderer(use_gpu=True)

        # UI state
        self.current_frame = self.project_state.get_current_frame()
        self.total_frames = self.frame_manager.get_frame_count() or self.project_state.get_total_frames()
        self.is_playing = False
        self.audio_enabled_var = tk.BooleanVar(value=True)
        self.current_video = None
        self.current_video_path = self.project_state.get_video_path()
        self.selected_tool = "brush"

        # Apply dark theme
        self.setup_theme()
        self.setup_ui()
        DarkTheme.apply_accessibility(self.root, self.accessibility_preferences)
        self.load_project_videos()
        self._playback_ui_job = self.root.after(16, self._drain_playback_ui)
        self._thumb_ready_job = self.root.after(50, self._drain_thumb_ready)
        self.root.after(250, self._show_state_recovery_notice)

        # Bind cleanup
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self._bind_shortcuts()
        self._start_models_watch()
        experience_level = self.project_manager.get_project_settings().get(
            "experience_level", "guided"
        )
        if experience_level == "guided" and not self.project_manager.get_project_videos():
            self.root.after(700, self.open_workflow_assistant)

    def _show_state_recovery_notice(self):
        report = self.project_state.recovery_report
        if report.get("recovered"):
            messagebox.showwarning(
                "Posição de trabalho recuperada",
                "O Benedito restaurou a última posição, seleção e configuração salvas com segurança.",
            )
        elif report.get("migrations"):
            messagebox.showinfo(
                "Preferências atualizadas",
                "As preferências deste projeto foram atualizadas para o formato atual.",
            )
        elif report.get("error"):
            messagebox.showwarning(
                "Estado visual protegido",
                "A posição e as preferências não puderam ser recuperadas. O arquivo danificado foi preservado e novas gravações foram bloqueadas; o histórico de restauração não foi alterado.",
            )

    def setup_theme(self):
        """Setup dark theme for the editor"""
        try:
            DarkTheme.configure_tkinter(self.root)
        except Exception as e:
            if hasattr(self, 'logger'):
                self.logger.warning(f"Could not setup theme: {e}")
            else:
                print(f"⚠️  Could not setup theme: {e}")

    def create_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Trocar projeto", command=self.back_to_welcome)
        file_menu.add_separator()
        file_menu.add_command(label="Sair", command=self.exit_app)
        menubar.add_cascade(label="Arquivo", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Undo", command=self.undo_action)
        edit_menu.add_command(label="Redo", command=self.redo_action)
        edit_menu.add_separator()
        edit_menu.add_command(label="Timeline multipista...", command=self.timeline_controller.open_dialog)
        menubar.add_cascade(label="Editar", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_command(label="Original", command=lambda: self._set_view_mode("original"))
        view_menu.add_command(label="Restaurado", command=lambda: self._set_view_mode("restored"))
        view_menu.add_command(label="Comparar (split)", command=self.enable_compare_view)
        view_menu.add_command(label="Scopes de cor...", command=self.color_scopes_controller.open_dialog)
        view_menu.add_separator()
        view_menu.add_command(label="Mostrar máscara manual", command=lambda: self._toggle_var(self.show_mask_var))
        view_menu.add_command(label="Mostrar auto-máscara", command=lambda: self._toggle_var(self.show_auto_mask_var))
        view_menu.add_separator()
        view_menu.add_command(label="Ocultar/mostrar painel inferior", command=self.toggle_frame_bottom_panel)
        view_menu.add_command(label="Abrir frame em segunda tela", command=self.open_detached_frame_viewer)
        view_menu.add_command(label="Ajustar frame à janela", command=self.reset_frame_view)
        menubar.add_cascade(label="Exibir", menu=view_menu)

        version_menu = tk.Menu(menubar, tearoff=0)
        version_menu.add_command(label="Gerenciar branches...", command=self.open_branch_manager)
        version_menu.add_command(label="Colaboração da equipe...", command=self.collaboration_controller.open_dialog)
        version_menu.add_command(label="Histórico do frame", command=self.show_current_frame_history)
        version_menu.add_separator()
        version_menu.add_command(label="Resetar frame para o original", command=self.reset_current_frame_to_original)
        menubar.add_cascade(label="Versionamento", menu=version_menu)

        workflow_menu = tk.Menu(menubar, tearoff=0)
        workflow_menu.add_command(
            label="Escolher fluxo de restauração...",
            command=self.open_restoration_workflows,
        )
        workflow_menu.add_command(
            label="Analisar danos nos frames...", command=self.open_damage_analysis
        )
        workflow_menu.add_command(
            label="Criar proxy de edição...", command=self.open_proxy_dialog
        )
        workflow_menu.add_command(
            label="Alinhar película pelas perfurações...",
            command=self.film_registration_controller.open_dialog,
        )
        menubar.add_cascade(label="Fluxos", menu=workflow_menu)

        models_menu = tk.Menu(menubar, tearoff=0)
        models_menu.add_command(
            label="Modelos instalados e créditos...",
            command=self.open_model_registry,
        )
        models_menu.add_command(
            label="Atualizar detecção de modelos",
            command=lambda: self.refresh_models(silent=False),
        )
        menubar.add_cascade(label="Modelos", menu=models_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="Assistente de restauração", command=self.open_workflow_assistant)
        help_menu.add_command(label="Leitura e acessibilidade", command=self.open_accessibility_dialog)
        help_menu.add_command(label="Verificar atualizações...", command=self.update_controller.check)
        help_menu.add_separator()
        help_menu.add_command(label="Tutorial rápido", command=self.open_tutorial)
        help_menu.add_command(label="Ajuda", command=self.show_help_dialog)
        menubar.add_cascade(label="Ajuda", menu=help_menu)

        self.root.config(menu=menubar)

    def open_branch_manager(self):
        self.version_controller.open_manager()

    def _export_branch_package(self, branch_name, package_path):
        self.version_controller.export_branch_package(branch_name, package_path)

    def _import_branch_package(self, package_path):
        self.version_controller.import_branch_package(package_path)

    def _open_branch_merge(self, source_branch, target_branch):
        self.version_controller.open_branch_merge(source_branch, target_branch)

    def _merge_branch(self, source_branch, target_branch, resolutions):
        self.version_controller.merge_branch(
            source_branch, target_branch, resolutions
        )

    def open_workflow_assistant(self):
        WorkflowAssistant(
            self.root,
            {
                "import": self.import_video,
                "prepare": lambda: self.notebook.select(2),
                "frames": self._go_to_frames,
                "restore": self.open_restoration_workflows,
                "export": self.show_render_options,
            },
        )

    def open_restoration_workflows(self):
        RestorationWorkflowDialog(self.root, self._apply_restoration_workflow)

    def _apply_restoration_workflow(self, workflow):
        if workflow == "film":
            self.fps_entry.delete(0, tk.END)
            self.fps_entry.insert(0, "Original")
            self.global_preset_var.set("Cinema")
            self._apply_global_preset()
            self.deflicker_var.set(True)
            self._go_to_frames()
            self.status_var.set(
                "Fluxo Filme preparado: inspecione, selecione e analise os frames"
            )
            if self.frame_manager and self.frame_manager.frames:
                self.open_damage_analysis()
        elif workflow == "quick":
            self.global_preset_var.set("Conservador")
            self._apply_global_preset()
            self.model_name_var.set("DnCNN (OpenCV)")
            self._go_to_frames()
            self.status_var.set(
                "Fluxo conservador preparado: marque um intervalo e aplique o filtro"
            )
        else:
            if not self.current_video:
                messagebox.showinfo(
                    "Escolha um vídeo",
                    "Importe e selecione uma captura VHS antes de iniciar este fluxo.",
                )
                return
            stem = os.path.splitext(self.current_video)[0]
            default_output = os.path.join(
                self.project_manager.get_exports_dir(),
                "renders",
                f"{stem}_vhs_restaurado.mp4",
            )
            VHSProcessingDialog(
                self.root, default_output, self._start_vhs_restoration
            )

    def _start_vhs_restoration(self, config):
        input_path = os.path.join(
            self.project_manager.get_originals_dir(), self.current_video
        )

        def vhs_task(context):
            try:
                success = self.video_processor.restore_vhs(
                    input_path,
                    config["output"],
                    deinterlace=config["deinterlace"],
                    denoise=config["denoise"],
                    stabilize=config["stabilize"],
                    progress_callback=lambda progress: context.report(
                        progress, "Restaurando captura VHS..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except ProcessingCancelled:
                context.check_cancelled()
                raise
            if not success:
                raise RuntimeError("A restauração VHS não foi concluída")
            return config["output"]

        def vhs_complete(output):
            messagebox.showinfo(
                "Restauração VHS concluída", f"Novo vídeo salvo em:\n{output}"
            )

        self._start_ui_job("Restauração de VHS", vhs_task, vhs_complete)

    def open_model_registry(self):
        ModelRegistryDialog(
            self.root, self.model_registry, self._import_native_model_weight
        )

    def _import_native_model_weight(self, source_path, family):
        def import_task(context):
            try:
                return self.model_registry.import_weight(
                    source_path,
                    self.native_weights_root,
                    family,
                    progress_callback=lambda progress: context.report(
                        progress, "Copiando e verificando peso do modelo..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except Exception:
                context.check_cancelled()
                raise

        def import_complete(record):
            self.refresh_models(silent=True)
            messagebox.showinfo(
                "Modelo adicionado",
                f"Peso: {record.name}\nFamília: {record.family}\n"
                f"Licença: {record.license}\nSHA-256: {record.sha256}",
            )

        self._start_ui_job("Importação de modelo", import_task, import_complete)

    def open_accessibility_dialog(self):
        AccessibilityDialog(
            self.root, self.accessibility_preferences, self._apply_accessibility_preferences
        )

    def _apply_accessibility_preferences(self, preferences):
        self.accessibility_preferences = preferences.normalized()
        self.interface_scale = self.accessibility_preferences.scale
        self.reduced_motion = self.accessibility_preferences.reduced_motion
        self.root.tk.call("tk", "scaling", self._base_tk_scaling * self.interface_scale)
        DarkTheme.apply_accessibility(self.root, self.accessibility_preferences)
        settings = dict(self.project_manager.get_project_settings())
        settings["interface_scale"] = self.interface_scale
        settings["accessibility"] = self.accessibility_preferences.to_dict()
        self.project_manager.update_project_settings(settings)
        self.status_var.set(
            f"Escala da interface alterada para {self.interface_scale * 100:.0f}%"
        )

    def _configure_branch_paths(self):
        project_path = self.project_manager.current_project_path
        worktree = self.workspace.branch_worktree() if self.workspace else project_path
        self.restored_dir = os.path.join(worktree, "restored")
        self.manual_stab_dir = os.path.join(worktree, "stabilized_manual")
        self.auto_stab_dir = os.path.join(worktree, "stabilized_auto")
        self.upscaled_dir = os.path.join(worktree, "upscaled")
        self.masks_dir = os.path.join(worktree, "masks")
        self.auto_masks_dir = os.path.join(worktree, "masks_auto")
        self.selections_dir = os.path.join(worktree, "selections")
        self.clean_plates_dir = os.path.join(worktree, "clean_plates")

    def create_local_branch(self):
        self.version_controller.create_local_branch()

    def checkout_local_branch(self):
        self.version_controller.checkout_local_branch()

    def _on_branch_changed(self):
        self.version_controller.on_branch_changed()

    def show_current_frame_history(self):
        self.version_controller.show_current_frame_history()

    def reset_current_frame_to_original(self):
        self.version_controller.reset_current_frame_to_original()

    def _toggle_var(self, var):
        try:
            var.set(not var.get())
            self.show_current_frame()
        except Exception:
            pass

    def _set_view_mode(self, mode):
        self.view_mode = mode
        self.show_current_frame()

    def back_to_welcome(self):
        try:
            self.root.destroy()
        except Exception:
            pass
        try:
            from gui.screens.welcome_screen import WelcomeScreen
            root = tk.Tk()
            root.title("Benedito Digital")
            root.geometry("1200x800")
            WelcomeScreen(root)
            root.mainloop()
        except Exception as e:
            messagebox.showerror("Erro", f"Não foi possível voltar para o início: {e}")

    def exit_app(self):
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def open_tutorial(self):
        try:
            tutorial_path = os.path.join(self.repo_root, "README_TUTORIAL.md")
            if os.path.exists(tutorial_path):
                os.startfile(tutorial_path)
            else:
                messagebox.showinfo("Tutorial", "Arquivo README_TUTORIAL.md não encontrado.")
        except Exception:
            messagebox.showinfo("Tutorial", "Veja o arquivo README_TUTORIAL.md na pasta do projeto.")

    def _bind_shortcuts(self):
        self.root.bind("<Left>", lambda event: self._navigation_shortcut(event, self.previous_frame))
        self.root.bind("<Right>", lambda event: self._navigation_shortcut(event, self.next_frame))
        self.root.bind("<Up>", lambda event: self._navigation_shortcut(event, self.first_frame))
        self.root.bind("<Down>", lambda event: self._navigation_shortcut(event, self.last_frame))
        self.root.bind("i", lambda e: self._set_range_start())
        self.root.bind("o", lambda e: self._set_range_end())
        self.root.bind("<Control-z>", lambda e: self.undo_action())
        self.root.bind("<Control-y>", lambda e: self.redo_action())
        self.root.bind("<Control-Shift-T>", lambda _event: self.timeline_controller.open_dialog())
        self.root.bind("<Control-Shift-C>", lambda _event: self.collaboration_controller.open_dialog())
        self.root.bind("<Control-Shift-S>", lambda _event: self.color_scopes_controller.open_dialog())
        self.root.bind("<F1>", lambda _event: self.show_help_dialog())

    @staticmethod
    def _navigation_shortcut(event, callback):
        if event.widget.winfo_class() in {"Entry", "TEntry", "Text", "TCombobox", "Spinbox", "TSpinbox"}:
            return None
        callback()
        return "break"

    def setup_ui(self):
        """Setup the main editor interface"""
        DarkTheme.configure_tkinter(self.root)

        main_frame = DarkTheme.create_custom_frame(self.root, 'Dark.TFrame')
        main_frame.pack(fill=tk.BOTH, expand=True)

        self.create_menu()
        self.create_toolbar(main_frame)
        self.create_panels(main_frame)
        self.create_status_bar(main_frame)

    def create_toolbar(self, parent):
        """Create main toolbar"""
        toolbar_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        toolbar_frame.pack(fill=tk.X, pady=(0, 2))

        # Project info
        project_frame = DarkTheme.create_custom_frame(toolbar_frame, 'DarkSecondary.TFrame')
        project_frame.pack(side=tk.LEFT, padx=10, pady=8)

        project_label = tk.Label(
            project_frame,
            text=f"📁 {self.project['name']}",
            font=DarkTheme.FONTS['title'],
            fg=DarkTheme.COLORS['accent_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        project_label.pack(side=tk.LEFT)

        self.tool_buttons = {}

        # Tool buttons removed (menu/side actions now)

        # Playback controls
        playback_frame = DarkTheme.create_custom_frame(toolbar_frame, 'DarkSecondary.TFrame')
        playback_frame.pack(side=tk.RIGHT, padx=10, pady=8)

        self.play_btn = tk.Button(
            playback_frame,
            text="▶️",
            font=('Arial', 12),
            bg=DarkTheme.COLORS['accent_secondary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            width=3,
            cursor='hand2',
            command=self.toggle_playback
        )
        self.play_btn.pack(side=tk.LEFT, padx=2)

        self.time_label = tk.Label(
            playback_frame,
            text="00:00:00 / 00:00:00",
            font=DarkTheme.FONTS['mono'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.time_label.pack(side=tk.LEFT, padx=10)

        undo_btn = tk.Button(
            playback_frame,
            text="⟲",
            font=('Arial', 12),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            width=3,
            cursor='hand2',
            command=self.undo_action
        )
        undo_btn.pack(side=tk.LEFT, padx=2)

        redo_btn = tk.Button(
            playback_frame,
            text="⟳",
            font=('Arial', 12),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            width=3,
            cursor='hand2',
            command=self.redo_action
        )
        redo_btn.pack(side=tk.LEFT, padx=2)

    def create_panels(self, parent):
        """Create main content panels"""
        main_container = DarkTheme.create_custom_frame(parent, 'Dark.TFrame')
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left panel - Media browser
        self.create_left_panel(main_container)

        # Center panel - Main workspace
        self.create_center_panel(main_container)

        # Right panel - Properties
        self.create_right_panel(main_container)

    def create_left_panel(self, parent):
        """Create left media browser panel"""
        left_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 2))
        left_frame.configure(width=310)

        # Panel header
        header_frame = DarkTheme.create_custom_frame(left_frame, 'DarkTertiary.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        header_label = tk.Label(
            header_frame,
            text="📂 Mídia",
            font=DarkTheme.FONTS['subtitle'],
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_tertiary']
        )
        header_label.pack(side=tk.LEFT, padx=10, pady=8)

        self.import_btn = tk.Button(
            header_frame,
            text="+",
            font=('Arial', 12, 'bold'),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            width=3,
            cursor='hand2',
            command=self.import_video
        )
        self.import_btn.pack(side=tk.RIGHT, padx=10, pady=5)

        self.proxy_btn = tk.Button(
            header_frame,
            text="Proxy",
            font=('Arial', 9, 'bold'),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=5,
            cursor='hand2',
            command=self.open_proxy_dialog,
        )
        self.proxy_btn.pack(side=tk.RIGHT, padx=(0, 2), pady=5)

        self.frames_btn = tk.Button(
            header_frame,
            text="Frames",
            font=('Arial', 9, 'bold'),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=5,
            cursor='hand2',
            command=self.show_extraction_options,
        )
        self.frames_btn.pack(side=tk.RIGHT, padx=(0, 2), pady=5)

        # Media list
        media_frame = DarkTheme.create_custom_frame(left_frame, 'DarkSecondary.TFrame')
        media_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        scrollbar = ttk.Scrollbar(
            media_frame,
            orient=tk.VERTICAL,
            style='Dark.Vertical.TScrollbar',
        )
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.media_tree = ttk.Treeview(
            media_frame,
            show="tree",
            selectmode="browse",
            yscrollcommand=scrollbar.set,
            style='Dark.Treeview',
        )
        self.media_tree.column("#0", width=270, minwidth=180, stretch=True)
        self.media_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.media_tree.yview)
        self._media_tree_items = {}
        self._media_video_items = {}
        self.media_tree.bind('<<TreeviewSelect>>', self.on_media_select)
        self.media_tree.bind('<<TreeviewOpen>>', self._on_media_tree_open)

    def create_center_panel(self, parent):
        """Create center main workspace panel"""
        center_frame = DarkTheme.create_custom_frame(parent, 'Dark.TFrame')
        center_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=2)

        self.notebook = ttk.Notebook(center_frame, style='Dark.TNotebook')
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Video player tab
        self.create_video_tab()

        # Frame viewer tab
        self.create_frame_tab()

        # Processing tab
        self.create_processing_tab()

    def create_video_tab(self):
        """Create video player tab"""
        video_frame = DarkTheme.create_custom_frame(self.notebook, 'Dark.TFrame')
        self.notebook.add(video_frame, text="🎬 Referencia")

        helper = tk.Label(
            video_frame,
            text="Player de referencia. A restauracao acontece nos frames.",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_primary']
        )
        helper.pack(anchor=tk.W, padx=10, pady=(10, 0))

        self.video_canvas = tk.Canvas(
            video_frame,
            bg=DarkTheme.COLORS['player_bg'],
            highlightthickness=1,
            highlightbackground=DarkTheme.COLORS['border_light'],
            highlightcolor=DarkTheme.COLORS['accent_primary']
        )
        self.video_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        controls_frame = DarkTheme.create_custom_frame(video_frame, 'DarkSecondary.TFrame')
        controls_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Scale(
            controls_frame,
            from_=0,
            to=100,
            variable=self.progress_var,
            style='Dark.Horizontal.TScale',
            command=self.on_seek
        )
        self.progress_bar.pack(fill=tk.X, padx=10, pady=10)

        audio_toggle = tk.Checkbutton(
            controls_frame,
            text="Reproduzir áudio",
            variable=self.audio_enabled_var,
            command=self._toggle_reference_audio,
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            activeforeground=DarkTheme.COLORS['text_primary'],
        )
        audio_toggle.pack(anchor=tk.W, padx=10, pady=(0, 8))

    def create_frame_tab(self):
        """Create frame viewer tab"""
        frame_frame = DarkTheme.create_custom_frame(self.notebook, 'Dark.TFrame')
        self.notebook.add(frame_frame, text="🖼️ Frames")

        tools_bar = DarkTheme.create_custom_frame(frame_frame, 'DarkSecondary.TFrame')
        tools_bar.pack(fill=tk.X, padx=10, pady=(10, 4))

        self.frame_tools_buttons = {}
        def make_tool(icon, label, tool_id):
            btn = tk.Button(
                tools_bar,
                text=f"{icon}  {label}",
                font=DarkTheme.FONTS['small'],
                bg=DarkTheme.COLORS['bg_tertiary'],
                fg=DarkTheme.COLORS['text_primary'],
                relief=tk.FLAT,
                bd=0,
                padx=10,
                pady=4,
                cursor='hand2',
                command=lambda t=tool_id: self._set_frame_tool(t)
            )
            btn.pack(side=tk.LEFT, padx=4)
            self.frame_tools_buttons[tool_id] = btn
        make_tool("↖", "Selecionar", "select")
        make_tool("▭", "Retângulo", "select_rect")
        make_tool("✧", "Laço", "select_lasso")
        make_tool("✎", "Pincel", "brush")
        make_tool("⌫", "Borracha", "erase")
        make_tool("⧉", "Clone", "clone")
        make_tool("✚", "Healing", "heal")

        tk.Button(
            tools_bar,
            text="Limpar seleção",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor='hand2',
            command=self.clear_current_selection,
        ).pack(side=tk.LEFT, padx=4)

        tk.Button(
            tools_bar,
            text="Seleção → máscara",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['accent_secondary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor='hand2',
            command=self.add_selection_to_manual_mask,
        ).pack(side=tk.LEFT, padx=4)

        auto_dust_button = tk.Menubutton(
            tools_bar,
            text="✦ Auto sujeira ▾",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor='hand2',
        )
        auto_dust_menu = tk.Menu(
            auto_dust_button,
            tearoff=0,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            activebackground=DarkTheme.COLORS['accent_primary'],
            activeforeground=DarkTheme.COLORS['text_inverse'],
        )
        auto_dust_menu.add_command(
            label="Detectar sujeira no frame", command=self.auto_select_dust_action
        )
        auto_dust_menu.add_command(
            label="Corrigir pontos detectados", command=self.repair_auto_dust_current
        )
        auto_dust_menu.add_separator()
        auto_dust_menu.add_command(
            label="Ocultar/mostrar pontos", command=self.toggle_auto_mask_overlay
        )
        auto_dust_menu.add_command(
            label="Limpar detecção do frame", command=self.clear_auto_mask_current
        )
        auto_dust_button.configure(menu=auto_dust_menu)
        auto_dust_button.pack(side=tk.LEFT, padx=4)

        tk.Button(
            tools_bar,
            text="▣ Placa limpa",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=10,
            pady=4,
            cursor='hand2',
            command=self.open_clean_plate_dialog,
        ).pack(side=tk.LEFT, padx=4)

        brush_frame = tk.Frame(tools_bar, bg=DarkTheme.COLORS['bg_secondary'])
        brush_frame.pack(side=tk.RIGHT, padx=6)
        tk.Label(
            brush_frame,
            text="Brush:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(side=tk.LEFT, padx=(0, 6))
        self.brush_size_var = tk.IntVar(value=self.brush_size)
        brush_slider = ttk.Scale(
            brush_frame,
            from_=1,
            to=200,
            orient=tk.HORIZONTAL,
            variable=self.brush_size_var,
            command=lambda v: self._on_brush_size_change(v)
        )
        brush_slider.pack(side=tk.LEFT, padx=(0, 6))
        self.brush_size_label = tk.Label(
            brush_frame,
            text=str(self.brush_size),
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.brush_size_label.pack(side=tk.LEFT)

        self._set_frame_tool(self.selected_tool)

        nav_frame = DarkTheme.create_custom_frame(frame_frame, 'DarkSecondary.TFrame')
        nav_frame.pack(fill=tk.X, padx=10, pady=10)

        nav_buttons = [
            ("⏮️", self.first_frame),
            ("⏪", self.previous_frame),
            ("⏩", self.next_frame),
            ("⏭️", self.last_frame),
        ]

        for btn_text, btn_cmd in nav_buttons:
            btn = tk.Button(
                nav_frame,
                text=btn_text,
                font=('Arial', 12),
                bg=DarkTheme.COLORS['bg_tertiary'],
                fg=DarkTheme.COLORS['text_primary'],
                relief=tk.FLAT,
                bd=0,
                width=4,
                cursor='hand2',
                command=btn_cmd
            )
            btn.pack(side=tk.LEFT, padx=2)

        tk.Button(
            nav_frame,
            text="⧉ Segunda tela",
            command=self.open_detached_frame_viewer,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor='hand2',
        ).pack(side=tk.RIGHT, padx=3)
        tk.Button(
            nav_frame,
            text="⊙ Ajustar",
            command=self.reset_frame_view,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor='hand2',
        ).pack(side=tk.RIGHT, padx=3)

        self.frame_counter = tk.Label(
            nav_frame,
            text="Frame 0 / 0",
            font=DarkTheme.FONTS['mono'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.frame_counter.pack(side=tk.LEFT, padx=10)

        self.unsaved_label = tk.Label(
            nav_frame,
            text="● Não salvo",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['accent_error'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.unsaved_label.pack(side=tk.LEFT, padx=6)
        self.unsaved_label.pack_forget()

        goto_frame = tk.Frame(nav_frame, bg=DarkTheme.COLORS['bg_secondary'])
        goto_frame.pack(side=tk.LEFT, padx=10)
        tk.Label(
            goto_frame,
            text="Ir para:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(side=tk.LEFT)
        self.goto_entry = tk.Entry(goto_frame, width=6)
        self.goto_entry.pack(side=tk.LEFT, padx=(6, 6))
        self.goto_entry.bind("<Return>", lambda e: self.go_to_frame_action())
        tk.Button(
            goto_frame,
            text="Ir",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.go_to_frame_action
        ).pack(side=tk.LEFT)

        frame_actions = [
            ("🗑️", self.delete_frame),
            ("📋", self.duplicate_frame),
            ("🔄", self.renumber_frames),
        ]

        for btn_text, btn_cmd in frame_actions:
            btn = tk.Button(
                nav_frame,
                text=btn_text,
                font=('Arial', 10),
                bg=DarkTheme.COLORS['bg_tertiary'],
                fg=DarkTheme.COLORS['text_primary'],
                relief=tk.FLAT,
                bd=0,
                width=3,
                cursor='hand2',
                command=btn_cmd
            )
            btn.pack(side=tk.RIGHT, padx=2)

        self.frame_canvas = tk.Canvas(
            frame_frame,
            bg=DarkTheme.COLORS['bg_tertiary'],
            highlightthickness=1,
            highlightbackground=DarkTheme.COLORS['border_light'],
            highlightcolor=DarkTheme.COLORS['accent_primary'],
            takefocus=True,
        )
        self.frame_canvas.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.frame_canvas.bind("<ButtonPress-1>", self._on_primary_start)
        self.frame_canvas.bind("<B1-Motion>", self._on_primary_move)
        self.frame_canvas.bind("<ButtonRelease-1>", self._on_primary_end)
        self.frame_canvas.bind("<ButtonPress-3>", self._on_secondary_start)
        self.frame_canvas.bind("<B3-Motion>", self._on_secondary_move)
        self.frame_canvas.bind("<ButtonRelease-3>", self._on_secondary_end)
        self.frame_canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.frame_canvas.bind(
            "<Configure>", lambda _event: self._schedule_frame_redraw(80)
        )

        self.frame_bottom_panel = tk.Frame(
            frame_frame, bg=DarkTheme.COLORS['bg_primary']
        )
        self.frame_bottom_panel.pack(fill=tk.X)

        self.selection_status_var = tk.StringVar(
            value="Seleção: nenhuma — escolha Retângulo ou Laço"
        )
        tk.Label(
            self.frame_bottom_panel,
            textvariable=self.selection_status_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_primary'],
        ).pack(anchor=tk.W, padx=12, pady=(0, 6))

        annotation_bar = tk.Frame(
            self.frame_bottom_panel, bg=DarkTheme.COLORS['bg_secondary']
        )
        annotation_bar.pack(fill=tk.X, padx=10, pady=(0, 8))
        tk.Label(
            annotation_bar,
            text="Estado do frame:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
        ).pack(side=tk.LEFT, padx=(8, 6), pady=6)
        self.frame_status_var = tk.StringVar(value="Sem marcação")
        self.frame_status_combo = ttk.Combobox(
            annotation_bar,
            textvariable=self.frame_status_var,
            values=list(self.FRAME_STATUS_LABELS),
            state="readonly",
            width=24,
            style="Dark.TCombobox",
        )
        self.frame_status_combo.pack(side=tk.LEFT, padx=(0, 6), pady=5)
        tk.Button(
            annotation_bar,
            text="Marcar",
            command=self.mark_current_frame_status,
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            padx=10,
            pady=4,
        ).pack(side=tk.LEFT, padx=3)
        tk.Button(
            annotation_bar,
            text="Analisar danos...",
            command=self.open_damage_analysis,
            bg=DarkTheme.COLORS['accent_secondary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            padx=10,
            pady=4,
        ).pack(side=tk.LEFT, padx=3)
        tk.Button(
            annotation_bar,
            text="← Problema anterior",
            command=lambda: self.go_to_flagged_frame(-1),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=9,
            pady=4,
        ).pack(side=tk.RIGHT, padx=3)
        tk.Button(
            annotation_bar,
            text="Próximo problema →",
            command=lambda: self.go_to_flagged_frame(1),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=9,
            pady=4,
        ).pack(side=tk.RIGHT, padx=3)
        self.frame_bottom_toggle_btn = tk.Button(
            annotation_bar,
            text="⌄ Ocultar miniaturas",
            command=self.toggle_frame_bottom_panel,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=9,
            pady=4,
            cursor='hand2',
        )
        self.frame_bottom_toggle_btn.pack(side=tk.RIGHT, padx=3)
        tk.Button(
            annotation_bar,
            text="🎥 Cenas/câmeras...",
            command=self.open_camera_segments_dialog,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=9,
            pady=4,
        ).pack(side=tk.LEFT, padx=3)

        self.range_summary_var = tk.StringVar(value="Intervalo: todos os frames")
        tk.Label(
            annotation_bar,
            textvariable=self.range_summary_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary'],
        ).pack(side=tk.RIGHT, padx=12)

        self.frame_collapsible_panel = tk.Frame(
            self.frame_bottom_panel, bg=DarkTheme.COLORS['bg_primary']
        )
        self.frame_collapsible_panel.pack(fill=tk.X)

        # Frame navigation slider (timeline)
        self.frame_slider_var = tk.IntVar(value=1)
        self.frame_slider = ttk.Scale(
            self.frame_collapsible_panel,
            from_=1,
            to=1,
            orient=tk.HORIZONTAL,
            variable=self.frame_slider_var,
            command=self.on_frame_slider
        )
        self.frame_slider.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.filmstrip_panel = tk.Frame(
            self.frame_collapsible_panel, bg=DarkTheme.COLORS['bg_primary']
        )
        self.filmstrip_panel.pack(fill=tk.X)

        # Filmstrip thumbnails
        self.filmstrip_canvas = tk.Canvas(
            self.filmstrip_panel,
            bg=DarkTheme.COLORS['bg_secondary'],
            height=110,
            highlightthickness=1,
            highlightbackground=DarkTheme.COLORS['border_light'],
            highlightcolor=DarkTheme.COLORS['accent_primary']
        )
        self.filmstrip_canvas.pack(fill=tk.X, padx=10, pady=(0, 10))
        self.filmstrip_canvas.bind("<Button-1>", self._on_filmstrip_click)
        self.filmstrip_canvas.bind("<MouseWheel>", self._on_filmstrip_scroll)

        self.filmstrip_scroll = tk.Scrollbar(
            self.filmstrip_panel,
            orient=tk.HORIZONTAL,
            command=self.filmstrip_canvas.xview
        )
        self.filmstrip_canvas.configure(xscrollcommand=self.filmstrip_scroll.set)
        self.filmstrip_scroll.pack(fill=tk.X, padx=10, pady=(0, 6))

        # Filmstrip zoom
        self.filmstrip_zoom_var = tk.DoubleVar(value=1.2)
        self.filmstrip_zoom = ttk.Scale(
            self.filmstrip_panel,
            from_=0.7,
            to=2.5,
            orient=tk.HORIZONTAL,
            variable=self.filmstrip_zoom_var,
            command=lambda _value: self._schedule_filmstrip_update()
        )
        self.filmstrip_zoom.pack(fill=tk.X, padx=10, pady=(0, 10))

    def create_processing_tab(self):
        """Create processing tab"""
        proc_frame = DarkTheme.create_custom_frame(self.notebook, 'Dark.TFrame')
        self.notebook.add(proc_frame, text="⚙️ Preparacao")

        tools_frame = DarkTheme.create_custom_frame(proc_frame, 'DarkSecondary.TFrame')
        tools_frame.pack(fill=tk.X, padx=10, pady=10)

        # Frame extraction
        extract_frame = DarkTheme.create_custom_frame(tools_frame, 'DarkTertiary.TFrame')
        extract_frame.pack(fill=tk.X)

        extract_label = tk.Label(
            extract_frame,
            text="📸 Extração de Frames (base para restauracao)",
            font=DarkTheme.FONTS['title'],
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_tertiary']
        )
        extract_label.pack(anchor=tk.W, padx=15, pady=(10, 5))

        extract_controls = DarkTheme.create_custom_frame(extract_frame, 'DarkTertiary.TFrame')
        extract_controls.pack(fill=tk.X, padx=15, pady=(0, 10))

        tk.Label(extract_controls, text="FPS:", font=('Arial', 10),
                fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_tertiary']).pack(side=tk.LEFT, padx=(0, 5))

        self.fps_entry = tk.Entry(extract_controls, font=('Arial', 10),
                                 bg=DarkTheme.COLORS['bg_primary'], fg=DarkTheme.COLORS['text_primary'],
                                 insertbackground=DarkTheme.COLORS['accent_primary'], relief=tk.FLAT, bd=5, width=10)
        self.fps_entry.insert(0, "Original")
        self.fps_entry.pack(side=tk.LEFT, padx=(0, 20))

        self.extract_btn_default_text = "Extrair"
        self.extract_btn = tk.Button(
            extract_controls,
            text=self.extract_btn_default_text,
            font=('Arial', 10, 'bold'),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=15,
            pady=5,
            cursor='hand2',
            command=self.show_extraction_options
        )
        self.extract_btn.pack(side=tk.LEFT)

        help_label = tk.Label(
            extract_frame,
            text="Recomendado: 'Original'. Os frames serão PNG sem perda e podem ocupar bastante espaço.",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_tertiary']
        )
        help_label.pack(anchor=tk.W, padx=15, pady=(0, 8))

        # Progress
        progress_frame = DarkTheme.create_custom_frame(proc_frame, 'DarkSecondary.TFrame')
        progress_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.progress_var_main = tk.DoubleVar()
        self.progress_bar_main = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var_main,
            style='Dark.Horizontal.TProgressbar',
            maximum=100
        )
        self.progress_bar_main.pack(fill=tk.X, padx=15, pady=10)

        self.status_label = tk.Label(
            progress_frame,
            text="Pronto para processamento",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.status_label.pack(pady=(0, 10))

    def create_right_panel(self, parent):
        """Create right properties panel"""
        right_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(2, 0))

        header_frame = DarkTheme.create_custom_frame(right_frame, 'DarkTertiary.TFrame')
        header_frame.pack(fill=tk.X, padx=5, pady=5)

        header_label = tk.Label(
            header_frame,
            text="🔧 Propriedades",
            font=DarkTheme.FONTS['subtitle'],
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_tertiary']
        )
        header_label.pack(side=tk.LEFT, padx=10, pady=8)

        props_canvas = tk.Canvas(
            right_frame,
            bg=DarkTheme.COLORS['bg_secondary'],
            highlightthickness=0,
            bd=0
        )
        props_scroll = tk.Scrollbar(right_frame, orient=tk.VERTICAL, command=props_canvas.yview)
        props_canvas.configure(yscrollcommand=props_scroll.set)
        props_scroll.pack(side=tk.RIGHT, fill=tk.Y, pady=(0, 5))
        props_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        props_frame = DarkTheme.create_custom_frame(props_canvas, 'DarkSecondary.TFrame')
        window_id = props_canvas.create_window((0, 0), window=props_frame, anchor="nw")

        def _on_props_configure(event):
            props_canvas.configure(scrollregion=props_canvas.bbox("all"))
        props_frame.bind("<Configure>", _on_props_configure)

        def _on_canvas_resize(event):
            try:
                props_canvas.itemconfig(window_id, width=event.width)
            except Exception:
                pass
        props_canvas.bind("<Configure>", _on_canvas_resize)

        def _on_props_mousewheel(event):
            try:
                return scroll_canvas_if_within(
                    event, props_canvas, props_frame
                )
            except Exception:
                return None
        props_canvas.bind_all("<MouseWheel>", _on_props_mousewheel)

        self.video_info_label = tk.Label(
            props_frame,
            text="Nenhum vídeo carregado",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.video_info_label.pack(anchor=tk.W, padx=10, pady=10)

        quick_actions = tk.Frame(props_frame, bg=DarkTheme.COLORS['bg_secondary'])
        quick_actions.pack(fill=tk.X, padx=10, pady=(0, 10))
        tk.Button(
            quick_actions,
            text="Undo",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.undo_action
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            quick_actions,
            text="Redo",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.redo_action
        ).pack(side=tk.LEFT, padx=(0, 6))
        tk.Button(
            quick_actions,
            text="Restaurar atual",
            font=('Arial', 9, 'bold'),
            bg=DarkTheme.COLORS['accent_primary'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.restore_current_frame_action
        ).pack(side=tk.LEFT)

        # Restoration section
        rest_header = tk.Label(
            props_frame,
            text="Restauracao Temporal (3 frames)",
            font=DarkTheme.FONTS['subtitle'],
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        rest_header.pack(anchor=tk.W, padx=10, pady=(6, 4))

        self.use_alignment_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            props_frame,
            text="Usar alinhamento (ECC)",
            variable=self.use_alignment_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        # Global presets
        tk.Label(
            props_frame,
            text="Preset Global:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 2))

        self.global_preset_var = tk.StringVar(value="Cinema")
        self.global_preset_combo = ttk.Combobox(
            props_frame,
            textvariable=self.global_preset_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["Conservador", "Cinema", "Nitro"]
        )
        self.global_preset_combo.pack(fill=tk.X, padx=10, pady=(0, 4))
        self.global_preset_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_global_preset())

        self.show_advanced_var = tk.BooleanVar(value=False)
        self.advanced_toggle_btn = tk.Button(
            props_frame,
            text="Mostrar opções avançadas ▾",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self._toggle_advanced
        )
        self.advanced_toggle_btn.pack(anchor=tk.W, padx=10, pady=(4, 6))

        self.advanced_frame = tk.Frame(props_frame, bg=DarkTheme.COLORS['bg_secondary'])

        self.deflicker_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            self.advanced_frame,
            text="Deflicker automatico",
            variable=self.deflicker_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        self.deflicker_strength_var = tk.DoubleVar(value=0.5)
        tk.Label(
            self.advanced_frame,
            text="Forca do deflicker:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(4, 2))
        ttk.Scale(
            self.advanced_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.deflicker_strength_var
        ).pack(fill=tk.X, padx=10)

        self.deflicker_local_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.advanced_frame,
            text="Deflicker local",
            variable=self.deflicker_local_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        self.deflicker_local_strength_var = tk.DoubleVar(value=0.4)
        ttk.Scale(
            self.advanced_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.deflicker_local_strength_var
        ).pack(fill=tk.X, padx=10, pady=(0, 6))

        self.fieldsplit_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.advanced_frame,
            text="FieldSplit (entrelaçado)",
            variable=self.fieldsplit_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        self.register_channels_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.advanced_frame,
            text="Registro de canais (RGB)",
            variable=self.register_channels_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        tk.Label(
            self.advanced_frame,
            text="Dewarp:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 2))
        self.dewarp_strength_var = tk.DoubleVar(value=0.0)
        ttk.Scale(
            self.advanced_frame,
            from_=-1.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.dewarp_strength_var
        ).pack(fill=tk.X, padx=10)

        self.auto_color_balance_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.advanced_frame,
            text="Auto white balance",
            variable=self.auto_color_balance_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        self.auto_contrast_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            self.advanced_frame,
            text="Auto contraste",
            variable=self.auto_contrast_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        tk.Label(
            self.advanced_frame,
            text="De-grain:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 2))
        self.degrain_strength_var = tk.DoubleVar(value=0.0)
        ttk.Scale(
            self.advanced_frame,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            variable=self.degrain_strength_var
        ).pack(fill=tk.X, padx=10)

        tk.Label(
            props_frame,
            text="Perfil:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 2))

        self.profile_var = tk.StringVar(value="Qualidade")
        tk.OptionMenu(
            props_frame,
            self.profile_var,
            "Rapido",
            "Qualidade",
            "Maximo",
            "Manual",
            command=lambda v: self._apply_profile(v)
        ).pack(anchor=tk.W, padx=10, pady=(0, 2))

        self.show_mask_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            props_frame,
            text="Mostrar mascara manual",
            variable=self.show_mask_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, padx=10)

        self.show_auto_mask_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            props_frame,
            text="Mostrar auto-mascara",
            variable=self.show_auto_mask_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, padx=10)

        self.auto_mask_live_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            props_frame,
            text="Auto-mascara dinamica (restaurado)",
            variable=self.auto_mask_live_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, padx=10)

        self.double_pass_var.set(False)
        tk.Checkbutton(
            props_frame,
            text="Dupla passada",
            variable=self.double_pass_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10)

        self.auto_save_restore_var = tk.BooleanVar(value=True)
        tk.Checkbutton(
            props_frame,
            text="Salvar automaticamente ao restaurar",
            variable=self.auto_save_restore_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(2, 4))

        tk.Label(
            props_frame,
            text="Auto-mascara:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(8, 2))

        self.automask_mode_var = tk.StringVar(value="normal")
        tk.OptionMenu(
            props_frame,
            self.automask_mode_var,
            "normal",
            "aggressive"
        ).pack(anchor=tk.W, padx=10)

        tk.Label(
            props_frame,
            text="Modelo ML:",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(6, 2))

        model_names = ["None", "DnCNN (OpenCV)", "DnCNN (PyTorch)", "UNet Dust", "SwinIR (Denoise)", "Restormer (Denoise)"]
        self.model_name_var = tk.StringVar(value="None")
        self.model_menu = tk.OptionMenu(
            props_frame,
            self.model_name_var,
            *model_names
        )
        self.model_menu.config(
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            activebackground=DarkTheme.COLORS['bg_hover'],
            activeforeground=DarkTheme.COLORS['text_primary'],
            highlightthickness=0,
            bd=0,
            font=DarkTheme.FONTS['body']
        )
        self.model_menu.pack(anchor=tk.W, padx=10)

        self.model_status_var = tk.StringVar(value="")
        tk.Label(
            props_frame,
            textvariable=self.model_status_var,
            font=('Trebuchet MS', 8),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(2, 4))

        try:
            display_root = os.path.relpath(self.model_roots[0], self.repo_root)
        except Exception:
            display_root = self.model_roots[0] if self.model_roots else "models"
        tk.Label(
            props_frame,
            text=f"Modelos: {display_root}",
            font=('Trebuchet MS', 8),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, padx=10, pady=(0, 4))

        weights_frame = tk.Frame(props_frame, bg=DarkTheme.COLORS['bg_secondary'])
        weights_frame.pack(fill=tk.X, padx=10, pady=(6, 6))

        self.unet_weights_var = tk.StringVar(value="")
        tk.Button(
            weights_frame,
            text="Selecionar UNet weights",
            font=('Arial', 8),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.select_unet_weights
        ).pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            weights_frame,
            textvariable=self.unet_weights_var,
            font=('Arial', 8),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W)

        self.dncnn_weights_var = tk.StringVar(value="")
        tk.Button(
            weights_frame,
            text="Selecionar DnCNN weights",
            font=('Arial', 8),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.select_dncnn_weights
        ).pack(fill=tk.X, pady=(6, 4))
        tk.Label(
            weights_frame,
            textvariable=self.dncnn_weights_var,
            font=('Arial', 8),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W)

        tk.Button(
            weights_frame,
            text="Baixar DnCNN (KAIR)",
            font=('Arial', 8),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.open_dncnn_kair
        ).pack(fill=tk.X, pady=(4, 4))

        self.dncnn_choice_var = tk.StringVar(value="Auto (melhor)")
        tk.Label(
            weights_frame,
            text="DnCNN pesos:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(2, 0))
        self.dncnn_choice_combo = ttk.Combobox(
            weights_frame,
            textvariable=self.dncnn_choice_var,
            state="readonly",
            style='Dark.TCombobox'
        )
        self.dncnn_choice_combo.pack(fill=tk.X, pady=(2, 4))
        self.dncnn_choice_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_dncnn_choice())

        self.swinir_choice_var = tk.StringVar(value="Auto (melhor)")
        tk.Label(
            weights_frame,
            text="SwinIR pesos:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(2, 0))
        self.swinir_choice_combo = ttk.Combobox(
            weights_frame,
            textvariable=self.swinir_choice_var,
            state="readonly",
            style='Dark.TCombobox'
        )
        self.swinir_choice_combo.pack(fill=tk.X, pady=(2, 4))
        self.swinir_choice_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_swinir_choice())

        self.restormer_choice_var = tk.StringVar(value="Auto (melhor)")
        tk.Label(
            weights_frame,
            text="Restormer pesos:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(2, 0))
        self.restormer_choice_combo = ttk.Combobox(
            weights_frame,
            textvariable=self.restormer_choice_var,
            state="readonly",
            style='Dark.TCombobox'
        )
        self.restormer_choice_combo.pack(fill=tk.X, pady=(2, 6))
        self.restormer_choice_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_restormer_choice())

        tk.Label(
            weights_frame,
            text="Adicionar peso custom:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(6, 0))

        self.custom_weight_type_var = tk.StringVar(value="SwinIR")
        self.custom_weight_type_combo = ttk.Combobox(
            weights_frame,
            textvariable=self.custom_weight_type_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["SwinIR", "Restormer", "DnCNN", "RRDB (BSRGAN/ESRGAN)"]
        )
        self.custom_weight_type_combo.pack(fill=tk.X, pady=(2, 4))

        tk.Button(
            weights_frame,
            text="Adicionar peso (.pth)",
            font=('Arial', 8),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.add_custom_weight_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            weights_frame,
            text="Atualizar modelos",
            font=('Arial', 8),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=6,
            pady=3,
            cursor='hand2',
            command=self.refresh_models
        ).pack(fill=tk.X, pady=(6, 4))

        self._sync_model_weight_labels()
        self._update_model_menu()
        self._update_dncnn_list()
        self._update_swinir_list()
        self._update_restormer_list()
        self._update_upscale_list()

        settings_frame = tk.Frame(self.advanced_frame, bg=DarkTheme.COLORS['bg_secondary'])
        settings_frame.pack(fill=tk.X, padx=10, pady=(8, 8))

        tk.Label(settings_frame, text="Inpaint:", font=('Arial', 9),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=0, sticky=tk.W)
        self.inpaint_radius_entry = tk.Entry(settings_frame, width=6)
        self.inpaint_radius_entry.insert(0, "3")
        self.inpaint_radius_entry.grid(row=0, column=1, padx=(6, 12))

        tk.Label(settings_frame, text="Strong:", font=('Arial', 9),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=2, sticky=tk.W)
        self.strong_thresh_entry = tk.Entry(settings_frame, width=6)
        self.strong_thresh_entry.insert(0, "35")
        self.strong_thresh_entry.grid(row=0, column=3, padx=(6, 0))

        self.restore_progress_var = tk.DoubleVar(value=0)
        self.restore_progress = ttk.Progressbar(
            props_frame,
            variable=self.restore_progress_var,
            style='Dark.Horizontal.TProgressbar',
            maximum=100
        )
        self.restore_progress.pack(fill=tk.X, padx=10, pady=(6, 4))

        range_frame = tk.Frame(props_frame, bg=DarkTheme.COLORS['bg_secondary'])
        range_frame.pack(fill=tk.X, padx=10, pady=(4, 6))

        tk.Label(range_frame, text="Intervalo:", font=('Arial', 9),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=0, sticky=tk.W)
        self.range_start_entry = tk.Entry(range_frame, width=6)
        self.range_start_entry.insert(0, "1")
        self.range_start_entry.grid(row=0, column=1, padx=(6, 6))
        self.range_start_entry.bind("<Return>", lambda _event: self._update_range_summary())
        self.range_start_entry.bind("<FocusOut>", lambda _event: self._update_range_summary())
        self.range_end_entry = tk.Entry(range_frame, width=6)
        self.range_end_entry.insert(0, "1")
        self.range_end_entry.grid(row=0, column=2, padx=(0, 6))
        self.range_end_entry.bind("<Return>", lambda _event: self._update_range_summary())
        self.range_end_entry.bind("<FocusOut>", lambda _event: self._update_range_summary())

        tk.Label(
            range_frame,
            text="Atalhos: I=inicio, O=fim",
            font=('Arial', 8),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=(4, 0))

        actions_frame = tk.Frame(props_frame, bg=DarkTheme.COLORS['bg_secondary'])
        actions_frame.pack(fill=tk.X, padx=10, pady=(6, 10))

        self.stabilize_render_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Estabilizar ao renderizar",
            variable=self.stabilize_render_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(0, 6))

        self.stab_overlay_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Overlay p/ estabilizacao manual",
            variable=self.stab_overlay_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, pady=(0, 6))

        stab_frame = tk.Frame(actions_frame, bg=DarkTheme.COLORS['bg_secondary'])
        stab_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(stab_frame, text="Offset X:", font=('Arial', 8),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=0, sticky=tk.W)
        self.stab_offset_x = tk.Entry(stab_frame, width=6)
        self.stab_offset_x.insert(0, "0")
        self.stab_offset_x.grid(row=0, column=1, padx=(4, 10))
        tk.Label(stab_frame, text="Offset Y:", font=('Arial', 8),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=2, sticky=tk.W)
        self.stab_offset_y = tk.Entry(stab_frame, width=6)
        self.stab_offset_y.insert(0, "0")
        self.stab_offset_y.grid(row=0, column=3, padx=(4, 0))

        stab_window_frame = tk.Frame(actions_frame, bg=DarkTheme.COLORS['bg_secondary'])
        stab_window_frame.pack(fill=tk.X, pady=(0, 6))
        tk.Label(stab_window_frame, text="Janela estabilização:", font=('Arial', 8),
                 fg=DarkTheme.COLORS['text_secondary'], bg=DarkTheme.COLORS['bg_secondary']).grid(row=0, column=0, sticky=tk.W)
        self.stab_window_entry = tk.Entry(stab_window_frame, width=6)
        self.stab_window_entry.insert(0, "3")
        self.stab_window_entry.grid(row=0, column=1, padx=(4, 0))

        tk.Button(
            actions_frame,
            text="Aplicar estabilizacao manual",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.apply_manual_stabilization_range
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Estabilizar intervalo (auto)",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.apply_auto_stabilization_range
        ).pack(fill=tk.X, pady=(0, 6))

        self.use_manual_stab_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Usar estabilizacao manual",
            variable=self.use_manual_stab_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, pady=(0, 6))

        self.use_auto_stab_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Usar estabilizacao automatica",
            variable=self.use_auto_stab_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W, pady=(0, 6))

        self.reprocess_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Reprocessar frames existentes",
            variable=self.reprocess_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(0, 6))

        self.render_range_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Renderizar apenas intervalo",
            variable=self.render_range_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Salvar frame (aplicar máscara)",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.save_current_frame_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Restaurar intervalo",
            font=('Arial', 9, 'bold'),
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.restore_range_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Aplicar filtro no intervalo",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.apply_filter_range_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Editor manual (mascara)",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.open_manual_editor_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Atualizar auto-mascara",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.update_auto_mask_current
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Preview (intervalo)",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.preview_from_frames_action
        ).pack(fill=tk.X, pady=(0, 6))

        tk.Button(
            actions_frame,
            text="Renderizar video restaurado",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.render_restored_video_action
        ).pack(fill=tk.X, pady=(0, 6))

        self.view_mode_label = tk.Label(
            actions_frame,
            text="Visualizacao: original",
            font=('Arial', 9),
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.view_mode_label.pack(anchor=tk.W, pady=(4, 0))

        self.compare_var = tk.IntVar(value=50)
        self.compare_slider = ttk.Scale(
            actions_frame,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            variable=self.compare_var,
            command=lambda v: self._on_compare_change()
        )
        self.compare_slider.pack(fill=tk.X, pady=(4, 6))

        tk.Button(
            actions_frame,
            text="Alternar visualizacao",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.toggle_view_mode
        ).pack(fill=tk.X, pady=(4, 0))

        tk.Button(
            actions_frame,
            text="Comparar (split)",
            font=('Arial', 9),
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.enable_compare_view
        ).pack(fill=tk.X, pady=(4, 0))

        # Upscale section
        upscale_header = tk.Label(
            actions_frame,
            text="Upscale (Super-Resolution)",
            font=DarkTheme.FONTS['subtitle'],
            fg=DarkTheme.COLORS['text_primary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        upscale_header.pack(anchor=tk.W, pady=(10, 4))

        self.view_upscale_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Ver upscale (se existir)",
            variable=self.view_upscale_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary'],
            command=self.show_current_frame
        ).pack(anchor=tk.W)

        self.use_upscale_render_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            actions_frame,
            text="Usar upscale no preview/render",
            variable=self.use_upscale_render_var,
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary'],
            selectcolor=DarkTheme.COLORS['bg_tertiary'],
            activebackground=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(0, 4))

        self.upscale_engine_var = tk.StringVar(value="RRDB")
        self.upscale_engine_combo = ttk.Combobox(
            actions_frame,
            textvariable=self.upscale_engine_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["RRDB (BSRGAN/ESRGAN)", "SwinIR (SR)"]
        )
        self.upscale_engine_combo.pack(fill=tk.X, pady=(2, 4))
        self.upscale_engine_combo.bind("<<ComboboxSelected>>", lambda e: self._update_upscale_list())

        self.upscale_model_var = tk.StringVar(value="Auto")
        self.upscale_combo = ttk.Combobox(
            actions_frame,
            textvariable=self.upscale_model_var,
            state="readonly",
            style='Dark.TCombobox'
        )
        self.upscale_combo.pack(fill=tk.X, pady=(2, 4))
        self.upscale_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_selected_upscale())

        self.upscale_info_var = tk.StringVar(value="Escala: x4")
        tk.Label(
            actions_frame,
            textvariable=self.upscale_info_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(anchor=tk.W, pady=(0, 4))

        self.upscale_scale_var = tk.StringVar(value="Auto")
        self.upscale_scale_combo = ttk.Combobox(
            actions_frame,
            textvariable=self.upscale_scale_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["Auto", "x2", "x4"]
        )
        self.upscale_scale_combo.pack(fill=tk.X, pady=(2, 4))
        self.upscale_scale_combo.bind("<<ComboboxSelected>>", lambda e: self._update_upscale_list())

        self.upscale_quality_var = tk.StringVar(value="Qualidade")
        self.upscale_quality_combo = ttk.Combobox(
            actions_frame,
            textvariable=self.upscale_quality_var,
            state="readonly",
            style='Dark.TCombobox',
            values=["Rapido", "Qualidade", "Maximo"]
        )
        self.upscale_quality_combo.pack(fill=tk.X, pady=(2, 4))
        self.upscale_quality_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_upscale_quality())

        tile_frame = tk.Frame(actions_frame, bg=DarkTheme.COLORS['bg_secondary'])
        tile_frame.pack(fill=tk.X, pady=(0, 4))
        tk.Label(
            tile_frame,
            text="Tile:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(side=tk.LEFT)
        self.upscale_tile_var = tk.IntVar(value=256)
        tk.Entry(
            tile_frame,
            textvariable=self.upscale_tile_var,
            width=6,
            bg=DarkTheme.COLORS['bg_primary'],
            fg=DarkTheme.COLORS['text_primary'],
            insertbackground=DarkTheme.COLORS['accent_primary'],
            relief=tk.FLAT,
            bd=5
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Label(
            tile_frame,
            text="Overlap:",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        ).pack(side=tk.LEFT, padx=(10, 0))
        self.upscale_overlap_var = tk.IntVar(value=24)
        tk.Entry(
            tile_frame,
            textvariable=self.upscale_overlap_var,
            width=6,
            bg=DarkTheme.COLORS['bg_primary'],
            fg=DarkTheme.COLORS['text_primary'],
            insertbackground=DarkTheme.COLORS['accent_primary'],
            relief=tk.FLAT,
            bd=5
        ).pack(side=tk.LEFT, padx=(6, 0))

        tk.Button(
            actions_frame,
            text="Upscale frame atual",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.upscale_current_frame_action
        ).pack(fill=tk.X, pady=(2, 2))

        tk.Button(
            actions_frame,
            text="Upscale intervalo",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            padx=8,
            pady=4,
            cursor='hand2',
            command=self.upscale_range_action
        ).pack(fill=tk.X, pady=(0, 2))

        # Apply preset defaults after upscale controls exist
        self._apply_upscale_quality()
        self._apply_global_preset()

    def create_status_bar(self, parent):
        """Create status bar"""
        status_frame = DarkTheme.create_custom_frame(parent, 'DarkSecondary.TFrame')
        status_frame.pack(fill=tk.X, side=tk.BOTTOM)

        from core.app_info import get_app_info

        app_info = get_app_info()
        self.status_var = tk.StringVar(value=f"{app_info.name} v{app_info.version} - Pronto")
        status_label = tk.Label(
            status_frame,
            textvariable=self.status_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        status_label.pack(side=tk.LEFT, padx=10, pady=5)

        self.status_anim_var = tk.StringVar(value="")
        self.status_anim_label = tk.Label(
            status_frame,
            textvariable=self.status_anim_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_muted'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.status_anim_label.pack(side=tk.RIGHT, padx=(0, 6), pady=5)

        self.status_percent_var = tk.StringVar(value="0%")
        self.status_percent_label = tk.Label(
            status_frame,
            textvariable=self.status_percent_var,
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['text_secondary'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        self.status_percent_label.pack(side=tk.RIGHT, padx=(0, 6), pady=5)

        self.status_progress = ttk.Progressbar(
            status_frame,
            style='Dark.Horizontal.TProgressbar',
            maximum=100,
            length=140
        )
        self.status_progress.pack(side=tk.RIGHT, padx=(0, 8), pady=6)

        self.cancel_job_btn = tk.Button(
            status_frame,
            text="Cancelar",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['accent_error'],
            fg=DarkTheme.COLORS['text_inverse'],
            relief=tk.FLAT,
            bd=0,
            state=tk.DISABLED,
            command=self._cancel_active_job,
        )
        self.cancel_job_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=4)

        self.show_job_btn = tk.Button(
            status_frame,
            text="Ver tarefa",
            font=DarkTheme.FONTS['small'],
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            bd=0,
            state=tk.DISABLED,
            command=self._show_progress_dialog,
        )
        self.show_job_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=4)

        gpu_status = self.get_gpu_status()
        gpu_label = tk.Label(
            status_frame,
            text=f"🚀 {gpu_status}",
            font=DarkTheme.FONTS['small'],
            fg=DarkTheme.COLORS['accent_success'],
            bg=DarkTheme.COLORS['bg_secondary']
        )
        gpu_label.pack(side=tk.RIGHT, padx=10, pady=5)

        self.status_frame = status_frame
        self.status_label = status_label
        self._bind_status_progress()

    def get_gpu_status(self):
        """Get GPU acceleration status"""
        try:
            import cv2
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                return "CUDA Ativada"
            elif cv2.ocl.haveOpenCL():
                return "OpenCL Ativado"
            else:
                return "CPU Only"
        except:
            return "Verificando..."

    def _bind_status_progress(self):
        try:
            if hasattr(self, "progress_var_main"):
                self.progress_var_main.trace_add("write", lambda *_: self._sync_status_progress(self.progress_var_main))
            if hasattr(self, "restore_progress_var"):
                self.restore_progress_var.trace_add("write", lambda *_: self._sync_status_progress(self.restore_progress_var))
            self._sync_status_progress(self.progress_var_main if hasattr(self, "progress_var_main") else None)
        except Exception:
            pass

    def _sync_status_progress(self, var):
        try:
            if var is None:
                return
            value = float(var.get())
        except Exception:
            return
        try:
            p = max(0.0, min(100.0, value))
            if hasattr(self, "status_progress"):
                self.status_progress["value"] = p
            if hasattr(self, "status_percent_var"):
                self.status_percent_var.set(f"{p:.0f}%")
            if 0 < p < 100:
                self._start_status_animation()
            else:
                self._stop_status_animation()
        except Exception:
            pass

    def _start_status_animation(self):
        if self.reduced_motion:
            return
        if self._status_anim_job:
            return
        self._status_anim_phase = 0
        self._animate_status_dots()

    def _animate_status_dots(self):
        try:
            dots = "." * ((self._status_anim_phase % 3) + 1)
            if hasattr(self, "status_anim_var"):
                self.status_anim_var.set(dots)
            glow_on = (self._status_anim_phase % 2) == 0
            glow_color = DarkTheme.COLORS['accent_primary'] if glow_on else DarkTheme.COLORS['accent_secondary']
            glow_bg = DarkTheme.COLORS['bg_tertiary'] if glow_on else DarkTheme.COLORS['bg_secondary']
            if hasattr(self, "status_percent_label"):
                self.status_percent_label.config(fg=glow_color)
            if hasattr(self, "status_anim_label"):
                self.status_anim_label.config(fg=glow_color)
            if hasattr(self, "status_frame"):
                self.status_frame.config(bg=glow_bg)
            if hasattr(self, "status_label"):
                self.status_label.config(bg=glow_bg)
            self._status_anim_phase += 1
            self._status_anim_job = self.root.after(400, self._animate_status_dots)
        except Exception:
            self._status_anim_job = None

    def _stop_status_animation(self):
        try:
            if self._status_anim_job:
                self.root.after_cancel(self._status_anim_job)
                self._status_anim_job = None
            if hasattr(self, "status_anim_var"):
                self.status_anim_var.set("")
            if hasattr(self, "status_percent_label"):
                self.status_percent_label.config(fg=DarkTheme.COLORS['text_secondary'])
            if hasattr(self, "status_anim_label"):
                self.status_anim_label.config(fg=DarkTheme.COLORS['text_muted'])
            if hasattr(self, "status_frame"):
                self.status_frame.config(bg=DarkTheme.COLORS['bg_secondary'])
            if hasattr(self, "status_label"):
                self.status_label.config(bg=DarkTheme.COLORS['bg_secondary'])
        except Exception:
            pass

    def _start_ui_job(
        self, name, task, on_success=None, on_error=None, on_finished=None
    ):
        if self._active_job_id is not None:
            messagebox.showwarning("Processamento", "Ja existe uma tarefa em andamento.")
            return None

        job = self.job_manager.submit(name, task)
        self._active_job_id = job.id
        self._active_job_callbacks[job.id] = (on_success, on_error, on_finished)
        if self.progress_dialog:
            self.progress_dialog.close()
        self.progress_dialog = TaskProgressDialog(
            self.root, name, self._cancel_active_job
        )
        if hasattr(self, "cancel_job_btn"):
            self.cancel_job_btn.config(state=tk.NORMAL)
        if hasattr(self, "show_job_btn"):
            self.show_job_btn.config(state=tk.NORMAL)
        self.root.after(0, self._poll_active_job)
        return job

    def _show_progress_dialog(self):
        if self.progress_dialog:
            self.progress_dialog.show()

    def _poll_active_job(self):
        job_id = self._active_job_id
        if job_id is None:
            return
        snapshot = self.job_manager.get(job_id)
        self._apply_job_snapshot(snapshot)
        if self._active_job_id == job_id:
            self.root.after(100, self._poll_active_job)

    def _apply_job_snapshot(self, snapshot):
        if snapshot.id != self._active_job_id:
            return
        if self.progress_dialog:
            self.progress_dialog.update(snapshot)
        self.progress_var_main.set(snapshot.progress)
        if hasattr(self, "restore_progress_var"):
            self.restore_progress_var.set(snapshot.progress)
        self.status_var.set(snapshot.message or snapshot.name)
        terminal_states = {JobState.COMPLETED, JobState.FAILED, JobState.CANCELLED}
        if snapshot.state not in terminal_states:
            return

        success_callback, error_callback, finished_callback = self._active_job_callbacks.pop(
            snapshot.id, (None, None, None)
        )
        self._active_job_id = None
        if hasattr(self, "cancel_job_btn"):
            self.cancel_job_btn.config(state=tk.DISABLED)
        if finished_callback:
            finished_callback()

        if snapshot.state == JobState.COMPLETED:
            self.status_var.set(f"{snapshot.name} concluida")
            if success_callback:
                success_callback(snapshot.result)
        elif snapshot.state == JobState.CANCELLED:
            self.status_var.set(f"{snapshot.name} cancelada")
        else:
            self.status_var.set(f"Erro em {snapshot.name}")
            if error_callback:
                error_callback(snapshot.error)
            else:
                messagebox.showerror("Erro", snapshot.error or "Falha no processamento.")

    def _cancel_active_job(self):
        if self._active_job_id and self.job_manager.cancel(self._active_job_id):
            self.status_var.set("Cancelando tarefa...")
            if hasattr(self, "cancel_job_btn"):
                self.cancel_job_btn.config(state=tk.DISABLED)

    # Tool methods
    def select_tool(self, tool_id):
        self.selected_tool = tool_id
        for tid, btn in self.tool_buttons.items():
            if tid == tool_id:
                btn.configure(bg=DarkTheme.COLORS['accent_primary'], fg=DarkTheme.COLORS['text_inverse'])
            else:
                btn.configure(bg=DarkTheme.COLORS['bg_tertiary'], fg=DarkTheme.COLORS['text_primary'])

    def cut_tool(self, tool_id):
        self.select_tool(tool_id)
        self.status_var.set("Ferramenta de corte selecionada")

    def extract_tool(self, tool_id):
        self.select_tool(tool_id)
        self.status_var.set("Ferramenta de extração selecionada")

    def _go_to_frames(self):
        try:
            self.notebook.select(1)
        except Exception:
            pass

    def show_help_dialog(self):
        messagebox.showinfo(
            "Ajuda",
            "Fluxo recomendado:\n"
            "1) Importar video e extrair frames\n"
            "2) Editar frames e mascaras\n"
            "3) Restaurar intervalo (ou aplicar filtro)\n"
            "4) Renderizar video restaurado\n\n"
            "Atalhos: Left/Right = frame anterior/proximo, I/O = marcar intervalo.\n"
            "Ctrl+Scroll = zoom no ponto do cursor; botão direito + arrasto = mover frame.\n"
            "Scroll = tamanho do brush; miniaturas = clique para navegar.\n"
            "Use Ocultar painel inferior para ampliar a área ou Segunda tela para outro monitor."
        )

    # Media management
    def load_project_videos(self):
        try:
            videos = self.project_manager.get_project_videos()
            for item in self.media_tree.get_children(""):
                self.media_tree.delete(item)
            self._media_tree_items.clear()
            self._media_video_items.clear()
            for video in videos:
                video_item = self.media_tree.insert(
                    "", tk.END, text=f"🎬 {video}", open=False
                )
                self._media_tree_items[video_item] = {
                    "kind": "video",
                    "video": video,
                }
                self._media_video_items[video] = video_item

                proxy_path = (
                    self.workspace.get_proxy_path(video) if self.workspace else None
                )
                proxy_text = (
                    f"⚡ Proxy: {proxy_path.name}"
                    if proxy_path
                    else "◇ Proxy ainda não criado"
                )
                proxy_item = self.media_tree.insert(
                    video_item, tk.END, text=proxy_text
                )
                self._media_tree_items[proxy_item] = {
                    "kind": "proxy",
                    "video": video,
                }

                frames_dir = self.project_manager.get_frames_dir(video)
                pages = paginate_frame_files(frames_dir, page_size=100)
                frame_count = sum(len(page.files) for page in pages)
                frames_item = self.media_tree.insert(
                    video_item,
                    tk.END,
                    text=f"🖼 Frames ({frame_count})",
                    open=False,
                )
                self._media_tree_items[frames_item] = {
                    "kind": "frames",
                    "video": video,
                }
                if not pages:
                    extract_item = self.media_tree.insert(
                        frames_item,
                        tk.END,
                        text="＋ Extrair frames sem perda...",
                    )
                    self._media_tree_items[extract_item] = {
                        "kind": "extract",
                        "video": video,
                    }
                    continue
                for page in pages:
                    page_item = self.media_tree.insert(
                        frames_item,
                        tk.END,
                        text=(
                            f"Página {page.number}: "
                            f"frames {page.start_index + 1}–{page.end_index + 1}"
                        ),
                    )
                    self._media_tree_items[page_item] = {
                        "kind": "page",
                        "video": video,
                        "page": page,
                        "loaded": False,
                    }
                    self.media_tree.insert(page_item, tk.END, text="Carregar página...")
        except Exception as e:
            self.logger.exception("Error loading media tree")
            self.status_var.set(f"Não foi possível atualizar a árvore de mídia: {e}")

    def _on_media_tree_open(self, _event=None):
        item = self.media_tree.focus()
        metadata = self._media_tree_items.get(item, {})
        if metadata.get("kind") != "page" or metadata.get("loaded"):
            return
        for child in self.media_tree.get_children(item):
            self.media_tree.delete(child)
        page = metadata["page"]
        for offset, filename in enumerate(page.files):
            frame_item = self.media_tree.insert(item, tk.END, text=filename)
            self._media_tree_items[frame_item] = {
                "kind": "frame",
                "video": metadata["video"],
                "filename": filename,
                "index": page.start_index + offset,
            }
        metadata["loaded"] = True

    def _selected_media_video(self):
        selection = self.media_tree.selection()
        if not selection:
            return None
        return self._media_tree_items.get(selection[0], {}).get("video")

    def select_media_video(self, video_name):
        item = self._media_video_items.get(video_name)
        if not item:
            return False
        self.media_tree.item(item, open=True)
        self.media_tree.selection_set(item)
        self.media_tree.focus(item)
        self.media_tree.see(item)
        return True

    def _activate_video_frames(self, video_name):
        frames_dir = self.project_manager.get_frames_dir(video_name)
        self.frame_manager.set_frames_dir(frames_dir)
        if self.workspace is not None:
            self.workspace.active_video_name = video_name
        self.total_frames = self.frame_manager.get_frame_count()
        self.current_frame = self.frame_manager.current_frame_index

    def on_media_select(self, _event=None):
        selection = self.media_tree.selection()
        if not selection:
            return
        metadata = self._media_tree_items.get(selection[0], {})
        video_name = metadata.get("video")
        kind = metadata.get("kind")
        if not video_name or kind in {"frames", "page"}:
            return
        if kind == "extract":
            if self.current_video != video_name:
                self.load_video(video_name)
            self.root.after_idle(self.show_extraction_options)
            return
        if kind == "frame":
            if self.current_video != video_name:
                self.load_video(video_name)
            else:
                self._activate_video_frames(video_name)
            try:
                frame_index = self.frame_manager.frames.index(metadata["filename"])
            except ValueError:
                frame_index = metadata["index"]
            self.frame_manager.current_frame_index = frame_index
            self.current_frame = frame_index
            self.notebook.select(1)
            self.show_current_frame()
            self.update_frame_counter()
            return
        if self.current_video == video_name and self.video_player.is_loaded():
            return
        self.load_video(video_name)

    def import_video(self):
        file_path = filedialog.askopenfilename(
            title="Selecione um vídeo",
            filetypes=[
                ("Arquivos de vídeo", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv"),
                ("Todos os arquivos", "*.*"),
            ],
        )

        if not file_path:
            return

        ImportModeDialog(
            self.root,
            file_path,
            lambda selection: self._analyze_video_for_import(file_path, selection),
        )

    def _analyze_video_for_import(self, file_path, selection):
        self.import_btn.config(state=tk.DISABLED)

        def analyze_task(context):
            context.report(10, "Lendo duração, resolução e codec...")
            info = self.video_processor.get_video_info(file_path)
            context.check_cancelled()
            info["file_size"] = os.path.getsize(file_path)
            if selection.is_segment:
                context.report(45, "Verificando os canais de áudio...")
                info["audio_analysis"] = self.video_processor.analyze_audio_balance(
                    file_path,
                    selection.start_time,
                    (selection.end_time or selection.start_time)
                    - selection.start_time,
                )
                context.check_cancelled()
            context.report(100, "Análise concluída")
            return info

        def analyze_complete(video_info):
            ImportVideoDialog(
                self.root,
                file_path,
                video_info,
                self.project_manager.get_originals_dir(),
                selection,
                self._start_video_import,
            )

        self._start_ui_job(
            "Analisando mídia",
            analyze_task,
            analyze_complete,
            lambda error: messagebox.showerror(
                "Erro", f"Não foi possível analisar o vídeo: {error}"
            ),
            lambda: self.import_btn.config(state=tk.NORMAL),
        )

    def _start_video_import(self, import_plan):
        self.import_btn.config(state=tk.DISABLED)

        def import_task(context):
            message = (
                "Criando trecho lossless e verificando..."
                if import_plan.is_segment
                else "Importando e verificando filme inteiro..."
            )
            success = self.project_manager.add_video_to_project(
                str(import_plan.source_path),
                video_name=import_plan.destination_name,
                progress_callback=lambda progress: context.report(progress, message),
                cancel_callback=lambda: context.cancellation_requested,
                import_plan=import_plan,
                video_processor=self.video_processor,
            )
            if not success:
                context.check_cancelled()
                raise RuntimeError(
                    self.project_manager.last_import_error or "Falha ao importar vídeo"
                )
            return self.project_manager.last_imported_video_name

        def import_complete(video_name):
            self.load_project_videos()
            self.select_media_video(video_name)
            self.load_video(video_name)
            self.status_var.set("Vídeo importado e verificado com sucesso!")
            self.open_proxy_dialog(video_name, offer_extraction=True)

        job = self._start_ui_job(
            "Importação de trecho" if import_plan.is_segment else "Importação completa",
            import_task,
            import_complete,
            lambda error: messagebox.showerror("Erro ao importar", error),
            lambda: self.import_btn.config(state=tk.NORMAL),
        )
        if job is None:
            self.import_btn.config(state=tk.NORMAL)

    def load_video(self, video_name):
        try:
            if self.is_playing:
                self.video_player.stop_playback()
                self._finish_playback_ui()
            original_path = os.path.join(
                self.project_manager.get_originals_dir(), video_name
            )
            proxy_path = self.workspace.get_proxy_path(video_name) if self.workspace else None
            video_path = str(proxy_path) if proxy_path else original_path

            if self.video_player.load_video(video_path):
                self.current_video = video_name
                self.current_video_path = original_path
                self._activate_video_frames(video_name)
                playback_label = "proxy leve" if proxy_path else "original"
                self.status_var.set(
                    f"Vídeo carregado: {video_name} — reprodução pelo {playback_label}"
                )

                video_info = self.video_player.get_video_info()
                info_text = f"Resolução: {video_info.get('width', 0)}x{video_info.get('height', 0)}\n"
                info_text += f"FPS: {video_info.get('fps', 0):.2f}\n"
                info_text += f"Duração: {video_info.get('duration', 0):.2f}s\n"
                info_text += f"GPU: {video_info.get('gpu_accelerated', False)}\n"
                info_text += f"Reprodução: {playback_label}"

                self.video_info_label.config(text=info_text)
                self.show_video_frame(0)
                self.video_player.seek(0)
                self.progress_var.set(0)
                self.time_label.config(
                    text=f"00:00:00 / {self.format_time(video_info.get('duration', 0))}"
                )
                self.update_frame_counter()
            else:
                messagebox.showerror("Erro", "Falha ao carregar vídeo.")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao carregar vídeo: {str(e)}")

    def open_proxy_dialog(self, video_name=None, offer_extraction=False):
        target_video = video_name or self.current_video
        if not target_video:
            target_video = self._selected_media_video()
        if not target_video:
            messagebox.showinfo(
                "Escolha um vídeo", "Selecione um vídeo na lista para criar o proxy."
            )
            return
        original_path = os.path.join(
            self.project_manager.get_originals_dir(), target_video
        )
        if not os.path.exists(original_path):
            messagebox.showerror("Proxy", "O material original não foi encontrado.")
            return
        video_info = self.video_processor.get_video_info(original_path)
        ProxyDialog(
            self.root,
            video_info,
            lambda width: self._start_proxy_creation(
                target_video,
                original_path,
                width,
                offer_extraction=offer_extraction,
            ),
        )

    def _start_proxy_creation(
        self, video_name, original_path, width, offer_extraction=False
    ):
        stem = os.path.splitext(video_name)[0]
        output_path = os.path.join(
            str(self.workspace.proxies_dir), f"{stem}_proxy_{width}.mp4"
        )

        def proxy_task(context):
            try:
                success = self.video_processor.create_proxy(
                    original_path,
                    output_path,
                    max_width=width,
                    progress_callback=lambda progress: context.report(
                        progress, "Criando proxy para navegação leve..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except ProcessingCancelled:
                context.check_cancelled()
                raise
            if not success:
                raise RuntimeError("Não foi possível criar o proxy")
            self.workspace.register_proxy(video_name, output_path, width)
            return output_path

        def proxy_complete(path):
            self.status_var.set(f"Proxy pronto: {os.path.basename(path)}")
            self.load_project_videos()
            self.select_media_video(video_name)
            self.load_video(video_name)
            if offer_extraction:
                self._offer_frame_extraction(video_name)

        self._start_ui_job("Criação de proxy", proxy_task, proxy_complete)

    def _offer_frame_extraction(self, video_name):
        frames_dir = Path(self.project_manager.get_frames_dir(video_name))
        if paginate_frame_files(frames_dir, page_size=1):
            return
        should_extract = messagebox.askyesno(
            "Proxy pronto — criar frames?",
            "O proxy de referência está pronto. Os frames para restauração quadro a "
            "quadro são uma etapa separada porque podem ocupar bastante espaço.\n\n"
            "Deseja revisar a estimativa e extrair os frames agora?",
            parent=self.root,
        )
        if should_extract:
            self.root.after(100, self.show_extraction_options)
        else:
            self.status_var.set(
                "Proxy pronto. Use Mídia > Frames > Extrair frames quando desejar."
            )

    def show_video_frame(self, frame_number=None):
        frame = self.video_player.get_frame(frame_number)
        if frame is not None:
            self._render_video_frame(frame)

    def _render_video_frame(self, frame):
        from PIL import Image, ImageTk

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        canvas_width = self.video_canvas.winfo_width()
        canvas_height = self.video_canvas.winfo_height()
        if canvas_width <= 1 or canvas_height <= 1:
            return
        source_height, source_width = frame_rgb.shape[:2]
        scale = min(canvas_width / source_width, canvas_height / source_height)
        target_width = max(1, int(source_width * scale))
        target_height = max(1, int(source_height * scale))
        frame_resized = cv2.resize(frame_rgb, (target_width, target_height))
        image = Image.fromarray(frame_resized)
        photo = ImageTk.PhotoImage(image=image)
        self.video_canvas.delete("all")
        self.video_canvas.create_image(
            canvas_width // 2,
            canvas_height // 2,
            image=photo,
        )
        self.video_canvas.image = photo

    def _queue_video_frame(self, frame):
        with self._playback_ui_lock:
            self._pending_playback_frame = frame

    def _queue_playback_progress(self, progress):
        with self._playback_ui_lock:
            self._pending_playback_progress = progress

    def _queue_playback_finished(self):
        with self._playback_ui_lock:
            self._pending_playback_finished = True

    def _drain_playback_ui(self):
        with self._playback_ui_lock:
            frame = self._pending_playback_frame
            progress = self._pending_playback_progress
            finished = self._pending_playback_finished
            self._pending_playback_frame = None
            self._pending_playback_progress = None
            self._pending_playback_finished = False
        if frame is not None:
            self._render_video_frame(frame)
        if progress is not None:
            self.update_playback_progress(progress)
        if finished:
            self._finish_playback_ui()
        try:
            self._playback_ui_job = self.root.after(16, self._drain_playback_ui)
        except tk.TclError:
            self._playback_ui_job = None

    # Playback controls
    def toggle_playback(self):
        if not self.video_player or not self.video_player.is_loaded():
            messagebox.showinfo(
                "Player de referência",
                "Selecione um vídeo ou proxy na árvore de mídia antes de reproduzir.",
            )
            return

        if not self.is_playing:
            self.is_playing = True
            self.play_btn.config(text="⏸️")
            self._start_play_pulse()
            self.video_player.start_playback(
                callback=self._queue_video_frame,
                progress_callback=self._queue_playback_progress,
                audio_enabled=self.audio_enabled_var.get(),
                finished_callback=self._queue_playback_finished,
            )
        else:
            self.video_player.stop_playback()
            self._finish_playback_ui()

    def _finish_playback_ui(self):
        self.is_playing = False
        self.play_btn.config(text="▶️")
        self._stop_play_pulse()

    def _toggle_reference_audio(self):
        enabled = self.audio_enabled_var.get()
        self.video_player.set_audio_enabled(enabled)
        self.status_var.set(
            "Áudio de referência ativado" if enabled else "Áudio de referência silenciado"
        )

    def _start_play_pulse(self):
        if self.reduced_motion:
            return
        if self._play_pulse_job:
            return
        self._play_pulse_state = False
        self._pulse_play_button()

    def _pulse_play_button(self):
        if not self.is_playing:
            self._stop_play_pulse()
            return
        color = DarkTheme.COLORS['accent_secondary'] if self._play_pulse_state else DarkTheme.COLORS['accent_primary']
        try:
            self.play_btn.config(bg=color)
        except Exception:
            pass
        self._play_pulse_state = not self._play_pulse_state
        self._play_pulse_job = self.root.after(420, self._pulse_play_button)

    def _stop_play_pulse(self):
        if self._play_pulse_job:
            try:
                self.root.after_cancel(self._play_pulse_job)
            except Exception:
                pass
        self._play_pulse_job = None
        try:
            self.play_btn.config(bg=DarkTheme.COLORS['accent_secondary'])
        except Exception:
            pass

    def update_playback_progress(self, progress):
        video_info = self.video_player.get_video_info()
        duration = video_info.get('duration', 0)
        current_time = (progress / 100) * duration

        self.progress_var.set(progress)

        current_str = self.format_time(current_time)
        total_str = self.format_time(duration)
        self.time_label.config(text=f"{current_str} / {total_str}")
        if progress >= 99.9:
            self._finish_playback_ui()

    def on_seek(self, value):
        if not self.video_player or not self.video_player.is_loaded():
            return

        if self.is_playing:
            self.video_player.stop_playback()
            self._finish_playback_ui()

        progress = float(value)
        video_info = self.video_player.get_video_info()
        duration = video_info.get('duration', 0)
        current_time = (progress / 100) * duration

        self.video_player.seek_to_time(current_time)
        self.show_video_frame()
        self.video_player.seek_to_time(current_time)

        current_str = self.format_time(current_time)
        total_str = self.format_time(duration)
        self.time_label.config(text=f"{current_str} / {total_str}")

    def format_time(self, seconds):
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    # Frame navigation
    def first_frame(self):
        if self.frame_manager:
            self.frame_manager.go_to_frame(0)
            self.show_current_frame()
            self.update_frame_counter()

    def previous_frame(self):
        if self.frame_manager and self.frame_manager.previous_frame():
            self.show_current_frame()
            self.update_frame_counter()

    def next_frame(self):
        if self.frame_manager and self.frame_manager.next_frame():
            self.show_current_frame()
            self.update_frame_counter()

    def last_frame(self):
        if self.frame_manager:
            total_frames = self.frame_manager.get_frame_count()
            if total_frames > 0:
                self.frame_manager.go_to_frame(total_frames - 1)
                self.show_current_frame()
                self.update_frame_counter()

    def show_current_frame(self):
        if not self.frame_manager:
            return

        canvas_width = self.frame_canvas.winfo_width()
        canvas_height = self.frame_canvas.winfo_height()

        info = self.frame_manager.get_current_frame_info()
        if not info:
            return

        original_path = info['path']
        restored_path = os.path.join(self.restored_dir, info['filename'])
        if not os.path.exists(restored_path) and self.workspace:
            artifact = self.workspace.latest_frame_artifact(info["index"], "frame")
            if artifact:
                self.workspace.materialize_object(artifact, restored_path)
        if self.use_manual_stab_var.get():
            manual_path = os.path.join(self.manual_stab_dir, info['filename'])
            if os.path.exists(manual_path):
                restored_path = manual_path
        elif self.use_auto_stab_var.get():
            auto_path = os.path.join(self.auto_stab_dir, info['filename'])
            if os.path.exists(auto_path):
                restored_path = auto_path
        if getattr(self, "view_upscale_var", None) is not None and self.view_upscale_var.get():
            up_path = os.path.join(self.upscaled_dir, info['filename'])
            if os.path.exists(up_path):
                restored_path = up_path

        base_img = self._load_image(original_path)
        restored_img = self._load_image(restored_path) if os.path.exists(restored_path) else None

        if base_img is None:
            return

        if self.view_mode == "restored" and restored_img is not None:
            display_img = restored_img
        elif self.view_mode == "compare" and restored_img is not None:
            display_img = self._compose_compare(base_img, restored_img, self.compare_var.get())
        else:
            display_img = base_img

        # Manual stabilization overlay preview
        if self.stab_overlay_var.get():
            try:
                from PIL import Image
                prev_idx = max(0, info['index'] - 1)
                prev_path = os.path.join(self.frame_manager.frames_dir, self.frame_manager.frames[prev_idx])
                prev_img = self._load_image(prev_path)
                if prev_img is not None:
                    dx = int(float(self.stab_offset_x.get() or "0"))
                    dy = int(float(self.stab_offset_y.get() or "0"))
                    shifted = self._apply_offset_pil(display_img, dx, dy)
                    display_img = Image.blend(prev_img, shifted, alpha=0.5)
            except Exception:
                pass

        # Overlay masks if enabled
        if self.show_mask_var.get():
            display_img = self._overlay_mask(display_img, self._load_mask(original_path))
        if self.show_auto_mask_var.get():
            live_var = getattr(self, "auto_mask_live_var", None)
            if live_var and live_var.get():
                source = restored_path if (self.view_mode != "original" and restored_img is not None) else original_path
                self.update_auto_mask_current(source_path=source, force=True, refresh_view=False)
            elif self._load_auto_mask(original_path) is None:
                self.update_auto_mask_current(refresh_view=False)
            display_img = self._overlay_mask(display_img, self._load_auto_mask(original_path), color=(255, 255, 0))
        selection_mask = self._load_selection(original_path)
        if selection_mask is not None and selection_bounds(selection_mask) is not None:
            display_img = self._overlay_mask(
                display_img, selection_mask, color=(40, 210, 255), alpha=0.28
            )

        photo = self._photo_from_pil(display_img, canvas_width, canvas_height)
        if photo:
            self.frame_canvas.delete("all")
            self.frame_canvas.create_image(canvas_width//2, canvas_height//2, image=photo)
            self.frame_canvas.image = photo
            self._draw_retouch_source_marker(info)
        self._current_display_image = display_img
        self._schedule_detached_render()
        self._update_dirty_indicator()

    def _selection_path_for_frame(self, frame_path):
        frame_name = os.path.splitext(os.path.basename(frame_path))[0]
        return os.path.join(self.selections_dir, f"selection_{frame_name}.png")

    def _load_selection(self, frame_path):
        try:
            if (
                self._selection_frame_path == frame_path
                and self._selection_mask is not None
            ):
                return self._selection_mask
            path = self._selection_path_for_frame(frame_path)
            if not os.path.exists(path) and self.workspace and self.frame_manager:
                artifact = self.workspace.latest_frame_artifact(
                    self.frame_manager.current_frame_index, "selection"
                )
                if artifact:
                    self.workspace.materialize_object(artifact, path)
            if os.path.exists(path):
                from PIL import Image

                self._selection_mask = Image.open(path).convert("L")
                self._selection_frame_path = frame_path
                self._update_selection_status(self._selection_mask)
                return self._selection_mask
        except Exception:
            pass
        self._selection_mask = None
        self._selection_frame_path = frame_path
        self._update_selection_status(None)
        return None

    def _load_selection_cv(self, frame_path, frame_index=None):
        path = self._selection_path_for_frame(frame_path)
        if not os.path.exists(path) and self.workspace:
            if frame_index is None and self.frame_manager:
                try:
                    frame_index = self.frame_manager.frames.index(
                        os.path.basename(frame_path)
                    )
                except ValueError:
                    frame_index = None
            if frame_index is not None:
                artifact = self.workspace.latest_frame_artifact(
                    frame_index, "selection"
                )
                if artifact:
                    self.workspace.materialize_object(artifact, path)
        if not os.path.exists(path):
            return None
        mask = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
        if mask is None or not np.any(mask):
            return None
        return mask

    def _save_selection(self, frame_path, mask, operation_type, payload):
        os.makedirs(self.selections_dir, exist_ok=True)
        path = self._selection_path_for_frame(frame_path)
        mask.convert("L").save(path, format="PNG")
        self._selection_mask = mask.convert("L")
        self._selection_frame_path = frame_path
        info = self.frame_manager.get_current_frame_info()
        if self.workspace and info:
            self.workspace.commit_operation(
                operation_type,
                payload=payload,
                frame_number=info["index"],
                artifacts={"selection": path},
            )
        self._update_selection_status(mask)

    def _update_selection_status(self, mask):
        if not hasattr(self, "selection_status_var"):
            return
        bounds = selection_bounds(mask) if mask is not None else None
        if bounds is None:
            self.selection_status_var.set(
                "Seleção: nenhuma — escolha Retângulo ou Laço"
            )
            return
        left, top, right, bottom = bounds
        self.selection_status_var.set(
            f"Seleção ativa: {right - left} × {bottom - top} px — filtros serão limitados a esta área"
        )

    def _on_primary_start(self, event):
        tool = getattr(self, "selected_tool", "brush")
        if tool in {"select_rect", "select_lasso"}:
            self._start_spatial_selection(event, tool)
        elif tool in {"clone", "heal"}:
            self._start_retouch(event, tool)
        elif tool == "erase":
            self._on_erase_start(event)
        elif tool == "brush":
            self._on_paint_start(event)

    def _on_primary_move(self, event):
        tool = getattr(self, "selected_tool", "brush")
        if tool in {"select_rect", "select_lasso"}:
            self._move_spatial_selection(event, tool)
        elif tool in {"clone", "heal"}:
            self._move_retouch(event)
        elif tool == "erase":
            self._on_erase_move(event)
        elif tool == "brush":
            self._on_paint_move(event)

    def _on_primary_end(self, event):
        tool = getattr(self, "selected_tool", "brush")
        if tool in {"select_rect", "select_lasso"}:
            self._finish_spatial_selection(event, tool)
        elif tool in {"clone", "heal"}:
            self._finish_retouch(event)
        elif tool == "erase":
            self._on_erase_end(event)
        elif tool == "brush":
            self._on_paint_end(event)

    def _on_secondary_start(self, event):
        self._secondary_pan_start = (event.x, event.y)
        self._secondary_pan_origin = self.frame_pan
        self._secondary_dragged = False
        try:
            self.frame_canvas.configure(cursor="fleur")
        except tk.TclError:
            pass

    def _on_secondary_move(self, event):
        if self._secondary_pan_start is None:
            return
        delta_x = event.x - self._secondary_pan_start[0]
        delta_y = event.y - self._secondary_pan_start[1]
        if abs(delta_x) + abs(delta_y) < 3 and not self._secondary_dragged:
            return
        self._secondary_dragged = True
        self.frame_pan = (
            self._secondary_pan_origin[0] + delta_x,
            self._secondary_pan_origin[1] + delta_y,
        )
        self._schedule_frame_redraw(16)

    def _on_secondary_end(self, event):
        try:
            self.frame_canvas.configure(cursor="")
        except tk.TclError:
            pass
        if (
            not self._secondary_dragged
            and getattr(self, "selected_tool", "brush") in {"clone", "heal"}
        ):
            self._set_retouch_source(event)
        self._secondary_pan_start = None

    def _start_spatial_selection(self, event, tool):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        size = (info["width"], info["height"])
        image_point = self._canvas_to_image(event.x, event.y, size)
        self._selection_start = image_point
        self._selection_points = [image_point]
        if self._selection_canvas_item:
            self.frame_canvas.delete(self._selection_canvas_item)
        if tool == "select_rect":
            self._selection_canvas_item = self.frame_canvas.create_rectangle(
                event.x,
                event.y,
                event.x,
                event.y,
                outline="#28d7ff",
                width=2,
                dash=(6, 4),
            )
        else:
            self._selection_canvas_item = self.frame_canvas.create_line(
                event.x,
                event.y,
                event.x,
                event.y,
                fill="#28d7ff",
                width=2,
            )

    def _move_spatial_selection(self, event, tool):
        if self._selection_start is None or not self._selection_canvas_item:
            return
        info = self.frame_manager.get_current_frame_info()
        size = (info["width"], info["height"])
        point = self._canvas_to_image(event.x, event.y, size)
        if tool == "select_rect":
            start_canvas_x = self._selection_start[0] * self._view_scale + self._view_offset[0]
            start_canvas_y = self._selection_start[1] * self._view_scale + self._view_offset[1]
            self.frame_canvas.coords(
                self._selection_canvas_item,
                start_canvas_x,
                start_canvas_y,
                event.x,
                event.y,
            )
        else:
            if not self._selection_points or self._selection_points[-1] != point:
                self._selection_points.append(point)
                coords = []
                for image_x, image_y in self._selection_points:
                    coords.extend(
                        [
                            image_x * self._view_scale + self._view_offset[0],
                            image_y * self._view_scale + self._view_offset[1],
                        ]
                    )
                self.frame_canvas.coords(self._selection_canvas_item, *coords)

    def _finish_spatial_selection(self, event, tool):
        if self._selection_start is None:
            return
        info = self.frame_manager.get_current_frame_info()
        if not info:
            return
        size = (info["width"], info["height"])
        end = self._canvas_to_image(event.x, event.y, size)
        if tool == "select_rect":
            mask = rectangle_mask(size, self._selection_start, end)
            payload = {"start": list(self._selection_start), "end": list(end)}
            operation_type = "selection.rectangle"
        else:
            if not self._selection_points or self._selection_points[-1] != end:
                self._selection_points.append(end)
            mask = polygon_mask(size, self._selection_points)
            payload = {"points": [list(point) for point in self._selection_points]}
            operation_type = "selection.lasso"
        if self._selection_canvas_item:
            self.frame_canvas.delete(self._selection_canvas_item)
        self._selection_canvas_item = None
        self._selection_start = None
        self._selection_points = []
        if selection_bounds(mask) is None:
            self.status_var.set("A seleção ficou vazia; tente desenhar uma área maior")
            return
        self._save_selection(info["path"], mask, operation_type, payload)
        self.status_var.set("Seleção salva para o frame atual")
        self.show_current_frame()

    def clear_current_selection(self):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        from PIL import Image

        empty = Image.new("L", (info["width"], info["height"]), 0)
        self._save_selection(
            info["path"], empty, "selection.clear", {"cleared": True}
        )
        self.show_current_frame()
        self.status_var.set("Seleção limpa no frame atual")

    def add_selection_to_manual_mask(self):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        selection = self._load_selection(info["path"])
        if selection is None or selection_bounds(selection) is None:
            messagebox.showinfo(
                "Seleção vazia", "Crie uma seleção retangular ou livre primeiro."
            )
            return
        from PIL import ImageChops

        manual = self._ensure_current_mask(
            info["path"], (info["width"], info["height"])
        )
        self._current_mask = ImageChops.lighter(manual, selection)
        self._save_current_mask()
        self._mark_frame_dirty(info["path"])
        mask_path = self._mask_path_for_frame(info["path"])
        if self.workspace:
            self.workspace.commit_operation(
                "mask.from_selection",
                payload={"selection": "current"},
                frame_number=info["index"],
                artifacts={"mask": mask_path},
            )
        self.show_current_frame()
        self.status_var.set("Seleção adicionada à máscara de restauração")

    def _load_image(self, frame_path):
        try:
            from PIL import Image
            stat = os.stat(frame_path)
            cache_key = (frame_path, stat.st_mtime_ns, stat.st_size)
            cached = self._frame_image_cache.get(cache_key)
            if cached is not None:
                return cached
            with Image.open(frame_path) as source:
                image = source.convert('RGB')
            stale = [key for key in self._frame_image_cache if key[0] == frame_path]
            for key in stale:
                self._frame_image_cache.pop(key, None)
                try:
                    self._frame_image_cache_order.remove(key)
                except ValueError:
                    pass
            self._frame_image_cache[cache_key] = image
            self._frame_image_cache_order.append(cache_key)
            while len(self._frame_image_cache_order) > self._frame_image_cache_max:
                oldest = self._frame_image_cache_order.pop(0)
                self._frame_image_cache.pop(oldest, None)
            return image
        except Exception:
            return None

    def _photo_from_pil(self, image, width, height):
        try:
            from PIL import Image, ImageTk
            img_width, img_height = image.size
            width = max(1, int(width))
            height = max(1, int(height))
            if img_width == 0 or img_height == 0:
                return None
            fit_scale = min(width / img_width, height / img_height)
            scale = max(0.0001, fit_scale * self.frame_zoom)
            self.frame_pan = clamp_view_pan(
                (img_width, img_height),
                (width, height),
                scale,
                self.frame_pan,
            )
            image_center_x = width / 2.0 + self.frame_pan[0]
            image_center_y = height / 2.0 + self.frame_pan[1]
            source_left = img_width / 2.0 - image_center_x / scale
            source_top = img_height / 2.0 - image_center_y / scale
            viewport = image.transform(
                (width, height),
                Image.Transform.AFFINE,
                (1.0 / scale, 0, source_left, 0, 1.0 / scale, source_top),
                resample=Image.Resampling.BICUBIC,
                fillcolor=(35, 23, 51),
            )
            self._view_scale = scale
            self._view_offset = (
                image_center_x - img_width * scale / 2.0,
                image_center_y - img_height * scale / 2.0,
            )
            return ImageTk.PhotoImage(image=viewport)
        except Exception:
            return None

    def _overlay_mask(self, image, mask, color=(255, 0, 0), alpha=0.35):
        if image is None or mask is None:
            return image
        try:
            import numpy as np
            from PIL import Image
            img_np = np.array(image).astype(np.float32)
            mask_np = np.array(mask).astype(np.uint8)
            if mask_np.ndim == 3:
                mask_np = mask_np[:, :, 0]
            m = mask_np > 0
            overlay = np.zeros_like(img_np)
            overlay[..., 0] = color[0]
            overlay[..., 1] = color[1]
            overlay[..., 2] = color[2]
            img_np[m] = img_np[m] * (1 - alpha) + overlay[m] * alpha
            return Image.fromarray(np.clip(img_np, 0, 255).astype(np.uint8))
        except Exception:
            return image

    def _apply_offset_pil(self, image, dx, dy):
        try:
            from PIL import Image
            out = Image.new("RGB", image.size)
            out.paste(image, (dx, dy))
            return out
        except Exception:
            return image

    def _compose_compare(self, original_img, restored_img, ratio):
        try:
            from PIL import Image
            w, h = original_img.size
            restored_img = restored_img.resize((w, h), Image.Resampling.LANCZOS)
            split = int(w * (ratio / 100.0))
            left = original_img.crop((0, 0, split, h))
            right = restored_img.crop((split, 0, w, h))
            out = Image.new("RGB", (w, h))
            out.paste(left, (0, 0))
            out.paste(right, (split, 0))
            try:
                from PIL import ImageDraw
                draw = ImageDraw.Draw(out)
                color = DarkTheme.COLORS['accent_primary']
                draw.line([(split, 0), (split, h)], fill=color, width=2)
            except Exception:
                pass
            return out
        except Exception:
            return original_img

    def _mask_path_for_frame(self, frame_path):
        frame_name = os.path.splitext(os.path.basename(frame_path))[0]
        return os.path.join(self.masks_dir, f"mask_{frame_name}.png")

    def _auto_mask_path_for_frame(self, frame_path):
        frame_name = os.path.splitext(os.path.basename(frame_path))[0]
        return os.path.join(self.auto_masks_dir, f"auto_{frame_name}.png")

    def _legacy_mask_path_for_frame(self, frame_path):
        return os.path.join(self.masks_dir, f"mask_{os.path.basename(frame_path)}")

    def _load_mask(self, frame_path):
        try:
            path = self._mask_path_for_frame(frame_path)
            if not os.path.exists(path) and self.workspace and self.frame_manager:
                artifact = self.workspace.latest_frame_artifact(
                    self.frame_manager.current_frame_index, "mask"
                )
                if artifact:
                    self.workspace.materialize_object(artifact, path)
            legacy_path = self._legacy_mask_path_for_frame(frame_path)
            if not os.path.exists(path) and os.path.exists(legacy_path):
                from PIL import Image
                legacy_mask = Image.open(legacy_path).convert('L')
                os.makedirs(os.path.dirname(path), exist_ok=True)
                legacy_mask.save(path, format="PNG")
            if os.path.exists(path):
                from PIL import Image
                return Image.open(path).convert('L')
        except Exception:
            pass
        return None

    def _load_auto_mask(self, frame_path):
        try:
            path = self._auto_mask_path_for_frame(frame_path)
            if os.path.exists(path):
                from PIL import Image
                return Image.open(path).convert('L')
        except Exception:
            pass
        return None

    def update_auto_mask_current(self, source_path=None, force=True, refresh_view=True):
        if not self.frame_manager:
            return
        info = self.frame_manager.get_current_frame_info()
        if not info:
            return
        try:
            os.makedirs(self.auto_masks_dir, exist_ok=True)
            out_path = self._auto_mask_path_for_frame(info['path'])
            if (not force) and os.path.exists(out_path):
                return
            src = source_path or info['path']
            img = cv2.imread(src, cv2.IMREAD_COLOR)
            if img is None:
                return
            mask = self.restorer.build_automask(img)
            cv2.imwrite(out_path, mask)
            if refresh_view:
                self.show_current_frame()
        except Exception:
            pass

    def _ensure_current_mask(self, frame_path, size):
        if self._current_mask_path != frame_path or self._current_mask is None:
            from PIL import Image
            os.makedirs(self.masks_dir, exist_ok=True)
            mask_path = self._mask_path_for_frame(frame_path)
            if os.path.exists(mask_path):
                mask = Image.open(mask_path).convert('L')
                if mask.size != size:
                    mask = mask.resize(size, Image.Resampling.NEAREST)
            else:
                mask = Image.new("L", size, 0)
            self._current_mask = mask
            self._current_mask_path = frame_path
        return self._current_mask

    def _compose_edge_mask(self, img_gray):
        try:
            edges = cv2.Canny(img_gray, 30, 90)
            edges = cv2.dilate(edges, np.ones((3, 3), np.uint8), iterations=1)
            return edges
        except Exception:
            return None

    def _compose_temporal_diff_mask(self, prev_gray, curr_gray, next_gray):
        try:
            diff_prev = cv2.absdiff(curr_gray, prev_gray)
            diff_next = cv2.absdiff(curr_gray, next_gray)
            diff = cv2.max(diff_prev, diff_next)
            _, mask = cv2.threshold(diff, 18, 255, cv2.THRESH_BINARY)
            mask = cv2.medianBlur(mask, 3)
            return mask
        except Exception:
            return None

    def _compose_auto_dust_mask(self, bgr_img, prev_bgr=None, next_bgr=None):
        try:
            return detect_transient_defects(prev_bgr, bgr_img, next_bgr)
        except Exception:
            return None

    def _save_current_mask(self):
        if self._current_mask is None or self._current_mask_path is None:
            return
        from PIL import Image
        os.makedirs(self.masks_dir, exist_ok=True)
        mask_path = self._mask_path_for_frame(self._current_mask_path)
        self._current_mask.save(mask_path)

    def _mark_frame_dirty(self, frame_path):
        if not frame_path:
            return
        if not hasattr(self, "_dirty_mask_frames"):
            self._dirty_mask_frames = set()
        self._dirty_mask_frames.add(frame_path)
        self._update_dirty_indicator()

    def _mark_frame_clean(self, frame_path):
        if not frame_path:
            return
        if hasattr(self, "_dirty_mask_frames"):
            self._dirty_mask_frames.discard(frame_path)
        self._update_dirty_indicator()

    def _update_dirty_indicator(self):
        if not hasattr(self, "unsaved_label") or not self.frame_manager:
            return
        info = self.frame_manager.get_current_frame_info()
        if not info:
            return
        path = info["path"]
        dirty = hasattr(self, "_dirty_mask_frames") and path in self._dirty_mask_frames
        if dirty:
            self.unsaved_label.pack(side=tk.LEFT, padx=6)
        else:
            self.unsaved_label.pack_forget()

    def _canvas_to_image(self, x, y, image_size):
        img_w, img_h = image_size
        scale = self._view_scale if self._view_scale > 0 else 1.0
        offset_x, offset_y = self._view_offset
        ix = (x - offset_x) / scale
        iy = (y - offset_y) / scale
        ix = max(0, min(img_w - 1, int(ix)))
        iy = max(0, min(img_h - 1, int(iy)))
        return ix, iy

    def _set_retouch_source(self, event):
        self.retouch_controller.set_source(event)

    def _draw_retouch_source_marker(self, info):
        self.retouch_controller.draw_source_marker(info)

    def _start_retouch(self, event, mode):
        self.retouch_controller.start(event, mode)

    def _move_retouch(self, event):
        self.retouch_controller.move(event)

    def _finish_retouch(self, _event):
        self.retouch_controller.finish(_event)

    def _apply_brush(self, x, y, value):
        info = self.frame_manager.get_current_frame_info()
        if not info:
            return
        size = (info['width'], info['height'])
        mask = self._ensure_current_mask(info['path'], size)
        ix, iy = self._canvas_to_image(x, y, size)
        from PIL import ImageDraw
        draw = ImageDraw.Draw(mask)
        r = max(1, int(self.brush_size))
        stroke = getattr(self, "_active_stroke", None)
        previous = stroke["points"][-1] if stroke and stroke["points"] else None
        if previous is not None:
            draw.line(
                (previous[0], previous[1], ix, iy),
                fill=value,
                width=max(1, r * 2),
            )
        draw.ellipse((ix - r, iy - r, ix + r, iy + r), fill=value)
        if stroke is not None:
            point = [ix, iy]
            if not stroke["points"] or stroke["points"][-1] != point:
                stroke["points"].append(point)
        self._current_mask = mask
        canvas_radius = max(2, int(r * max(0.01, self._view_scale)))
        preview_color = "#f43f5e" if value else "#60a5fa"
        previous_canvas = getattr(self, "_brush_preview_canvas_point", None)
        if previous_canvas is not None:
            self.frame_canvas.create_line(
                previous_canvas[0],
                previous_canvas[1],
                x,
                y,
                fill=preview_color,
                width=max(2, canvas_radius * 2),
                capstyle=tk.ROUND,
                tags="brush-preview",
            )
        else:
            self.frame_canvas.create_oval(
                x - canvas_radius,
                y - canvas_radius,
                x + canvas_radius,
                y + canvas_radius,
                fill=preview_color,
                outline="",
                tags="brush-preview",
            )
        self._brush_preview_canvas_point = (x, y)

    def _on_paint_start(self, event):
        if getattr(self, "selected_tool", "brush") == "erase":
            self._on_erase_start(event)
            return
        if getattr(self, "selected_tool", "brush") != "brush":
            return
        self._painting = True
        self.frame_canvas.delete("brush-preview")
        self._brush_preview_canvas_point = None
        self._push_undo_current("mask")
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if info:
            self._mark_frame_dirty(info["path"])
            self._active_stroke = {
                "tool": "brush",
                "radius": int(self.brush_size),
                "value": 255,
                "points": [],
            }
        self._apply_brush(event.x, event.y, 255)

    def _on_paint_move(self, event):
        if getattr(self, "selected_tool", "brush") != "brush":
            return
        if getattr(self, "_painting", False):
            self._apply_brush(event.x, event.y, 255)

    def _on_paint_end(self, event):
        self._painting = False
        self._finish_brush_stroke()

    def _on_erase_start(self, event):
        if getattr(self, "selected_tool", "brush") not in {"brush", "erase"}:
            return
        self._erasing = True
        self.frame_canvas.delete("brush-preview")
        self._brush_preview_canvas_point = None
        self._push_undo_current("mask")
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if info:
            self._mark_frame_dirty(info["path"])
            self._active_stroke = {
                "tool": "erase",
                "radius": int(self.brush_size),
                "value": 0,
                "points": [],
            }
        self._apply_brush(event.x, event.y, 0)

    def _on_erase_move(self, event):
        if getattr(self, "selected_tool", "brush") not in {"brush", "erase"}:
            return
        if getattr(self, "_erasing", False):
            self._apply_brush(event.x, event.y, 0)

    def _on_erase_end(self, event):
        self._erasing = False
        self._finish_brush_stroke()

    def _finish_brush_stroke(self):
        if self._current_mask is not None:
            self._save_current_mask()
        self.frame_canvas.delete("brush-preview")
        self._brush_preview_canvas_point = None
        self.show_current_frame()
        self._commit_active_stroke()

    def _commit_active_stroke(self):
        stroke = getattr(self, "_active_stroke", None)
        self._active_stroke = None
        if not stroke or not stroke["points"] or not self.workspace:
            return
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        mask_path = self._mask_path_for_frame(info["path"])
        if not os.path.exists(mask_path):
            return
        operation_type = "brush.stroke" if stroke["tool"] == "brush" else "mask.erase"
        self.workspace.commit_operation(
            operation_type,
            payload=stroke,
            frame_number=info["index"],
            artifacts={"mask": mask_path},
        )
        self.status_var.set(
            f"Pincelada salva em {self.workspace.active_branch} — frame {info['index'] + 1}"
        )

    def _on_mouse_wheel(self, event):
        ctrl = (event.state & 0x0004) != 0
        delta = 1 if event.delta > 0 else -1
        if ctrl:
            old_zoom = self.frame_zoom
            new_zoom = max(
                0.25,
                min(8.0, old_zoom * (1.12 if delta > 0 else 1 / 1.12)),
            )
            old_scale = max(0.0001, self._view_scale)
            new_scale = old_scale * (new_zoom / old_zoom)
            self.frame_pan = anchored_zoom_pan(
                (self.frame_canvas.winfo_width(), self.frame_canvas.winfo_height()),
                (event.x, event.y),
                old_scale,
                new_scale,
                self.frame_pan,
            )
            self.frame_zoom = new_zoom
            self._schedule_frame_redraw(35)
        else:
            self.brush_size = max(1, min(200, self.brush_size + delta))
            if hasattr(self, "brush_size_var"):
                self.brush_size_var.set(self.brush_size)
            if hasattr(self, "brush_size_label"):
                self.brush_size_label.config(text=str(self.brush_size))
        return "break"

    def _schedule_frame_redraw(self, delay=35):
        if self._zoom_redraw_job:
            try:
                self.root.after_cancel(self._zoom_redraw_job)
            except Exception:
                pass
        self._zoom_redraw_job = self.root.after(delay, self._run_frame_redraw)

    def _run_frame_redraw(self):
        self._zoom_redraw_job = None
        self.show_current_frame()

    def reset_frame_view(self):
        self.frame_zoom = 1.0
        self.frame_pan = (0.0, 0.0)
        self._schedule_frame_redraw(0)

    def toggle_frame_bottom_panel(self):
        if not hasattr(self, "frame_collapsible_panel"):
            return
        if self._frame_bottom_visible:
            self.frame_collapsible_panel.pack_forget()
            self._frame_bottom_visible = False
            self.frame_bottom_toggle_btn.config(text="⌃ Mostrar miniaturas")
            self.status_var.set("Miniaturas ocultas — mais espaço para restauração")
        else:
            self.frame_collapsible_panel.pack(fill=tk.X)
            self._frame_bottom_visible = True
            self.frame_bottom_toggle_btn.config(text="⌄ Ocultar miniaturas")
        self.root.after_idle(self._run_frame_redraw)

    def open_detached_frame_viewer(self):
        if self._detached_viewer is not None:
            try:
                self._detached_viewer.deiconify()
                self._detached_viewer.lift()
                self._detached_viewer.focus_force()
                return
            except tk.TclError:
                self._detached_viewer = None
        window = tk.Toplevel(self.root)
        window.title("Benedito Digital — Frame em segunda tela")
        window.geometry("1100x720")
        window.minsize(520, 360)
        window.configure(bg=DarkTheme.COLORS['bg_primary'])
        window.protocol("WM_DELETE_WINDOW", self._close_detached_frame_viewer)
        window.bind("<F11>", lambda _event: self._toggle_detached_fullscreen())

        header = tk.Frame(window, bg=DarkTheme.COLORS['bg_secondary'])
        header.pack(fill=tk.X)
        tk.Label(
            header,
            text="Visualização duplicada — arraste esta janela para outro monitor",
            bg=DarkTheme.COLORS['bg_secondary'],
            fg=DarkTheme.COLORS['text_secondary'],
            font=DarkTheme.FONTS['small'],
        ).pack(side=tk.LEFT, padx=12, pady=8)
        tk.Button(
            header,
            text="Tela cheia (F11)",
            command=self._toggle_detached_fullscreen,
            bg=DarkTheme.COLORS['bg_tertiary'],
            fg=DarkTheme.COLORS['text_primary'],
            relief=tk.FLAT,
            padx=10,
            pady=4,
        ).pack(side=tk.RIGHT, padx=8, pady=5)
        canvas = tk.Canvas(
            window,
            bg=DarkTheme.COLORS['player_bg'],
            highlightthickness=0,
        )
        canvas.pack(fill=tk.BOTH, expand=True)
        canvas.bind("<Configure>", lambda _event: self._schedule_detached_render())
        self._detached_viewer = window
        self._detached_canvas = canvas
        self._schedule_detached_render(0)

    def _toggle_detached_fullscreen(self):
        if self._detached_viewer is None:
            return
        try:
            current = bool(self._detached_viewer.attributes("-fullscreen"))
            self._detached_viewer.attributes("-fullscreen", not current)
        except tk.TclError:
            pass

    def _close_detached_frame_viewer(self):
        if self._detached_render_job:
            try:
                self.root.after_cancel(self._detached_render_job)
            except Exception:
                pass
        self._detached_render_job = None
        if self._detached_viewer is not None:
            try:
                self._detached_viewer.destroy()
            except tk.TclError:
                pass
        self._detached_viewer = None
        self._detached_canvas = None

    def _schedule_detached_render(self, delay=30):
        if self._detached_viewer is None or self._detached_canvas is None:
            return
        if self._detached_render_job:
            try:
                self.root.after_cancel(self._detached_render_job)
            except Exception:
                pass
        self._detached_render_job = self.root.after(
            delay, self._render_detached_frame
        )

    def _render_detached_frame(self):
        self._detached_render_job = None
        if self._detached_canvas is None or self._current_display_image is None:
            return
        try:
            from PIL import Image, ImageTk

            width = max(1, self._detached_canvas.winfo_width())
            height = max(1, self._detached_canvas.winfo_height())
            image = self._current_display_image.copy()
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(image)
            self._detached_canvas.delete("all")
            self._detached_canvas.create_image(
                width // 2, height // 2, image=photo, anchor=tk.CENTER
            )
            self._detached_canvas.image = photo
            if self.frame_manager:
                info = self.frame_manager.get_current_frame_info()
                if info and self._detached_viewer is not None:
                    self._detached_viewer.title(
                        f"Benedito Digital — Frame {info['index'] + 1} / {info['total']}"
                    )
        except (tk.TclError, OSError):
            pass

    # Undo/Redo
    def _read_bytes(self, path):
        try:
            if path and os.path.exists(path):
                with open(path, "rb") as f:
                    return f.read()
        except Exception:
            return None
        return None

    def _write_bytes(self, path, data):
        try:
            if data is None:
                if path and os.path.exists(path):
                    os.remove(path)
                return
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
        except Exception:
            pass

    def _snapshot_frame(self, frame_info):
        if not frame_info:
            return None
        frame_path = frame_info['path']
        mask_path = self._mask_path_for_frame(frame_path)
        restored_path = os.path.join(self.restored_dir, frame_info['filename'])
        manual_path = os.path.join(self.manual_stab_dir, frame_info['filename'])
        return {
            "frame": frame_info['filename'],
            "index": frame_info.get("index"),
            "mask_path": mask_path,
            "mask_bytes": self._read_bytes(mask_path),
            "restored_path": restored_path,
            "restored_bytes": self._read_bytes(restored_path),
            "manual_path": manual_path,
            "manual_bytes": self._read_bytes(manual_path),
        }

    def _restore_snapshot(self, snap):
        if not snap:
            return
        self._write_bytes(snap.get("mask_path"), snap.get("mask_bytes"))
        self._write_bytes(snap.get("restored_path"), snap.get("restored_bytes"))
        self._write_bytes(snap.get("manual_path"), snap.get("manual_bytes"))

    def _push_undo_entry(self, entry):
        if not entry:
            return
        self.undo_stack.append(entry)
        if len(self.undo_stack) > 20:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def _push_undo_current(self, desc=""):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        snap = self._snapshot_frame(info)
        if snap:
            self._push_undo_entry({"desc": desc or "frame", "items": [snap]})

    def _push_undo_range(self, start, end, desc=""):
        if not self.frame_manager:
            return True
        frames = self.frame_manager.frames
        total = max(0, min(end, len(frames) - 1) - max(0, start) + 1)
        if total > 200:
            messagebox.showwarning("Aviso", "Intervalo muito grande para Undo completo. Continue sem undo.")
            return False
        items = []
        for i in range(max(0, start), min(end, len(frames) - 1) + 1):
            frame_path = os.path.join(self.frame_manager.frames_dir, frames[i])
            info = {"path": frame_path, "filename": frames[i]}
            snap = self._snapshot_frame(info)
            if snap:
                items.append(snap)
        if items:
            self._push_undo_entry({"desc": desc or "range", "items": items})
            return True
        return False

    def undo_action(self):
        if not self.undo_stack:
            self.status_label.config(text="Nada para desfazer")
            return
        entry = self.undo_stack.pop()
        # capture current state for redo
        redo_items = []
        for snap in entry.get("items", []):
            frame_path = os.path.join(self.frame_manager.frames_dir, snap["frame"])
            info = {"path": frame_path, "filename": snap["frame"]}
            current = self._snapshot_frame(info)
            if current:
                redo_items.append(current)
        self.redo_stack.append({"desc": entry.get("desc", "redo"), "items": redo_items})

        for snap in entry.get("items", []):
            self._restore_snapshot(snap)
        self._commit_history_restore("history.undo", entry)
        self.show_current_frame()
        self.status_label.config(text="Undo")

    def redo_action(self):
        if not self.redo_stack:
            self.status_label.config(text="Nada para refazer")
            return
        entry = self.redo_stack.pop()
        # capture current state for undo
        undo_items = []
        for snap in entry.get("items", []):
            frame_path = os.path.join(self.frame_manager.frames_dir, snap["frame"])
            info = {"path": frame_path, "filename": snap["frame"]}
            current = self._snapshot_frame(info)
            if current:
                undo_items.append(current)
        self.undo_stack.append({"desc": entry.get("desc", "undo"), "items": undo_items})

        for snap in entry.get("items", []):
            self._restore_snapshot(snap)
        self._commit_history_restore("history.redo", entry)
        self.show_current_frame()
        self.status_label.config(text="Redo")

    def _commit_history_restore(self, operation_type, entry):
        if not self.workspace or not self.frame_manager:
            return
        for snap in entry.get("items", []):
            frame_index = snap.get("index")
            if frame_index is None:
                try:
                    frame_index = self.frame_manager.frames.index(snap["frame"])
                except (ValueError, KeyError):
                    continue
            artifacts = {}
            cleared = []
            for label, path_key in (
                ("frame", "restored_path"),
                ("mask", "mask_path"),
                ("stabilized", "manual_path"),
            ):
                path = snap.get(path_key)
                if path and os.path.isfile(path):
                    artifacts[label] = path
                else:
                    cleared.append(label)
            self.workspace.commit_operation(
                operation_type,
                payload={
                    "description": entry.get("desc", "frame"),
                    "cleared_artifacts": cleared,
                },
                frame_number=int(frame_index),
                artifacts=artifacts,
            )

    def update_frame_counter(self):
        if self.frame_manager:
            info = self.frame_manager.get_current_frame_info()
            if info:
                self.frame_counter.config(text=f"Frame {info['index'] + 1} / {info['total']}")
                try:
                    self.frame_slider.configure(to=info['total'])
                    self._updating_frame_slider = True
                    self.frame_slider_var.set(info['index'] + 1)
                except Exception:
                    pass
                finally:
                    self._updating_frame_slider = False
                try:
                    if int(self.range_end_entry.get() or "0") <= 1:
                        self.range_end_entry.delete(0, tk.END)
                        self.range_end_entry.insert(0, str(info['total']))
                except Exception:
                    pass
                try:
                    if hasattr(self, "goto_entry"):
                        self.goto_entry.delete(0, tk.END)
                        self.goto_entry.insert(0, str(info['index'] + 1))
                except Exception:
                    pass
                self._sync_current_frame_status(info["index"])
                self._update_range_summary()
                self._update_filmstrip(info['index'])

    def _sync_current_frame_status(self, frame_index):
        if not hasattr(self, "frame_status_var"):
            return
        status = self.workspace.get_frame_status(frame_index) if self.workspace else None
        status_key = status.get("status") if status else "unmarked"
        label = next(
            (
                candidate
                for candidate, value in self.FRAME_STATUS_LABELS.items()
                if value == status_key
            ),
            "Sem marcação",
        )
        self.frame_status_var.set(label)

    def mark_current_frame_status(self):
        if not self.workspace or not self.frame_manager:
            return
        info = self.frame_manager.get_current_frame_info()
        if not info:
            return
        status = self.FRAME_STATUS_LABELS.get(
            self.frame_status_var.get(), "unmarked"
        )
        note = ""
        if status in {"review", "dust", "scratch", "stain", "missing", "perforation"}:
            note = simpledialog.askstring(
                "Observação do frame",
                "Descreva o problema, se desejar:",
                parent=self.root,
            ) or ""
        self.workspace.set_frame_status(info["index"], status, note)
        self.status_var.set(
            f"Frame {info['index'] + 1}: {self.frame_status_var.get()}"
        )
        self._update_filmstrip(info["index"])

    def go_to_flagged_frame(self, direction):
        if not self.workspace or not self.frame_manager:
            return
        statuses = self.workspace.get_frame_statuses()
        flagged = sorted(
            frame_index
            for frame_index, value in statuses.items()
            if value.get("status") not in {"approved", "unmarked"}
        )
        if not flagged:
            messagebox.showinfo(
                "Nenhum problema marcado",
                "Marque frames como Revisar, Poeira, Risco, Mancha, Perfuração ou Ausente.",
            )
            return
        current = self.frame_manager.current_frame_index
        candidates = (
            [index for index in flagged if index > current]
            if direction > 0
            else [index for index in flagged if index < current]
        )
        target = (
            candidates[0]
            if direction > 0 and candidates
            else candidates[-1]
            if direction < 0 and candidates
            else flagged[0]
            if direction > 0
            else flagged[-1]
        )
        if self.frame_manager.go_to_frame(target):
            self.show_current_frame()
            self.update_frame_counter()

    def open_damage_analysis(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showinfo("Análise", "Extraia ou carregue frames primeiro.")
            return
        try:
            start = max(1, int(self.range_start_entry.get()))
            end = min(len(self.frame_manager.frames), int(self.range_end_entry.get()))
        except ValueError:
            start, end = 1, len(self.frame_manager.frames)
        DamageAnalysisDialog(
            self.root,
            start,
            end,
            len(self.frame_manager.frames),
            lambda scope, sensitivity: self._start_damage_analysis(
                scope, sensitivity, start - 1, end - 1
            ),
        )

    def _start_damage_analysis(self, scope, sensitivity, range_start, range_end):
        frames = list(self.frame_manager.frames)
        if scope == "all":
            indices = list(range(len(frames)))
        else:
            indices = list(
                range(max(0, range_start), min(range_end, len(frames) - 1) + 1)
            )

        def analysis_task(context):
            analyzer = FrameDamageAnalyzer(sensitivity)
            results = {}
            flagged = 0
            for position, frame_index in enumerate(indices):
                context.check_cancelled()
                previous_index = max(0, frame_index - 1)
                following_index = min(len(frames) - 1, frame_index + 1)
                current = cv2.imread(
                    os.path.join(self.frame_manager.frames_dir, frames[frame_index]),
                    cv2.IMREAD_COLOR,
                )
                previous = cv2.imread(
                    os.path.join(self.frame_manager.frames_dir, frames[previous_index]),
                    cv2.IMREAD_COLOR,
                )
                following = cv2.imread(
                    os.path.join(self.frame_manager.frames_dir, frames[following_index]),
                    cv2.IMREAD_COLOR,
                )
                if current is None:
                    results[str(frame_index)] = {
                        "status": "missing",
                        "confidence": 1.0,
                        "note": "Arquivo de frame ilegível",
                    }
                    existing = self.workspace.get_frame_status(frame_index) if self.workspace else None
                    if not existing:
                        self.workspace.set_frame_status(
                            frame_index, "missing", "Arquivo de frame ilegível"
                        )
                        flagged += 1
                    context.report(
                        (position + 1) * 100.0 / max(1, len(indices)),
                        f"Analisando danos — {position + 1}/{len(indices)}",
                    )
                    continue
                result = analyzer.analyze(current, previous, following)
                results[str(frame_index)] = result.to_dict()
                existing = self.workspace.get_frame_status(frame_index) if self.workspace else None
                if result.status != "unmarked" and not existing:
                    self.workspace.set_frame_status(
                        frame_index,
                        result.status,
                        f"Análise automática: {result.note} ({result.confidence * 100:.0f}%)",
                    )
                    flagged += 1
                context.report(
                    (position + 1) * 100.0 / max(1, len(indices)),
                    f"Analisando danos — {position + 1}/{len(indices)}",
                )
            report_dir = os.path.join(
                str(self.workspace.branch_worktree()), "analysis"
            )
            os.makedirs(report_dir, exist_ok=True)
            report_path = os.path.join(report_dir, "damage_report.json")
            temporary = report_path + ".tmp"
            with open(temporary, "w", encoding="utf-8") as file_handle:
                json.dump(
                    {
                        "branch": self.workspace.active_branch,
                        "sensitivity": sensitivity,
                        "results": results,
                    },
                    file_handle,
                    ensure_ascii=False,
                    indent=2,
                )
            os.replace(temporary, report_path)
            return {"analyzed": len(indices), "flagged": flagged}

        def analysis_complete(result):
            self._update_filmstrip(self.frame_manager.current_frame_index)
            self._sync_current_frame_status(self.frame_manager.current_frame_index)
            messagebox.showinfo(
                "Análise concluída",
                f"Frames analisados: {result['analyzed']}\n"
                f"Novas marcações para revisão: {result['flagged']}",
            )

        self._start_ui_job("Análise de danos", analysis_task, analysis_complete)

    def _update_range_summary(self):
        if not hasattr(self, "range_summary_var"):
            return
        try:
            start = max(1, int(self.range_start_entry.get()))
            end = max(start, int(self.range_end_entry.get()))
            self.range_summary_var.set(
                f"Intervalo: {start}–{end} ({end - start + 1} frames)"
            )
        except (ValueError, AttributeError):
            self.range_summary_var.set("Intervalo: não definido")

    def _update_filmstrip(self, center_index):
        if not self.frame_manager or not hasattr(self, "filmstrip_canvas"):
            return
        frames = self.frame_manager.frames
        if not frames:
            return
        from PIL import Image, ImageTk

        total = len(frames)
        zoom = self.filmstrip_zoom_var.get() if hasattr(self, "filmstrip_zoom_var") else 1.0
        thumb_h = int(90 * max(0.6, min(2.5, float(zoom))))
        current_info = self.frame_manager.get_current_frame_info()
        if current_info and current_info.get("height"):
            self._filmstrip_aspect_ratio = (
                current_info["width"] / current_info["height"]
            )
        indices = filmstrip_window_indices(total, center_index, limit=11)
        signature = (total, thumb_h, tuple(indices))

        if signature != self._filmstrip_signature:
            self.filmstrip_canvas.delete("all")
            self._filmstrip_images = []
            self._filmstrip_map = {}
            self._filmstrip_positions = {}
            self._filmstrip_indices = []

            self._filmstrip_indices = indices

            x = 10
            for idx in indices:
                path = os.path.join(self.frame_manager.frames_dir, frames[idx])
                try:
                    result = self._get_filmstrip_thumb(path, thumb_h)
                    if not result:
                        continue
                    photo, thumb_w = result
                    item = self.filmstrip_canvas.create_image(x, 5, anchor=tk.NW, image=photo)
                    self._filmstrip_images.append(photo)
                    self._filmstrip_map[item] = idx
                    self._filmstrip_positions[idx] = (x, thumb_w)
                    x += thumb_w + 6
                except Exception:
                    continue

            self.filmstrip_canvas.configure(scrollregion=self.filmstrip_canvas.bbox("all"))
            self._filmstrip_signature = signature

        # highlight nearest
        self.filmstrip_canvas.delete("highlight")
        indices = getattr(self, "_filmstrip_indices", [])
        if indices:
            nearest = min(indices, key=lambda i: abs(i - center_index))
            pos = self._filmstrip_positions.get(nearest)
            if pos:
                x, thumb_w = pos
                self.filmstrip_canvas.create_rectangle(
                    x, 5, x + thumb_w, 5 + thumb_h,
                    outline=DarkTheme.COLORS['accent_primary'],
                    width=2,
                    tags="highlight"
                )
                try:
                    canvas_w = max(1, self.filmstrip_canvas.winfo_width())
                    bbox_all = self.filmstrip_canvas.bbox("all")
                    if bbox_all:
                        total_w = max(1, bbox_all[2])
                        center_x = x + (thumb_w / 2)
                        target = max(0.0, min(1.0, (center_x - canvas_w / 2) / total_w))
                        self.filmstrip_canvas.xview_moveto(target)
                except Exception:
                    pass
        self._draw_timeline_annotations(thumb_h)

    def _schedule_filmstrip_update(self, delay=120):
        if self._filmstrip_update_job:
            try:
                self.root.after_cancel(self._filmstrip_update_job)
            except Exception:
                pass
        self._filmstrip_update_job = self.root.after(
            delay, self._run_filmstrip_update
        )

    def _run_filmstrip_update(self):
        self._filmstrip_update_job = None
        center = self.frame_manager.current_frame_index if self.frame_manager else 0
        self._filmstrip_signature = None
        self._update_filmstrip(center)

    def _draw_timeline_annotations(self, thumb_h):
        self.filmstrip_canvas.delete("annotation")
        indices = getattr(self, "_filmstrip_indices", [])
        if not indices:
            return
        if self.workspace:
            for frame_index, value in self.workspace.get_frame_statuses().items():
                nearest = min(indices, key=lambda index: abs(index - frame_index))
                position = self._filmstrip_positions.get(nearest)
                color = self.FRAME_STATUS_COLORS.get(value.get("status"))
                if not position or not color:
                    continue
                x, thumb_width = position
                marker = self.filmstrip_canvas.create_rectangle(
                    x,
                    5,
                    x + thumb_width,
                    11,
                    fill=color,
                    outline=color,
                    tags="annotation",
                )
                self._filmstrip_map[marker] = frame_index
        try:
            range_markers = (
                (int(self.range_start_entry.get()) - 1, "#22c55e"),
                (int(self.range_end_entry.get()) - 1, "#f43f5e"),
            )
            for frame_index, color in range_markers:
                nearest = min(indices, key=lambda index: abs(index - frame_index))
                position = self._filmstrip_positions.get(nearest)
                if not position:
                    continue
                x, thumb_width = position
                marker = self.filmstrip_canvas.create_line(
                    x + thumb_width / 2,
                    3,
                    x + thumb_width / 2,
                    5 + thumb_h,
                    fill=color,
                    width=3,
                    tags="annotation",
                )
                self._filmstrip_map[marker] = frame_index
        except (ValueError, AttributeError):
            pass

    def _get_filmstrip_cache_dir(self, thumb_h):
        root = getattr(self, "thumb_cache_root", None)
        if not root:
            return None
        cache_dir = os.path.join(root, f"h{thumb_h}")
        try:
            os.makedirs(cache_dir, exist_ok=True)
        except Exception:
            return None
        return cache_dir

    def _get_filmstrip_thumb(self, path, thumb_h):
        if not os.path.exists(path):
            return None
        try:
            src_mtime = os.path.getmtime(path)
        except Exception:
            src_mtime = 0

        cache_key = (path, thumb_h, src_mtime)
        cached = self._thumb_cache.get(cache_key) if hasattr(self, "_thumb_cache") else None
        if cached:
            return cached

        cache_dir = self._get_filmstrip_cache_dir(thumb_h)
        cache_path = None
        if cache_dir:
            source_id = hashlib.sha1(
                os.path.abspath(path).encode("utf-8", errors="surrogatepass")
            ).hexdigest()[:12]
            cache_path = os.path.join(
                cache_dir, f"{source_id}-{os.path.basename(path)}.jpg"
            )

        try:
            from PIL import Image, ImageTk
            img = None
            if cache_path and os.path.exists(cache_path):
                try:
                    if os.path.getmtime(cache_path) >= src_mtime:
                        img = Image.open(cache_path).convert("RGB")
                except Exception:
                    img = None
            if img is None:
                self._queue_filmstrip_thumbnail(
                    path, thumb_h, src_mtime, cache_path
                )
                aspect = getattr(self, "_filmstrip_aspect_ratio", 16 / 9)
                thumb_w = max(1, int(aspect * thumb_h))
                placeholder = self._filmstrip_placeholder_cache.get(
                    (thumb_w, thumb_h)
                )
                if placeholder is None:
                    placeholder_image = Image.new(
                        "RGB", (thumb_w, thumb_h), DarkTheme.COLORS['bg_tertiary']
                    )
                    placeholder = ImageTk.PhotoImage(placeholder_image)
                    self._filmstrip_placeholder_cache[(thumb_w, thumb_h)] = placeholder
                return placeholder, thumb_w
            else:
                thumb_w = img.size[0]

            photo = ImageTk.PhotoImage(img)
            if hasattr(self, "_thumb_cache"):
                self._thumb_cache[cache_key] = (photo, thumb_w)
                self._thumb_cache_order.append(cache_key)
                if len(self._thumb_cache_order) > self._thumb_cache_max:
                    drop = self._thumb_cache_order.pop(0)
                    try:
                        del self._thumb_cache[drop]
                    except Exception:
                        pass
            return photo, thumb_w
        except Exception:
            return None

    def _queue_filmstrip_thumbnail(self, path, thumb_h, src_mtime, cache_path):
        if not cache_path:
            return
        key = (path, thumb_h, src_mtime)
        with self._thumb_generation_lock:
            if key in self._thumb_generation_pending:
                return
            self._thumb_generation_pending.add(key)
        self._thumb_generation_queue.put((key, cache_path))

    def _filmstrip_thumb_worker(self):
        from PIL import Image

        while not self._thumb_worker_stop.is_set():
            try:
                key, cache_path = self._thumb_generation_queue.get(timeout=0.2)
            except queue.Empty:
                continue
            path, thumb_h, _src_mtime = key
            try:
                with Image.open(path) as source:
                    image = source.convert("RGB")
                if image.height <= 0:
                    continue
                thumb_w = max(1, int((image.width / image.height) * thumb_h))
                image = image.resize(
                    (thumb_w, thumb_h), Image.Resampling.LANCZOS
                )
                temporary = cache_path + ".tmp"
                image.save(temporary, "JPEG", quality=88)
                os.replace(temporary, cache_path)
            except Exception:
                try:
                    os.remove(cache_path + ".tmp")
                except OSError:
                    pass
            finally:
                self._thumb_generation_queue.task_done()
                self._thumb_ready_queue.put(key)

    def _drain_thumb_ready(self):
        refreshed = False
        while True:
            try:
                key = self._thumb_ready_queue.get_nowait()
            except queue.Empty:
                break
            with self._thumb_generation_lock:
                self._thumb_generation_pending.discard(key)
            refreshed = True
        if refreshed:
            self._filmstrip_signature = None
            self._schedule_filmstrip_update(20)
        try:
            self._thumb_ready_job = self.root.after(50, self._drain_thumb_ready)
        except tk.TclError:
            self._thumb_ready_job = None

    def _on_filmstrip_click(self, event):
        if not self._filmstrip_map:
            return
        canvas_x = self.filmstrip_canvas.canvasx(event.x)
        canvas_y = self.filmstrip_canvas.canvasy(event.y)
        candidates = list(
            reversed(
                self.filmstrip_canvas.find_overlapping(
                    canvas_x - 2, canvas_y - 2, canvas_x + 2, canvas_y + 2
                )
            )
        )
        closest = self.filmstrip_canvas.find_closest(canvas_x, canvas_y)
        if closest:
            candidates.extend(closest)
        idx = next(
            (self._filmstrip_map[item] for item in candidates if item in self._filmstrip_map),
            None,
        )
        if idx is None:
            return
        if self.frame_manager and self.frame_manager.go_to_frame(idx):
            self.show_current_frame()
            self.update_frame_counter()

    def _on_filmstrip_scroll(self, event):
        try:
            self.filmstrip_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def on_frame_slider(self, value):
        try:
            index = int(float(value)) - 1
        except Exception:
            return
        if self._updating_frame_slider:
            return
        if self._slider_navigation_job:
            try:
                self.root.after_cancel(self._slider_navigation_job)
            except Exception:
                pass
        self._slider_navigation_job = self.root.after(
            70, lambda target=index: self._run_slider_navigation(target)
        )

    def _run_slider_navigation(self, index):
        self._slider_navigation_job = None
        if (
            self.frame_manager
            and index != self.frame_manager.current_frame_index
            and self.frame_manager.go_to_frame(index)
        ):
            self.show_current_frame()
            self.update_frame_counter()

    def _set_range_start(self):
        if not self.frame_manager:
            return
        info = self.frame_manager.get_current_frame_info()
        if info:
            self.range_start_entry.delete(0, tk.END)
            self.range_start_entry.insert(0, str(info['index'] + 1))
            self._update_range_summary()
            self._update_filmstrip(info['index'])

    def _set_range_end(self):
        if not self.frame_manager:
            return
        info = self.frame_manager.get_current_frame_info()
        if info:
            self.range_end_entry.delete(0, tk.END)
            self.range_end_entry.insert(0, str(info['index'] + 1))
            self._update_range_summary()
            self._update_filmstrip(info['index'])

    def _set_frame_tool(self, tool_id):
        self.selected_tool = tool_id
        for tid, btn in getattr(self, "frame_tools_buttons", {}).items():
            if tid == tool_id:
                btn.configure(bg=DarkTheme.COLORS['accent_primary'], fg=DarkTheme.COLORS['text_inverse'])
            else:
                btn.configure(bg=DarkTheme.COLORS['bg_tertiary'], fg=DarkTheme.COLORS['text_primary'])
        instructions = {
            "clone": "Clone: clique direito define a fonte; arraste o direito para mover a imagem.",
            "heal": "Healing: clique direito define a fonte; arraste o direito para mover a imagem.",
            "brush": "Pincel: arraste para marcar; botão direito + arrasto move a imagem.",
            "erase": "Borracha: arraste para apagar; botão direito + arrasto move a imagem.",
            "select_rect": "Retângulo: arraste para limitar filtros e retoques à seleção.",
            "select_lasso": "Laço: contorne livremente a área desejada.",
            "select": "Selecionar: botão direito + arrasto move o frame ampliado.",
        }
        if hasattr(self, "selection_status_var") and tool_id in instructions:
            self.selection_status_var.set(instructions[tool_id])
        if hasattr(self, "status_var") and tool_id in instructions:
            self.status_var.set(instructions[tool_id])

    def _on_brush_size_change(self, value):
        try:
            self.brush_size = int(float(value))
            if hasattr(self, "brush_size_label"):
                self.brush_size_label.config(text=str(self.brush_size))
        except Exception:
            pass

    def auto_select_dust_action(self):
        try:
            info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
            if not info:
                return
            idx = info["index"]
            prev_path, curr_path, next_path, _ = self._get_triplet_paths(idx)
            curr = cv2.imread(curr_path, cv2.IMREAD_COLOR) if curr_path else None
            prev = cv2.imread(prev_path, cv2.IMREAD_COLOR) if prev_path else None
            nxt = cv2.imread(next_path, cv2.IMREAD_COLOR) if next_path else None
            if curr is None:
                return
            mask = self._compose_auto_dust_mask(curr, prev, nxt)
            if mask is None:
                self.update_auto_mask_current(force=True)
                mask = self._load_auto_mask(curr_path)
            else:
                os.makedirs(self.auto_masks_dir, exist_ok=True)
                mask_path = self._auto_mask_path_for_frame(curr_path)
                cv2.imwrite(mask_path, mask)
            detected_pixels = int(np.count_nonzero(mask)) if mask is not None else 0
            if hasattr(self, "show_auto_mask_var"):
                self.show_auto_mask_var.set(detected_pixels > 0)
            self.show_current_frame()
            if detected_pixels:
                self.status_label.config(
                    text=(
                        f"Sujeira detectada ({detected_pixels} px). "
                        "Use Auto sujeira > Corrigir pontos detectados."
                    )
                )
            else:
                self.status_label.config(text="Nenhuma sujeira transitória segura detectada.")
        except Exception:
            self.status_label.config(text="Falha ao gerar auto-máscara.")

    def toggle_auto_mask_overlay(self):
        self.show_auto_mask_var.set(not self.show_auto_mask_var.get())
        self.show_current_frame()
        self.status_var.set(
            "Pontos automáticos visíveis"
            if self.show_auto_mask_var.get()
            else "Pontos automáticos ocultos"
        )

    def clear_auto_mask_current(self):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        try:
            os.remove(self._auto_mask_path_for_frame(info["path"]))
        except FileNotFoundError:
            pass
        self.show_auto_mask_var.set(False)
        self.show_current_frame()
        self.status_var.set("Detecção automática removida do frame")

    def repair_auto_dust_current(self):
        if not self.frame_manager or not self.frame_manager.frames:
            return
        info = self.frame_manager.get_current_frame_info()
        auto_mask_path = self._auto_mask_path_for_frame(info["path"])
        if not os.path.exists(auto_mask_path):
            self.auto_select_dust_action()
        mask = cv2.imread(auto_mask_path, cv2.IMREAD_GRAYSCALE)
        if mask is None or not np.any(mask):
            messagebox.showinfo(
                "Sem pontos seguros",
                "Não há sujeira automática segura para corrigir neste frame.",
            )
            return
        self._update_restorer_config()
        self._push_undo_current("auto-dust")
        frame_index = info["index"]
        prev_path, curr_path, next_path, out_path = self._get_triplet_paths(frame_index)
        options = {
            "model_name": self.model_name_var.get().strip(),
            "show_auto_mask": True,
            "double_pass": bool(self.double_pass_var.get()),
            "frame_index": frame_index,
            "limit_output_to_mask": True,
        }

        def repair_task(context):
            context.report(15, "Alinhando frames vizinhos...")
            self._restore_triplet_to_path(
                prev_path, curr_path, next_path, out_path, options=options
            )
            context.report(100, "Correção automática concluída")
            return out_path

        def repair_complete(_path):
            if self.workspace:
                self.workspace.commit_operation(
                    "auto_dust.repair",
                    payload={"automatic_mask": True},
                    frame_number=frame_index,
                    artifacts={"frame": out_path, "auto_mask": auto_mask_path},
                )
            self.view_mode = "restored"
            self.view_mode_label.config(text="Visualização: restaurado")
            self.show_auto_mask_var.set(False)
            self._mark_frame_clean(curr_path)
            self.show_current_frame()
            self.status_var.set(
                "Sujeira automática corrigida; marcações amarelas foram ocultadas"
            )

        self._start_ui_job("Correção de sujeira", repair_task, repair_complete)

    def _camera_segment_source(self):
        return self.current_video or getattr(self.workspace, "active_video_name", None) or os.path.basename(self.frame_manager.frames_dir)

    def open_camera_segments_dialog(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showinfo("Sem frames", "Extraia e selecione uma sequência primeiro.")
            return
        try:
            current_range = (
                max(1, int(self.range_start_entry.get())),
                min(len(self.frame_manager.frames), int(self.range_end_entry.get())),
            )
        except ValueError:
            current_range = (1, len(self.frame_manager.frames))
        source = self._camera_segment_source()
        CameraSegmentsDialog(
            self.root,
            self.camera_segment_store.list(source),
            current_range,
            self._detect_camera_segments,
            self._add_camera_segment,
            self._delete_camera_segment,
            self._apply_camera_segment,
        )

    def _detect_camera_segments(self, dialog):
        frames = list(self.frame_manager.frames)
        frames_dir = self.frame_manager.frames_dir
        paths = [os.path.join(frames_dir, filename) for filename in frames]
        source = self._camera_segment_source()
        dialog.set_detecting(True)

        def detection_task(context):
            return detect_camera_segments(
                paths,
                progress_callback=lambda value: context.report(
                    value, f"Comparando posições de câmera — {value:.0f}%"
                ),
                cancel_callback=lambda: context.cancellation_requested,
            )

        def detection_complete(segments):
            self.camera_segment_store.replace(source, segments)
            if self.workspace:
                self.workspace.commit_operation(
                    "camera_segments.detect",
                    payload={
                        "source": source,
                        "segments": [
                            {
                                "id": item.id,
                                "name": item.name,
                                "start": item.start,
                                "end": item.end,
                                "confidence": item.confidence,
                            }
                            for item in segments
                        ],
                    },
                )
            try:
                dialog.set_segments(segments)
                dialog.set_detecting(False)
            except tk.TclError:
                pass
            self.status_var.set(f"{len(segments)} cenas/câmeras detectadas")

        def detection_error(error):
            try:
                dialog.set_detecting(False)
            except tk.TclError:
                pass
            messagebox.showerror("Detecção de câmeras", error)

        self._start_ui_job(
            "Detecção de cenas", detection_task, detection_complete, detection_error
        )

    def _add_camera_segment(self, name, start, end, dialog):
        source = self._camera_segment_source()
        segment = CameraSegment.create(name, start - 1, end - 1)
        self.camera_segment_store.add(source, segment)
        dialog.set_segments(self.camera_segment_store.list(source))
        if self.workspace:
            self.workspace.commit_operation(
                "camera_segment.add",
                payload={
                    "source": source,
                    "id": segment.id,
                    "name": segment.name,
                    "start": segment.start,
                    "end": segment.end,
                },
            )

    def _delete_camera_segment(self, segment, dialog):
        source = self._camera_segment_source()
        self.camera_segment_store.delete(source, segment.id)
        dialog.set_segments(self.camera_segment_store.list(source))
        if self.workspace:
            self.workspace.commit_operation(
                "camera_segment.delete",
                payload={"source": source, "id": segment.id},
            )

    def _apply_camera_segment(self, segment):
        self.range_start_entry.delete(0, tk.END)
        self.range_start_entry.insert(0, str(segment.start + 1))
        self.range_end_entry.delete(0, tk.END)
        self.range_end_entry.insert(0, str(segment.end + 1))
        self._update_range_summary()
        self.frame_manager.go_to_frame(segment.start)
        self.show_current_frame()
        self.update_frame_counter()
        self.status_var.set(
            f"Intervalo ativo: {segment.name} ({segment.start + 1}–{segment.end + 1})"
        )

    def open_clean_plate_dialog(self):
        if not self.frame_manager or len(self.frame_manager.frames) < 3:
            messagebox.showinfo(
                "Placa limpa", "São necessários pelo menos três frames extraídos."
            )
            return
        try:
            start = max(0, int(self.range_start_entry.get()) - 1)
            end = min(
                len(self.frame_manager.frames) - 1,
                int(self.range_end_entry.get()) - 1,
            )
        except ValueError:
            messagebox.showerror("Placa limpa", "Escolha um intervalo válido.")
            return
        if end - start < 2:
            messagebox.showerror(
                "Placa limpa", "O intervalo precisa conter pelo menos três frames."
            )
            return
        CleanPlateDialog(
            self.root,
            start + 1,
            end + 1,
            lambda apply_after: self._start_clean_plate(start, end, apply_after),
        )

    def _start_clean_plate(self, start, end, apply_after_build):
        frames = list(self.frame_manager.frames)
        frames_dir = self.frame_manager.frames_dir
        source_paths = []
        for frame_index, filename in enumerate(frames):
            restored = os.path.join(self.restored_dir, filename)
            original = os.path.join(frames_dir, filename)
            source_paths.append(restored if os.path.exists(restored) else original)
        sample_indices = sorted(
            set(np.linspace(start, end, min(15, end - start + 1), dtype=int).tolist())
        )
        source_name = self._camera_segment_source()
        plate_id = hashlib.sha256(
            f"{source_name}:{start}:{end}:{self.workspace.active_branch if self.workspace else 'principal'}".encode("utf-8")
        ).hexdigest()[:16]
        plate_dir = os.path.join(self.clean_plates_dir, plate_id)
        plate_path = os.path.join(plate_dir, "plate.png")
        static_mask_path = os.path.join(plate_dir, "static_background.png")

        def clean_plate_task(context):
            samples = []
            for position, frame_index in enumerate(sample_indices):
                context.check_cancelled()
                image = cv2.imread(source_paths[frame_index], cv2.IMREAD_COLOR)
                if image is None:
                    raise RuntimeError(f"Não foi possível ler {source_paths[frame_index]}")
                samples.append(image)
                context.report(
                    (position + 1) * 25.0 / len(sample_indices),
                    f"Lendo amostras estáticas — {position + 1}/{len(sample_indices)}",
                )
            plate, static_mask, diagnostics = build_clean_plate(
                samples,
                progress_callback=lambda value: context.report(
                    25.0 + value * 0.35,
                    f"Separando fundo e movimento — {value:.0f}%",
                ),
            )
            os.makedirs(plate_dir, exist_ok=True)
            if not cv2.imwrite(plate_path, plate) or not cv2.imwrite(
                static_mask_path, static_mask
            ):
                raise RuntimeError("Não foi possível salvar a placa limpa")
            if self.workspace:
                self.workspace.commit_operation(
                    "clean_plate.build",
                    payload={
                        "source": source_name,
                        "start": start,
                        "end": end,
                        "diagnostics": diagnostics,
                    },
                    artifacts={"plate": plate_path, "background_mask": static_mask_path},
                )
            modified = 0
            context.report(60, "Placa limpa criada")
            if apply_after_build and diagnostics["camera_static"]:
                chunk_artifacts = {}
                for position, frame_index in enumerate(range(start, end + 1)):
                    context.check_cancelled()
                    current = cv2.imread(source_paths[frame_index], cv2.IMREAD_COLOR)
                    previous = cv2.imread(
                        source_paths[max(start, frame_index - 1)], cv2.IMREAD_COLOR
                    )
                    following = cv2.imread(
                        source_paths[min(end, frame_index + 1)], cv2.IMREAD_COLOR
                    )
                    if current is None:
                        continue
                    defect_mask = detect_transient_defects(previous, current, following)
                    for extra_path in (
                        self._mask_path_for_frame(os.path.join(frames_dir, frames[frame_index])),
                        self._auto_mask_path_for_frame(os.path.join(frames_dir, frames[frame_index])),
                    ):
                        extra = cv2.imread(extra_path, cv2.IMREAD_GRAYSCALE) if os.path.exists(extra_path) else None
                        if extra is not None:
                            defect_mask = cv2.bitwise_or(defect_mask, extra)
                    selection = self._load_selection_cv(
                        os.path.join(frames_dir, frames[frame_index]), frame_index
                    )
                    if selection is not None:
                        defect_mask = cv2.bitwise_and(defect_mask, selection)
                    restored, frame_diagnostics = apply_clean_plate(
                        current, plate, static_mask, defect_mask
                    )
                    if frame_diagnostics["replaced_pixels"]:
                        output = os.path.join(self.restored_dir, frames[frame_index])
                        os.makedirs(self.restored_dir, exist_ok=True)
                        if not cv2.imwrite(output, restored):
                            raise RuntimeError(f"Não foi possível salvar {output}")
                        chunk_artifacts[f"frame_{frame_index:09d}"] = output
                        modified += 1
                    if len(chunk_artifacts) >= 24 or frame_index == end:
                        if self.workspace and chunk_artifacts:
                            self.workspace.commit_operation(
                                "clean_plate.apply",
                                payload={
                                    "plate_id": plate_id,
                                    "start": start,
                                    "end": end,
                                    "foreground_protection": True,
                                },
                                artifacts=chunk_artifacts,
                            )
                        chunk_artifacts = {}
                    context.report(
                        60.0 + (position + 1) * 40.0 / (end - start + 1),
                        f"Aplicando somente no fundo — {position + 1}/{end - start + 1}",
                    )
            return {
                "diagnostics": diagnostics,
                "modified": modified,
                "applied": bool(apply_after_build and diagnostics["camera_static"]),
            }

        def clean_plate_complete(result):
            diagnostics = result["diagnostics"]
            if apply_after_build and not diagnostics["camera_static"]:
                messagebox.showwarning(
                    "Câmera não estática",
                    "A placa foi criada para inspeção, mas não foi aplicada. Separe uma cena menor ou estabilize o intervalo primeiro.",
                )
            elif result["applied"]:
                self.view_mode = "restored"
                self.view_mode_label.config(text="Visualização: restaurado")
                self.show_current_frame()
                messagebox.showinfo(
                    "Placa limpa concluída",
                    f"Fundo estável: {diagnostics['static_ratio'] * 100:.1f}%\nFrames modificados: {result['modified']}\nPessoas e movimentos grandes foram protegidos.",
                )
            else:
                messagebox.showinfo(
                    "Placa limpa criada",
                    f"Fundo estável identificado: {diagnostics['static_ratio'] * 100:.1f}%.",
                )

        self._start_ui_job(
            "Placa limpa de fundo", clean_plate_task, clean_plate_complete
        )

    def go_to_frame_action(self):
        if not self.frame_manager:
            return
        try:
            idx = int(self.goto_entry.get()) - 1
        except Exception:
            return
        if self.frame_manager.go_to_frame(idx):
            self.show_current_frame()
            self.update_frame_counter()

    # Restoration actions
    def _update_restorer_config(self):
        try:
            self.restorer.cfg.use_alignment = bool(self.use_alignment_var.get())
            mode = self.automask_mode_var.get().strip().lower()
            self.restorer.cfg.automask_mode = "aggressive" if mode == "aggressive" else "normal"
            self.restorer.cfg.inpaint_radius = int(self.inpaint_radius_entry.get())
            self.restorer.cfg.strong_thresh = int(self.strong_thresh_entry.get())
            self.restorer.cfg.deflicker_enabled = bool(self.deflicker_var.get())
            self.restorer.cfg.deflicker_strength = float(self.deflicker_strength_var.get())
            self.restorer.cfg.deflicker_local_enabled = bool(self.deflicker_local_var.get())
            self.restorer.cfg.deflicker_local_strength = float(self.deflicker_local_strength_var.get())
            self.restorer.cfg.fieldsplit_enabled = bool(self.fieldsplit_var.get())
            self.restorer.cfg.register_channels = bool(self.register_channels_var.get())
            self.restorer.cfg.dewarp_strength = float(self.dewarp_strength_var.get())
            self.restorer.cfg.auto_color_balance = bool(self.auto_color_balance_var.get())
            self.restorer.cfg.auto_contrast = bool(self.auto_contrast_var.get())
            self.restorer.cfg.degrain_strength = float(self.degrain_strength_var.get())
        except Exception:
            pass

    def _apply_profile(self, profile_name):
        profile = (profile_name or "").strip().lower()
        if profile == "rapido":
            self.use_alignment_var.set(False)
            self.inpaint_radius_entry.delete(0, tk.END)
            self.inpaint_radius_entry.insert(0, "2")
            self.strong_thresh_entry.delete(0, tk.END)
            self.strong_thresh_entry.insert(0, "45")
            self.deflicker_var.set(False)
            self.deflicker_strength_var.set(0.2)
            self.double_pass_var.set(False)
            self.deflicker_local_var.set(False)
            self.deflicker_local_strength_var.set(0.2)
            self.fieldsplit_var.set(False)
            self.register_channels_var.set(False)
            self.dewarp_strength_var.set(0.0)
            self.auto_color_balance_var.set(False)
            self.auto_contrast_var.set(False)
            self.degrain_strength_var.set(0.0)
        elif profile == "maximo":
            self.use_alignment_var.set(True)
            self.inpaint_radius_entry.delete(0, tk.END)
            self.inpaint_radius_entry.insert(0, "4")
            self.strong_thresh_entry.delete(0, tk.END)
            self.strong_thresh_entry.insert(0, "30")
            self.deflicker_var.set(True)
            self.deflicker_strength_var.set(0.7)
            self.double_pass_var.set(True)
            self.deflicker_local_var.set(True)
            self.deflicker_local_strength_var.set(0.6)
            self.fieldsplit_var.set(False)
            self.register_channels_var.set(True)
            self.dewarp_strength_var.set(0.2)
            self.auto_color_balance_var.set(True)
            self.auto_contrast_var.set(True)
            self.degrain_strength_var.set(0.3)
        elif profile == "qualidade":
            self.use_alignment_var.set(True)
            self.inpaint_radius_entry.delete(0, tk.END)
            self.inpaint_radius_entry.insert(0, "3")
            self.strong_thresh_entry.delete(0, tk.END)
            self.strong_thresh_entry.insert(0, "35")
            self.deflicker_var.set(True)
            self.deflicker_strength_var.set(0.5)
            self.double_pass_var.set(False)
            self.deflicker_local_var.set(True)
            self.deflicker_local_strength_var.set(0.4)
            self.fieldsplit_var.set(False)
            self.register_channels_var.set(True)
            self.dewarp_strength_var.set(0.1)
            self.auto_color_balance_var.set(False)
            self.auto_contrast_var.set(True)
            self.degrain_strength_var.set(0.2)
        else:
            # Manual: do nothing
            pass
        self._update_restorer_config()

    def _toggle_advanced(self):
        if not hasattr(self, "advanced_frame"):
            return
        try:
            is_visible = self.show_advanced_var.get()
        except Exception:
            is_visible = False
        if is_visible:
            self.advanced_frame.pack_forget()
            self.show_advanced_var.set(False)
            try:
                if hasattr(self, "advanced_toggle_btn"):
                    self.advanced_toggle_btn.config(text="Mostrar opções avançadas ▾")
            except Exception:
                pass
        else:
            self.advanced_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
            self.show_advanced_var.set(True)
            try:
                if hasattr(self, "advanced_toggle_btn"):
                    self.advanced_toggle_btn.config(text="Ocultar opções avançadas ▴")
            except Exception:
                pass

    def _apply_global_preset(self):
        preset_name = self.global_preset_var.get() if hasattr(self, "global_preset_var") else ""
        settings = get_global_preset_settings(preset_name)
        profile_label = settings.get("profile_label", "Qualidade")
        upscale_quality = settings.get("upscale_quality", "Qualidade")
        upscale_scale = settings.get("upscale_scale", "Auto")
        use_upscale = bool(settings.get("use_upscale", False))
        view_upscale = bool(settings.get("view_upscale", False))
        prefer_swinir = bool(settings.get("prefer_swinir", True))

        # Apply restoration profile
        try:
            if hasattr(self, "profile_var"):
                self.profile_var.set(profile_label)
            self._apply_profile(profile_label)
        except Exception:
            pass

        # Upscale controls
        try:
            if hasattr(self, "upscale_quality_var"):
                self.upscale_quality_var.set(upscale_quality)
            if hasattr(self, "upscale_scale_var"):
                self.upscale_scale_var.set(upscale_scale)
            if hasattr(self, "use_upscale_render_var"):
                self.use_upscale_render_var.set(use_upscale)
            if hasattr(self, "view_upscale_var"):
                self.view_upscale_var.set(view_upscale)
        except Exception:
            pass

        # Choose engine based on availability
        try:
            engine_value = "RRDB (BSRGAN/ESRGAN)"
            if prefer_swinir and self.model_pipeline:
                scale = self._get_selected_upscale_scale()
                try:
                    swinir_candidates = self.model_pipeline.list_swinir_sr_weights(scale=scale)
                except Exception:
                    swinir_candidates = []
                if swinir_candidates:
                    engine_value = "SwinIR (SR)"
            if hasattr(self, "upscale_engine_var"):
                self.upscale_engine_var.set(engine_value)
        except Exception:
            pass

        try:
            self._apply_upscale_quality()
            self._update_upscale_list()
            self._apply_selected_upscale()
            self._update_upscale_info_label()
        except Exception:
            pass

        try:
            if hasattr(self, "status_label"):
                label = (preset_name or "Cinema").capitalize()
                self.status_label.config(text=f"Preset global aplicado: {label}")
        except Exception:
            pass

    def _restore_triplet_to_path(
        self, prev_path, curr_path, next_path, out_path, options=None
    ):
        prev = cv2.imread(prev_path, cv2.IMREAD_COLOR)
        curr = cv2.imread(curr_path, cv2.IMREAD_COLOR)
        nxt = cv2.imread(next_path, cv2.IMREAD_COLOR)
        if prev is None or curr is None or nxt is None:
            raise FileNotFoundError("Nao foi possivel carregar frames para restauracao")

        original_curr = curr.copy()
        h, w = curr.shape[:2]
        prev = cv2.resize(prev, (w, h), interpolation=cv2.INTER_AREA)
        nxt = cv2.resize(nxt, (w, h), interpolation=cv2.INTER_AREA)

        options = options or {}
        model_name = options.get("model_name")
        if model_name is None:
            model_name = self.model_name_var.get().strip()
        mask = None
        # load manual mask if exists
        manual_mask_path = self._mask_path_for_frame(curr_path)
        if os.path.exists(manual_mask_path):
            try:
                mask = cv2.imread(manual_mask_path, cv2.IMREAD_GRAYSCALE)
            except Exception:
                mask = None
        selection_mask = self._load_selection_cv(
            curr_path, options.get("frame_index")
        )
        if selection_mask is not None:
            if selection_mask.shape != curr.shape[:2]:
                selection_mask = cv2.resize(
                    selection_mask,
                    (curr.shape[1], curr.shape[0]),
                    interpolation=cv2.INTER_NEAREST,
                )
            mask = (
                selection_mask
                if mask is None
                else cv2.bitwise_and(mask, selection_mask)
            )

        if model_name == "DnCNN (OpenCV)":
            prev = self.model_pipeline.denoise_opencv(prev)
            curr = self.model_pipeline.denoise_opencv(curr)
            nxt = self.model_pipeline.denoise_opencv(nxt)
        elif model_name == "DnCNN (PyTorch)":
            p = self.model_pipeline.denoise_dncnn(prev)
            c = self.model_pipeline.denoise_dncnn(curr)
            n = self.model_pipeline.denoise_dncnn(nxt)
            if p is not None:
                prev = p
            if c is not None:
                curr = c
            if n is not None:
                nxt = n
        elif model_name == "SwinIR (Denoise)":
            p = self.model_pipeline.denoise_swinir(prev)
            c = self.model_pipeline.denoise_swinir(curr)
            n = self.model_pipeline.denoise_swinir(nxt)
            if p is not None:
                prev = p
            if c is not None:
                curr = c
            if n is not None:
                nxt = n
        elif model_name == "Restormer (Denoise)":
            p = self.model_pipeline.denoise_restormer(prev)
            c = self.model_pipeline.denoise_restormer(curr)
            n = self.model_pipeline.denoise_restormer(nxt)
            if p is not None:
                prev = p
            if c is not None:
                curr = c
            if n is not None:
                nxt = n

        if model_name == "UNet Dust":
            model_mask = self.model_pipeline.predict_dust_mask_unet(curr, threshold=0.5)
            if model_mask is not None:
                mask = model_mask if mask is None else cv2.bitwise_or(mask, model_mask)

        # auto-mask overlay if enabled
        show_auto_mask = options.get("show_auto_mask")
        if show_auto_mask is None:
            show_auto_mask = self.show_auto_mask_var.get()
        if show_auto_mask:
            try:
                auto_mask_path = self._auto_mask_path_for_frame(curr_path)
                auto_mask = cv2.imread(
                    auto_mask_path, cv2.IMREAD_GRAYSCALE
                ) if os.path.exists(auto_mask_path) else None
                if auto_mask is None:
                    auto_mask = self.restorer.build_automask(curr)
                mask = auto_mask if mask is None else cv2.bitwise_or(mask, auto_mask)
            except Exception:
                pass
        if selection_mask is not None and mask is not None:
            mask = cv2.bitwise_and(mask, selection_mask)

        restored, _ = self.restorer.restore_triplet(prev, curr, nxt, mask=mask)
        double_pass = options.get("double_pass")
        if double_pass is None:
            double_pass = self.double_pass_var.get()
        if double_pass:
            restored, _ = self.restorer.restore_triplet(prev, restored, nxt, mask=mask)
        output_limit = selection_mask
        if options.get("limit_output_to_mask") and mask is not None:
            output_limit = (
                mask
                if output_limit is None
                else cv2.bitwise_and(output_limit, mask)
            )
        if output_limit is not None:
            restored[output_limit == 0] = original_curr[output_limit == 0]
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        cv2.imwrite(out_path, restored)

    def _get_triplet_paths(self, index):
        frames = self.frame_manager.frames
        if not frames:
            return None, None, None, None
        index = max(0, min(index, len(frames) - 1))
        prev_i = max(0, index - 1)
        next_i = min(len(frames) - 1, index + 1)
        frames_dir = self.frame_manager.frames_dir
        prev_path = os.path.join(frames_dir, frames[prev_i])
        curr_path = os.path.join(frames_dir, frames[index])
        next_path = os.path.join(frames_dir, frames[next_i])
        out_path = os.path.join(self.restored_dir, frames[index])
        return prev_path, curr_path, next_path, out_path

    def _get_source_frame_path(self, index):
        frames = self.frame_manager.frames
        if not frames:
            return None
        index = max(0, min(index, len(frames) - 1))
        frame_name = frames[index]
        original = os.path.join(self.frame_manager.frames_dir, frame_name)
        restored = os.path.join(self.restored_dir, frame_name)
        manual = os.path.join(self.manual_stab_dir, frame_name)
        if self.use_manual_stab_var.get() and os.path.exists(manual):
            return manual
        if os.path.exists(restored):
            return restored
        return original

    def restore_current_frame_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        self._update_restorer_config()
        self.restore_progress_var.set(0)
        self._push_undo_current("restore")

        idx = self.frame_manager.current_frame_index
        prev_path, curr_path, next_path, out_path = self._get_triplet_paths(idx)
        if not curr_path:
            return

        self.status_label.config(text="Restaurando frame atual...")
        try:
            if (not self.reprocess_var.get()) and os.path.exists(out_path):
                self.status_label.config(text="Frame ja restaurado (cache)")
            else:
                self._restore_triplet_to_path(prev_path, curr_path, next_path, out_path)
            self.status_label.config(text="Frame restaurado.")
            self.view_mode = "restored"
            self.view_mode_label.config(text="Visualizacao: restaurado")
            self.show_current_frame()
            if getattr(self, "auto_save_restore_var", None) is None or self.auto_save_restore_var.get():
                self._mark_frame_clean(curr_path)
        except Exception as e:
            self.status_label.config(text=f"Erro: {str(e)}")
            messagebox.showerror("Erro", f"Erro ao restaurar frame: {str(e)}")

    def save_current_frame_action(self):
        info = self.frame_manager.get_current_frame_info() if self.frame_manager else None
        if not info:
            return
        path = info["path"]
        if not hasattr(self, "_dirty_mask_frames") or path not in self._dirty_mask_frames:
            self.status_label.config(text="Nada para salvar no frame atual.")
            return
        self.restore_current_frame_action()

    def restore_range_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        self._update_restorer_config()
        self.restore_progress_var.set(0)

        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return
        frames = list(self.frame_manager.frames)
        start = max(0, start)
        end = min(end, len(frames) - 1)
        if start > end:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return

        frame_indices = list(range(start, end + 1))
        options = {
            "model_name": self.model_name_var.get().strip(),
            "show_auto_mask": bool(self.show_auto_mask_var.get()),
            "double_pass": bool(self.double_pass_var.get()),
        }
        reprocess = bool(self.reprocess_var.get())
        deflicker = bool(self.deflicker_var.get())
        mask_signatures = []
        for frame_index in frame_indices:
            mask_path = self._mask_path_for_frame(
                os.path.join(self.frame_manager.frames_dir, frames[frame_index])
            )
            if os.path.exists(mask_path):
                stat = os.stat(mask_path)
                mask_signatures.append([frame_index, stat.st_size, stat.st_mtime_ns])
        fingerprint_data = {
            "branch": self.workspace.active_branch if self.workspace else "principal",
            "frames": frames[start:end + 1],
            "options": options,
            "config": vars(self.restorer.cfg),
            "deflicker": deflicker,
            "masks": mask_signatures,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        worktree = self.workspace.branch_worktree() if self.workspace else self.project_manager.current_project_path
        checkpoint_path = os.path.join(
            worktree, ".jobs", "restoration", f"{fingerprint}.json"
        )
        if reprocess and os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)

        def restore_task(context):
            def process_frame(_item_index, frame_index):
                prev_path, curr_path, next_path, out_path = self._get_triplet_paths(frame_index)
                if reprocess or not os.path.exists(out_path):
                    self._restore_triplet_to_path(
                        prev_path,
                        curr_path,
                        next_path,
                        out_path,
                        options={**options, "frame_index": frame_index},
                    )
                if deflicker and frame_index > start:
                    previous_path = os.path.join(
                        self.restored_dir, frames[frame_index - 1]
                    )
                    previous = cv2.imread(previous_path, cv2.IMREAD_COLOR)
                    restored = cv2.imread(out_path, cv2.IMREAD_COLOR)
                    if previous is not None and restored is not None:
                        restored = self.restorer.deflicker_match(
                            previous, restored, self.restorer.cfg.deflicker_strength
                        )
                        cv2.imwrite(out_path, restored)

            def commit_chunk(chunk_start, chunk_end):
                if not self.workspace:
                    return
                chunk_indices = frame_indices[chunk_start:chunk_end]
                artifacts = {
                    f"frame_{frame_index:09d}": os.path.join(
                        self.restored_dir, frames[frame_index]
                    )
                    for frame_index in chunk_indices
                    if os.path.exists(os.path.join(self.restored_dir, frames[frame_index]))
                }
                self.workspace.commit_operation(
                    "restoration.chunk",
                    payload={
                        "fingerprint": fingerprint,
                        "start": chunk_indices[0],
                        "end": chunk_indices[-1],
                        "options": options,
                    },
                    artifacts=artifacts,
                )

            return self.chunk_runner.run(
                frame_indices,
                process_frame,
                context,
                checkpoint_path,
                fingerprint,
                message="Restaurando intervalo",
                on_chunk_complete=commit_chunk,
            )

        def restore_complete(result):
            self.view_mode = "restored"
            self.view_mode_label.config(text="Visualizacao: restaurado")
            self.show_current_frame()
            self.status_var.set(
                f"Restauração concluída: {result['total']} frames, "
                f"{result['skipped']} retomados do checkpoint"
            )

        self._start_ui_job("Restauração", restore_task, restore_complete)

    def apply_filter_range_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        self._update_restorer_config()

        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return
        frames = list(self.frame_manager.frames)
        start = max(0, start)
        end = min(end, len(frames) - 1)
        if start > end:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return
        frame_indices = list(range(start, end + 1))
        model_name = self.model_name_var.get().strip()
        reprocess = bool(self.reprocess_var.get())
        fingerprint_data = {
            "branch": self.workspace.active_branch if self.workspace else "principal",
            "frames": frames[start:end + 1],
            "model": model_name,
        }
        fingerprint = hashlib.sha256(
            json.dumps(fingerprint_data, sort_keys=True).encode("utf-8")
        ).hexdigest()
        worktree = self.workspace.branch_worktree() if self.workspace else self.project_manager.current_project_path
        checkpoint_path = os.path.join(
            worktree, ".jobs", "filter", f"{fingerprint}.json"
        )
        if reprocess and os.path.exists(checkpoint_path):
            os.remove(checkpoint_path)

        def filter_task(context):
            def process_frame(_item_index, frame_index):
                _, curr_path, _, out_path = self._get_triplet_paths(frame_index)
                if not reprocess and os.path.exists(out_path):
                    return
                image = cv2.imread(curr_path, cv2.IMREAD_COLOR)
                if image is None:
                    raise RuntimeError(f"Não foi possível ler {curr_path}")
                original_image = image.copy()
                if model_name == "DnCNN (OpenCV)":
                    image = self.model_pipeline.denoise_opencv(image)
                elif model_name == "DnCNN (PyTorch)":
                    denoised = self.model_pipeline.denoise_dncnn(image)
                    if denoised is not None:
                        image = denoised
                elif model_name == "SwinIR (Denoise)":
                    denoised = self.model_pipeline.denoise_swinir(image)
                    if denoised is not None:
                        image = denoised
                elif model_name == "Restormer (Denoise)":
                    denoised = self.model_pipeline.denoise_restormer(image)
                    if denoised is not None:
                        image = denoised
                elif model_name == "UNet Dust":
                    mask = self.model_pipeline.predict_dust_mask_unet(
                        image, threshold=0.5
                    )
                    if mask is not None:
                        image = self.restorer.restore_triplet(
                            image, image, image, mask=mask
                        )[0]
                selection_mask = self._load_selection_cv(curr_path, frame_index)
                if selection_mask is not None:
                    if selection_mask.shape != image.shape[:2]:
                        selection_mask = cv2.resize(
                            selection_mask,
                            (image.shape[1], image.shape[0]),
                            interpolation=cv2.INTER_NEAREST,
                        )
                    selected = selection_mask > 0
                    image = np.where(selected[..., None], image, original_image)
                os.makedirs(os.path.dirname(out_path), exist_ok=True)
                if not cv2.imwrite(out_path, image):
                    raise RuntimeError(f"Não foi possível salvar {out_path}")

            def commit_chunk(chunk_start, chunk_end):
                if not self.workspace:
                    return
                chunk_indices = frame_indices[chunk_start:chunk_end]
                artifacts = {
                    f"frame_{frame_index:09d}": os.path.join(
                        self.restored_dir, frames[frame_index]
                    )
                    for frame_index in chunk_indices
                    if os.path.exists(os.path.join(self.restored_dir, frames[frame_index]))
                }
                self.workspace.commit_operation(
                    "filter.chunk",
                    payload={
                        "fingerprint": fingerprint,
                        "model": model_name,
                        "start": chunk_indices[0],
                        "end": chunk_indices[-1],
                    },
                    artifacts=artifacts,
                )

            return self.chunk_runner.run(
                frame_indices,
                process_frame,
                context,
                checkpoint_path,
                fingerprint,
                message=f"Aplicando {model_name}",
                on_chunk_complete=commit_chunk,
            )

        def filter_complete(result):
            self.view_mode = "restored"
            self.view_mode_label.config(text="Visualizacao: restaurado")
            self.show_current_frame()
            self.status_var.set(
                f"Filtro concluído: {result['total']} frames, "
                f"{result['skipped']} retomados do checkpoint"
            )

        self._start_ui_job("Filtro", filter_task, filter_complete)

    def apply_manual_stabilization_range(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return

        try:
            dx = int(float(self.stab_offset_x.get() or "0"))
            dy = int(float(self.stab_offset_y.get() or "0"))
        except Exception:
            dx, dy = 0, 0

        frames = list(self.frame_manager.frames)
        frame_indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))

        def stabilization_task(context):
            os.makedirs(self.manual_stab_dir, exist_ok=True)
            done = 0
            for position, frame_index in enumerate(frame_indices):
                context.check_cancelled()
                source = os.path.join(self.restored_dir, frames[frame_index])
                if not os.path.exists(source):
                    source = os.path.join(self.frame_manager.frames_dir, frames[frame_index])
                image = cv2.imread(source, cv2.IMREAD_COLOR)
                if image is None:
                    continue
                height, width = image.shape[:2]
                transform = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
                shifted = cv2.warpAffine(
                    image, transform, (width, height), borderMode=cv2.BORDER_REFLECT
                )
                output = os.path.join(self.manual_stab_dir, frames[frame_index])
                if not cv2.imwrite(output, shifted):
                    raise RuntimeError(f"Não foi possível salvar {output}")
                if self.workspace:
                    self.workspace.commit_operation(
                        "frame.transform",
                        payload={
                            "translate_x": dx,
                            "translate_y": dy,
                            "rotation": 0.0,
                            "scale": 1.0,
                            "border_mode": "reflect",
                        },
                        frame_number=frame_index,
                        artifacts={"result": output},
                    )
                done += 1
                context.report(
                    (position + 1) * 100.0 / max(1, len(frame_indices)),
                    f"Centralizando frames — {position + 1}/{len(frame_indices)}",
                )
            return done

        def stabilization_complete(done):
            self.use_manual_stab_var.set(True)
            self.show_current_frame()
            self.status_var.set(f"Centralização aplicada em {done} frames")

        self._start_ui_job(
            "Centralização manual", stabilization_task, stabilization_complete
        )

    def apply_auto_stabilization_range(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return

        try:
            window = int(self.stab_window_entry.get())
        except Exception:
            window = 3
        if window < 3:
            window = 3
        if window % 2 == 0:
            window += 1
        radius = max(1, window // 2)

        frames = list(self.frame_manager.frames)
        frame_indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))

        def stabilization_task(context):
            os.makedirs(self.auto_stab_dir, exist_ok=True)
            temp_in = os.path.join(self.video_renderer.temp_dir, "stab_in")
            temp_out = os.path.join(self.video_renderer.temp_dir, "stab_out")
            os.makedirs(temp_in, exist_ok=True)
            os.makedirs(temp_out, exist_ok=True)
            for directory in (temp_in, temp_out):
                for filename in os.listdir(directory):
                    path = os.path.join(directory, filename)
                    if os.path.isfile(path):
                        os.remove(path)

            for position, frame_index in enumerate(frame_indices):
                context.check_cancelled()
                source = os.path.join(self.restored_dir, frames[frame_index])
                if not os.path.exists(source):
                    source = os.path.join(self.frame_manager.frames_dir, frames[frame_index])
                if os.path.exists(source):
                    shutil.copy2(source, os.path.join(temp_in, frames[frame_index]))
                context.report(
                    (position + 1) * 20.0 / max(1, len(frame_indices)),
                    f"Preparando estabilização — {position + 1}/{len(frame_indices)}",
                )

            def progress_callback(progress):
                context.report(
                    20.0 + progress * 0.7,
                    f"Analisando movimento — {progress:.0f}%",
                )

            success = self.video_renderer.stabilize_frames_ecc(
                temp_in,
                temp_out,
                progress_callback=progress_callback,
                window_radius=radius,
            )
            if not success:
                raise RuntimeError("A estabilização automática não produziu resultado")
            outputs = []
            output_names = os.listdir(temp_out)
            for position, filename in enumerate(output_names):
                context.check_cancelled()
                destination = os.path.join(self.auto_stab_dir, filename)
                shutil.copy2(os.path.join(temp_out, filename), destination)
                outputs.append(destination)
                context.report(
                    90.0 + (position + 1) * 10.0 / max(1, len(output_names)),
                    f"Salvando estabilização — {position + 1}/{len(output_names)}",
                )
            return len(outputs)

        def stabilization_complete(done):
            self.use_auto_stab_var.set(True)
            self.show_current_frame()
            self.status_var.set(f"Estabilização automática aplicada em {done} frames")

        self._start_ui_job(
            "Estabilização automática", stabilization_task, stabilization_complete
        )

    def _ensure_upscale_model(self):
        selection = self.upscale_model_var.get() if hasattr(self, "upscale_model_var") else "Auto"
        engine = self._get_upscale_engine()
        if selection.startswith("Auto"):
            scale = self._get_selected_upscale_scale()
            if engine == "swinir":
                if hasattr(self.model_pipeline, "auto_select_swinir_sr"):
                    self.model_pipeline.auto_select_swinir_sr(scale=scale)
                return self.model_pipeline.ensure_swinir_sr(scale=scale)
            if hasattr(self.model_pipeline, "auto_select_sr"):
                self.model_pipeline.auto_select_sr(scale=scale)
            return self.model_pipeline.get_sr_info().get("path") is not None
        if engine == "swinir":
            path = self.model_pipeline.get_swinir_weight_path(selection)
            if path:
                return self.model_pipeline.set_swinir_weights(path)
            return False
        path = self.model_pipeline.get_sr_weight_path(selection)
        if path:
            return self.model_pipeline.set_sr_weights(path)
        return False

    def upscale_current_frame_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        if not self._ensure_upscale_model():
            messagebox.showerror("Erro", "Nenhum modelo de upscale encontrado.")
            return

        idx = self.frame_manager.current_frame_index
        src_path = self._get_source_frame_path(idx)
        if not src_path:
            return

        try:
            tile = int(self.upscale_tile_var.get())
        except Exception:
            tile = 256
        try:
            overlap = int(self.upscale_overlap_var.get())
        except Exception:
            overlap = 20
        engine = self._get_upscale_engine()

        def upscale_task(context):
            context.report(5, "Carregando frame...")
            image = cv2.imread(src_path, cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Falha ao carregar frame.")
            context.report(15, "Executando super-resolução...")
            if engine == "swinir":
                upscaled = self.model_pipeline.upscale_swinir(
                    image, tile=tile, tile_overlap=overlap
                )
            else:
                upscaled = self.model_pipeline.upscale_rrdb(
                    image, tile=tile, tile_overlap=overlap
                )
            context.check_cancelled()
            if upscaled is None:
                raise ValueError("Upscale falhou.")
            os.makedirs(self.upscaled_dir, exist_ok=True)
            output = os.path.join(self.upscaled_dir, os.path.basename(src_path))
            context.report(90, "Salvando frame ampliado...")
            if not cv2.imwrite(output, upscaled):
                raise RuntimeError(f"Não foi possível salvar {output}")
            if self.workspace:
                self.workspace.commit_operation(
                    "frame.upscale",
                    payload={"engine": engine, "tile": tile, "overlap": overlap},
                    frame_number=idx,
                    artifacts={"result": output},
                )
            return output

        def upscale_complete(_output):
            self.view_upscale_var.set(True)
            self.show_current_frame()
            self.status_var.set("Upscale aplicado ao frame atual")

        self._start_ui_job("Upscale do frame", upscale_task, upscale_complete)

    def upscale_range_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        if not self._ensure_upscale_model():
            messagebox.showerror("Erro", "Nenhum modelo de upscale encontrado.")
            return

        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            messagebox.showerror("Erro", "Intervalo invalido.")
            return

        try:
            tile = int(self.upscale_tile_var.get())
        except Exception:
            tile = 256
        try:
            overlap = int(self.upscale_overlap_var.get())
        except Exception:
            overlap = 20
        engine = self._get_upscale_engine()
        frames = list(self.frame_manager.frames)
        frame_indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))
        source_paths = {index: self._get_source_frame_path(index) for index in frame_indices}

        def upscale_task(context):
            os.makedirs(self.upscaled_dir, exist_ok=True)
            done = 0
            for position, frame_index in enumerate(frame_indices):
                context.check_cancelled()
                source = source_paths.get(frame_index)
                if not source or not os.path.exists(source):
                    continue
                image = cv2.imread(source, cv2.IMREAD_COLOR)
                if image is None:
                    continue
                if engine == "swinir":
                    upscaled = self.model_pipeline.upscale_swinir(
                        image, tile=tile, tile_overlap=overlap
                    )
                else:
                    upscaled = self.model_pipeline.upscale_rrdb(
                        image, tile=tile, tile_overlap=overlap
                    )
                context.check_cancelled()
                if upscaled is None:
                    continue
                output = os.path.join(self.upscaled_dir, frames[frame_index])
                if not cv2.imwrite(output, upscaled):
                    raise RuntimeError(f"Não foi possível salvar {output}")
                if self.workspace:
                    self.workspace.commit_operation(
                        "frame.upscale",
                        payload={"engine": engine, "tile": tile, "overlap": overlap},
                        frame_number=frame_index,
                        artifacts={"result": output},
                    )
                done += 1
                context.report(
                    (position + 1) * 100.0 / max(1, len(frame_indices)),
                    f"Ampliando frames — {position + 1}/{len(frame_indices)}",
                )
            return done

        def upscale_complete(done):
            self.view_upscale_var.set(True)
            self.show_current_frame()
            self.status_var.set(f"Upscale aplicado em {done} frames")

        self._start_ui_job("Upscale do intervalo", upscale_task, upscale_complete)

    def toggle_view_mode(self):
        if self.view_mode == "original":
            self.view_mode = "restored"
        elif self.view_mode == "restored":
            self.view_mode = "compare"
        else:
            self.view_mode = "original"
        self.view_mode_label.config(text=f"Visualizacao: {self.view_mode}")
        self.show_current_frame()

    def open_manual_editor_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame carregado.")
            return
        idx = self.frame_manager.current_frame_index
        prev_path, curr_path, next_path, out_path = self._get_triplet_paths(idx)
        if not curr_path:
            return
        self._update_restorer_config()
        try:
            open_manual_editor(prev_path, curr_path, next_path, out_path, self.restorer.cfg)
            self.view_mode = "restored"
            self.view_mode_label.config(text="Visualizacao: restaurado")
            self.show_current_frame()
        except Exception as e:
            messagebox.showerror("Erro", f"Erro no editor manual: {str(e)}")

    def enable_compare_view(self):
        self.view_mode = "compare"
        self.view_mode_label.config(text="Visualizacao: compare")
        self.show_current_frame()

    def _on_compare_change(self):
        if self.view_mode != "compare":
            self.view_mode = "compare"
            self.view_mode_label.config(text="Visualizacao: compare")
        self.show_current_frame()

    def select_unet_weights(self):
        path = filedialog.askopenfilename(
            title="Selecionar UNet weights",
            filetypes=[("PyTorch weights", "*.pth"), ("All files", "*.*")]
        )
        if path:
            ok = self.model_pipeline.set_unet_weights(path)
            self.unet_weights_var.set(os.path.basename(path))
            if ok:
                self.status_label.config(text="UNet weights carregados")
            else:
                self.status_label.config(text="Falha ao carregar UNet weights")

    def select_dncnn_weights(self):
        path = filedialog.askopenfilename(
            title="Selecionar DnCNN weights",
            filetypes=[("Weights", "*.pth *.pt *.mat"), ("All files", "*.*")]
        )
        if path:
            if path.lower().endswith(".mat"):
                self.status_label.config(text="DnCNN .mat nao suportado. Use pesos .pth (KAIR).")
                return
            ok = self.model_pipeline.set_dncnn_weights(path)
            self.dncnn_weights_var.set(os.path.basename(path))
            self.status_label.config(text="DnCNN weights selecionados" if ok else "DnCNN weights invalidos")
            self._update_model_menu()

    def _apply_dncnn_choice(self):
        try:
            selection = self.dncnn_choice_var.get()
            if selection.startswith("Auto"):
                if hasattr(self.model_pipeline, "refresh_dncnn"):
                    self.model_pipeline.refresh_dncnn()
            else:
                path = self.model_pipeline.get_dncnn_weight_path(selection)
                if path:
                    self.model_pipeline.set_dncnn_weights(path)
                    self.dncnn_weights_var.set(os.path.basename(path))
            self._update_model_menu()
            self._sync_model_weight_labels()
            self.status_label.config(text="DnCNN pronto")
        except Exception:
            self.status_label.config(text="Falha ao aplicar DnCNN")

    def _apply_swinir_choice(self):
        try:
            selection = self.swinir_choice_var.get()
            if selection.startswith("Auto"):
                if hasattr(self.model_pipeline, "refresh_swinir"):
                    self.model_pipeline.refresh_swinir()
            else:
                path = self.model_pipeline.get_swinir_weight_path(selection)
                if path:
                    self.model_pipeline.set_swinir_weights(path)
            self._update_model_menu()
            self.status_label.config(text="SwinIR pronto")
        except Exception:
            self.status_label.config(text="Falha ao aplicar SwinIR")

    def _apply_restormer_choice(self):
        try:
            selection = self.restormer_choice_var.get()
            if selection.startswith("Auto"):
                if hasattr(self.model_pipeline, "refresh_restormer"):
                    self.model_pipeline.refresh_restormer()
            else:
                path = self.model_pipeline.get_restormer_weight_path(selection)
                if path:
                    self.model_pipeline.set_restormer_weights(path)
            self._update_model_menu()
            self.status_label.config(text="Restormer pronto")
        except Exception:
            self.status_label.config(text="Falha ao aplicar Restormer")

    def _custom_weight_mapping(self, label: str) -> dict:
        value = (label or "").strip().lower()
        if "swinir" in value:
            return {"prefix": "swinir_", "folder": "swinir"}
        if "restormer" in value:
            return {"prefix": "restormer_", "folder": "restormer"}
        if "dncnn" in value:
            return {"prefix": "dncnn_", "folder": "dncnn"}
        return {"prefix": "rrdb_", "folder": "rrdb"}

    def add_custom_weight_action(self):
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
            mapping = self._custom_weight_mapping(self.custom_weight_type_var.get())
            prefix = mapping["prefix"]
            folder = mapping["folder"]

            dest_root = os.path.join(self.repo_root, "src", "models", "custom", folder)
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
            if hasattr(self, "status_label"):
                self.status_label.config(text=f"Peso adicionado: {os.path.basename(dest_path)}")
            self.refresh_models(silent=True)
        except Exception as e:
            messagebox.showerror("Erro", f"Nao foi possivel adicionar o peso: {e}")

    def _sync_model_weight_labels(self):
        try:
            info = self.model_pipeline.get_weights_info() if self.model_pipeline else {}
            if info.get("unet"):
                self.unet_weights_var.set(os.path.basename(info["unet"]))
            if info.get("dncnn"):
                self.dncnn_weights_var.set(os.path.basename(info["dncnn"]))
            if info.get("sr") or info.get("swinir"):
                self._update_upscale_info_label()
        except Exception:
            pass

    def _update_model_menu(self):
        if not hasattr(self, "model_menu"):
            return
        try:
            models = self.model_pipeline.available_models() if self.model_pipeline else []
            available = ["None"]
            missing = []
            for info in models:
                if info.name == "None":
                    continue
                if info.available:
                    available.append(info.name)
                else:
                    missing.append(f"{info.name}: {info.reason}")
            if self.model_name_var.get() not in available:
                self.model_name_var.set("None")
            menu = self.model_menu["menu"]
            menu.delete(0, "end")
            for name in available:
                menu.add_command(label=name, command=lambda v=name: self.model_name_var.set(v))
            if hasattr(self, "model_status_var"):
                if missing:
                    self.model_status_var.set(" | ".join(missing))
                else:
                    self.model_status_var.set("Modelos prontos")
        except Exception:
            pass

    def refresh_models(self, silent=False):
        try:
            if self.model_pipeline:
                self.model_pipeline.refresh()
            self._sync_model_weight_labels()
            self._update_model_menu()
            self._update_dncnn_list()
            self._update_swinir_list()
            self._update_restormer_list()
            self._update_upscale_list()
            if (not silent) and hasattr(self, "status_label"):
                self.status_label.config(text="Modelos atualizados")
        except Exception:
            if (not silent) and hasattr(self, "status_label"):
                self.status_label.config(text="Falha ao atualizar modelos")

    def _update_dncnn_list(self):
        if not hasattr(self, "dncnn_choice_combo"):
            return
        try:
            names = self.model_pipeline.list_dncnn_weights() if self.model_pipeline else []
            values = ["Auto (melhor)"] + names
            self.dncnn_choice_combo["values"] = values
            current = self.dncnn_weights_var.get()
            if current in names:
                self.dncnn_choice_var.set(current)
            else:
                self.dncnn_choice_var.set(values[0])
        except Exception:
            pass

    def _update_swinir_list(self):
        if not hasattr(self, "swinir_choice_combo"):
            return
        try:
            names = self.model_pipeline.list_swinir_weights() if self.model_pipeline else []
            values = ["Auto (melhor)"] + names
            self.swinir_choice_combo["values"] = values
            if self.swinir_choice_var.get() not in values:
                self.swinir_choice_var.set(values[0])
        except Exception:
            pass

    def _update_restormer_list(self):
        if not hasattr(self, "restormer_choice_combo"):
            return
        try:
            names = self.model_pipeline.list_restormer_weights() if self.model_pipeline else []
            values = ["Auto (melhor)"] + names
            self.restormer_choice_combo["values"] = values
            if self.restormer_choice_var.get() not in values:
                self.restormer_choice_var.set(values[0])
        except Exception:
            pass

    def _update_upscale_info_label(self, override_text=None):
        if not hasattr(self, "upscale_info_var"):
            return
        if override_text:
            try:
                self.upscale_info_var.set(override_text)
                return
            except Exception:
                return
        try:
            engine = self._get_upscale_engine()
            if engine == "swinir":
                info = self.model_pipeline.get_swinir_info() if self.model_pipeline else {}
                name = info.get("name") if info else ""
                scale = info.get("scale") if info else None
                task = info.get("task") if info else None
                if not scale:
                    scale = self._get_selected_upscale_scale()
                if name:
                    mode_label = task if task else "sr"
                    label = f"SwinIR {mode_label} x{scale or '?'} - {name}"
                else:
                    label = "SwinIR - sem peso"
                    if scale:
                        label = f"SwinIR - sem peso x{scale}"
            else:
                info = self.model_pipeline.get_sr_info() if self.model_pipeline else {}
                name = info.get("name") if info else ""
                scale = info.get("scale") if info else None
                if not scale:
                    scale = self._get_selected_upscale_scale()
                if name:
                    label = f"RRDB x{scale or '?'} - {name}"
                else:
                    label = "RRDB - sem peso"
                    if scale:
                        label = f"RRDB - sem peso x{scale}"
            self.upscale_info_var.set(label)
        except Exception:
            pass

    def _update_upscale_list(self):
        if not hasattr(self, "upscale_combo"):
            return
        try:
            scale = self._get_selected_upscale_scale()
            engine = self._get_upscale_engine()
            if engine == "swinir":
                if scale:
                    names = self.model_pipeline.list_swinir_sr_weights(scale=scale) if self.model_pipeline else []
                else:
                    names = self.model_pipeline.list_swinir_sr_weights() if self.model_pipeline else []
            else:
                if scale:
                    names = self.model_pipeline.list_sr_weights_by_scale(scale) if self.model_pipeline else []
                else:
                    names = self.model_pipeline.list_sr_weights() if self.model_pipeline else []
            values = ["Auto (melhor)"] + names
            self.upscale_combo["values"] = values
            current = self.upscale_model_var.get()
            if current in names:
                self.upscale_model_var.set(current)
            else:
                self.upscale_model_var.set(values[0])
            if scale and not names:
                engine_label = "SwinIR" if engine == "swinir" else "RRDB"
                self._update_upscale_info_label(override_text=f"{engine_label} - sem peso x{scale}")
            else:
                self._update_upscale_info_label()
        except Exception:
            pass

    def _apply_selected_upscale(self):
        try:
            selection = self.upscale_model_var.get()
            if selection.startswith("Auto"):
                scale = self._get_selected_upscale_scale()
                engine = self._get_upscale_engine()
                if engine == "swinir":
                    if hasattr(self.model_pipeline, "auto_select_swinir_sr"):
                        self.model_pipeline.auto_select_swinir_sr(scale=scale)
                    elif hasattr(self.model_pipeline, "refresh_swinir"):
                        self.model_pipeline.refresh_swinir()
                else:
                    if hasattr(self.model_pipeline, "auto_select_sr"):
                        self.model_pipeline.auto_select_sr(scale=scale)
                    elif hasattr(self.model_pipeline, "refresh_sr"):
                        self.model_pipeline.refresh_sr()
            else:
                engine = self._get_upscale_engine()
                if engine == "swinir":
                    path = self.model_pipeline.get_swinir_weight_path(selection)
                    if path:
                        self.model_pipeline.set_swinir_weights(path)
                else:
                    path = self.model_pipeline.get_sr_weight_path(selection)
                    if path:
                        self.model_pipeline.set_sr_weights(path)
            self._update_upscale_info_label()
            self.status_label.config(text="Upscale pronto")
        except Exception:
            self.status_label.config(text="Falha ao aplicar upscale")

    def _get_upscale_engine(self):
        if not hasattr(self, "upscale_engine_var"):
            return "rrdb"
        value = (self.upscale_engine_var.get() or "").lower()
        if "swinir" in value:
            return "swinir"
        return "rrdb"

    def _get_selected_upscale_scale(self):
        if not hasattr(self, "upscale_scale_var"):
            return None
        value = (self.upscale_scale_var.get() or "").lower().strip()
        if value in ("x2", "2"):
            return 2
        if value in ("x4", "4"):
            return 4
        return None

    def _apply_upscale_quality(self):
        if not hasattr(self, "upscale_quality_var"):
            return
        value = (self.upscale_quality_var.get() or "").strip().lower()
        if value == "rapido":
            self.upscale_tile_var.set(320)
            self.upscale_overlap_var.set(16)
        elif value == "maximo":
            self.upscale_tile_var.set(192)
            self.upscale_overlap_var.set(32)
        else:
            self.upscale_tile_var.set(256)
            self.upscale_overlap_var.set(24)

    def _models_scan_mtime(self):
        latest = 0.0
        roots = getattr(self, "model_roots", []) or []
        for root in roots:
            try:
                latest = max(latest, os.path.getmtime(root))
            except Exception:
                pass
            try:
                for name in os.listdir(root):
                    path = os.path.join(root, name)
                    try:
                        latest = max(latest, os.path.getmtime(path))
                    except Exception:
                        pass
            except Exception:
                pass
        return latest

    def _watch_models(self):
        try:
            latest = self._models_scan_mtime()
            if latest > self._models_last_mtime:
                self._models_last_mtime = latest
                self.refresh_models(silent=True)
        except Exception:
            pass
        try:
            self.root.after(4000, self._watch_models)
        except Exception:
            pass

    def _start_models_watch(self):
        try:
            self._models_last_mtime = self._models_scan_mtime()
            self.root.after(4000, self._watch_models)
        except Exception:
            pass

    def open_dncnn_kair(self):
        try:
            import webbrowser
            webbrowser.open("https://github.com/cszn/KAIR#model-zoo")
            webbrowser.open("https://drive.google.com/drive/folders/13kfr3qny7S2xwG9h7v95F5mkWs0OmU0D")
            if hasattr(self, "status_label"):
                self.status_label.config(text="Abrindo KAIR Model Zoo...")
        except Exception:
            if hasattr(self, "status_label"):
                self.status_label.config(text="Nao foi possivel abrir o link do KAIR")

    def render_restored_video_action(self):
        if not os.path.exists(self.restored_dir):
            messagebox.showwarning("Aviso", "Nenhum frame restaurado encontrado.")
            return

        export_dir = os.path.join(self.project_manager.current_project_path, "exports", "renders")
        export_settings = ExportDialog(self.root, export_dir, "Exportar vídeo restaurado").show()
        if not export_settings:
            return
        output_path = export_settings["output_path"]
        export_profile = export_settings["profile"]
        preserve_audio = export_settings["preserve_audio"]
        fps = 30
        video_path = self._original_video_path()
        if video_path:
            fps = self.video_processor.get_video_info(video_path).get("fps", 30) or 30
        frames_source = self.restored_dir
        if self.use_manual_stab_var.get() and os.path.exists(self.manual_stab_dir):
            frames_source = self.manual_stab_dir
        elif self.use_auto_stab_var.get() and os.path.exists(self.auto_stab_dir):
            frames_source = self.auto_stab_dir
        if self.use_upscale_render_var.get() and os.path.exists(self.upscaled_dir):
            frames_source = self.upscaled_dir
        render_range = bool(self.render_range_var.get())
        stabilize = bool(self.stabilize_render_var.get())
        frames = list(self.frame_manager.frames)
        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            start, end = 0, len(frames) - 1

        def render_task(context):
            source = frames_source
            if render_range:
                temp_dir = os.path.join(self.video_renderer.temp_dir, "render_range")
                os.makedirs(temp_dir, exist_ok=True)
                for filename in os.listdir(temp_dir):
                    path = os.path.join(temp_dir, filename)
                    if os.path.isfile(path):
                        os.remove(path)
                indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))
                output_index = 1
                for position, frame_index in enumerate(indices):
                    context.check_cancelled()
                    frame_path = os.path.join(source, frames[frame_index])
                    image = cv2.imread(frame_path, cv2.IMREAD_COLOR)
                    if image is None:
                        continue
                    destination = os.path.join(temp_dir, f"frame_{output_index:06d}.png")
                    if not cv2.imwrite(destination, image):
                        raise RuntimeError(f"Não foi possível preparar {destination}")
                    output_index += 1
                    context.report(
                        (position + 1) * 35.0 / max(1, len(indices)),
                        f"Preparando intervalo — {position + 1}/{len(indices)}",
                    )
                source = temp_dir

            if stabilize:
                temp_stabilized = os.path.join(self.video_renderer.temp_dir, "stabilized_frames")
                success = self.video_renderer.stabilize_frames_ecc(
                    source,
                    temp_stabilized,
                    progress_callback=lambda progress: context.report(
                        35.0 + progress * 0.45,
                        f"Estabilizando para exportação — {progress:.0f}%",
                    ),
                )
                if success:
                    source = temp_stabilized
            context.check_cancelled()
            context.report(85, "Codificando vídeo e áudio...")
            success = self.video_renderer.render_frames_to_video(
                source,
                output_path,
                fps=fps,
                profile=export_profile,
                audio_source=video_path,
                audio_start=max(0, start) / fps if render_range else 0.0,
                preserve_audio=preserve_audio,
                progress_callback=lambda progress: context.report(
                    85.0 + progress * 0.13,
                    f"Codificando vídeo e áudio — {progress:.0f}%",
                ),
                cancel_callback=lambda: context.cancellation_requested,
            )
            if not success:
                raise RuntimeError("Falha ao codificar o vídeo")
            context.report(98, "Finalizando arquivo...")
            return output_path

        def render_complete(path):
            messagebox.showinfo("Render concluído", f"Vídeo salvo em:\n{path}")

        self._start_ui_job("Renderização final", render_task, render_complete)

    def _original_video_path(self):
        if self.current_video:
            candidate = os.path.join(self.project_manager.get_originals_dir(), self.current_video)
            if os.path.isfile(candidate):
                return candidate
        if self.current_video_path and os.path.isfile(self.current_video_path):
            return self.current_video_path
        return None

    def preview_from_frames_action(self):
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showwarning("Aviso", "Nenhum frame encontrado.")
            return

        output_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("All files", "*.*")]
        )
        if not output_path:
            return

        try:
            start = int(self.range_start_entry.get()) - 1
            end = int(self.range_end_entry.get()) - 1
        except ValueError:
            start = max(0, self.frame_manager.current_frame_index - 60)
            end = min(len(self.frame_manager.frames) - 1, self.frame_manager.current_frame_index + 60)

        frames_source = self.restored_dir if os.path.exists(self.restored_dir) and self.view_mode != "original" else self.frame_manager.frames_dir
        if self.use_manual_stab_var.get() and os.path.exists(self.manual_stab_dir):
            frames_source = self.manual_stab_dir
        elif self.use_auto_stab_var.get() and os.path.exists(self.auto_stab_dir):
            frames_source = self.auto_stab_dir
        if self.use_upscale_render_var.get() and os.path.exists(self.upscaled_dir):
            frames_source = self.upscaled_dir
        frames = list(self.frame_manager.frames)
        fps = 30
        video_path = self._original_video_path()
        if video_path:
            fps = self.video_processor.get_video_info(video_path).get("fps", 30) or 30

        def preview_task(context):
            temp_dir = os.path.join(self.video_renderer.temp_dir, "preview_frames")
            os.makedirs(temp_dir, exist_ok=True)
            for filename in os.listdir(temp_dir):
                path = os.path.join(temp_dir, filename)
                if os.path.isfile(path):
                    os.remove(path)
            indices = list(range(max(0, start), min(end, len(frames) - 1) + 1))
            output_index = 1
            for position, frame_index in enumerate(indices):
                context.check_cancelled()
                source = os.path.join(frames_source, frames[frame_index])
                image = cv2.imread(source, cv2.IMREAD_COLOR)
                if image is None:
                    continue
                destination = os.path.join(temp_dir, f"frame_{output_index:06d}.png")
                if not cv2.imwrite(destination, image):
                    raise RuntimeError(f"Não foi possível preparar {destination}")
                output_index += 1
                context.report(
                    (position + 1) * 75.0 / max(1, len(indices)),
                    f"Preparando preview — {position + 1}/{len(indices)}",
                )
            context.report(85, "Codificando preview...")
            success = self.video_renderer.render_frames_to_video(
                temp_dir,
                output_path,
                fps=fps,
                codec="h264",
                audio_source=video_path,
                audio_start=max(0, start) / fps,
                preserve_audio=True,
                progress_callback=lambda progress: context.report(
                    85.0 + progress * 0.13,
                    f"Codificando preview — {progress:.0f}%",
                ),
                cancel_callback=lambda: context.cancellation_requested,
            )
            if not success:
                raise RuntimeError("Falha ao codificar o preview")
            return output_path

        def preview_complete(path):
            messagebox.showinfo("Preview concluído", f"Preview salvo em:\n{path}")

        self._start_ui_job("Geração de preview", preview_task, preview_complete)

    def delete_frame(self):
        if self.frame_manager and messagebox.askyesno("Confirmar", "Excluir frame atual?"):
            if self.frame_manager.delete_current_frame():
                self.show_current_frame()
                self.update_frame_counter()
                self.status_var.set("Frame excluído!")

    def duplicate_frame(self):
        if self.frame_manager:
            if self.frame_manager.duplicate_frame():
                self.show_current_frame()
                self.update_frame_counter()
                self.status_var.set("Frame duplicado!")

    def renumber_frames(self):
        if self.frame_manager and messagebox.askyesno("Confirmar", "Renumerar todos os frames?"):
            if self.frame_manager.renumber_frames():
                self.show_current_frame()
                self.update_frame_counter()
                self.status_var.set("Frames renumerados!")

    # Processing actions
    def cut_video_action(self):
        if not self.current_video:
            messagebox.showwarning("Aviso", "Selecione um vídeo primeiro.")
            return

        try:
            start_time = float(self.start_time_entry.get())
            end_time = float(self.end_time_entry.get())
        except ValueError:
            messagebox.showerror("Erro", "Insira valores numéricos válidos.")
            return

        if start_time >= end_time:
            messagebox.showerror("Erro", "O tempo de início deve ser menor que o tempo de fim.")
            return

        self._cut_video_thread(start_time, end_time)

    def _cut_video_thread(self, start_time, end_time):
        project_path = self.project_manager.get_current_project_path()
        input_path = os.path.join(self.project_manager.get_originals_dir(), self.current_video)
        exports_dir = self.project_manager.get_exports_dir()
        output_path = os.path.join(
            exports_dir, 'renders', f'cut_{start_time}_{end_time}_{self.current_video}'
        )
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        def cut_task(context):
            try:
                success = self.video_processor.cut_video(
                    input_path,
                    output_path,
                    start_time,
                    end_time,
                    progress_callback=lambda progress: context.report(
                        progress, "Cortando vídeo..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            except ProcessingCancelled:
                context.check_cancelled()
                raise
            if not success:
                context.check_cancelled()
                raise RuntimeError("Falha ao cortar vídeo")
            return output_path

        def cut_complete(_path):
            messagebox.showinfo("Sucesso", "Vídeo cortado com sucesso!")

        self._start_ui_job("Corte", cut_task, cut_complete)

    def extract_frames_action(self):
        if not self.current_video:
            messagebox.showwarning("Aviso", "Selecione um vídeo primeiro.")
            return
        if hasattr(self, "extract_btn"):
            self.extract_btn.config(state=tk.DISABLED, text="Extraindo...")
        self.status_var.set("Extraindo frames... Aguarde")
        self._extract_frames_thread()

    def show_extraction_options(self):
        target_video = self.current_video or self._selected_media_video()
        if not target_video:
            messagebox.showwarning(
                "Escolha uma fonte",
                "Selecione um vídeo na árvore de mídia antes de extrair os frames.",
            )
            return
        if self.current_video != target_video:
            self.load_video(target_video)
        originals_dir = self.project_manager.get_originals_dir()
        frames_dir = self.project_manager.get_frames_dir(self.current_video)
        video_path = os.path.join(originals_dir, self.current_video)
        video_info = self.video_processor.get_video_info(video_path)

        def start_extraction(fps_value):
            self.fps_entry.delete(0, tk.END)
            self.fps_entry.insert(0, fps_value)
            self.extract_frames_action()

        ExtractionDialog(
            self.root,
            video_info,
            self.fps_entry.get().strip() or "Original",
            start_extraction,
            frames_dir,
        )

    def _extract_frames_thread(self):
        project_path = self.project_manager.get_current_project_path()
        input_path = os.path.join(self.project_manager.get_originals_dir(), self.current_video)
        frames_dir = self.project_manager.get_frames_dir(self.current_video)
        self.frame_manager.set_frames_dir(frames_dir)
        fps_text = self.fps_entry.get().strip()
        if not fps_text or fps_text.lower() in {"original", "orig", "fonte"}:
            fps = None
        else:
            try:
                fps = float(fps_text)
            except ValueError:
                messagebox.showerror(
                    "FPS inválido",
                    "Use 'Original' para preservar o vídeo ou informe um número, como 24 ou 30.",
                )
                self.extract_btn.config(
                    state=tk.NORMAL, text=self.extract_btn_default_text
                )
                return
            if fps <= 0 or fps > 240:
                messagebox.showerror("FPS inválido", "Informe um valor entre 0 e 240.")
                self.extract_btn.config(
                    state=tk.NORMAL, text=self.extract_btn_default_text
                )
                return

        def extract_task(context):
            try:
                video_info = self.video_processor.get_video_info(input_path)
                effective_fps = fps or float(video_info.get("fps", 0) or 0)
                estimated_bytes = estimate_lossless_frames_bytes(
                    float(video_info.get("duration", 0) or 0),
                    effective_fps,
                    int(video_info.get("width", 0) or 0),
                    int(video_info.get("height", 0) or 0),
                )
                require_free_space(frames_dir, estimated_bytes)
                success = self.video_processor.extract_frames(
                    input_path,
                    frames_dir,
                    frame_rate=fps,
                    progress_callback=lambda progress: context.report(
                        progress, "Extraindo frames sem perda..."
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                    lossless=True,
                )
            except ProcessingCancelled:
                context.check_cancelled()
                raise
            if not success:
                context.check_cancelled()
                raise RuntimeError("Falha ao extrair frames")
            return True

        def extract_complete(_result):
            if self.frame_manager is None:
                self.frame_manager = FrameManager(project_path)
            self.frame_manager.set_frames_dir(frames_dir)
            self.frame_manager.refresh_frames_list()
            self.total_frames = self.frame_manager.get_frame_count()
            self.current_frame = self.frame_manager.current_frame_index
            self.load_project_videos()
            self.select_media_video(self.current_video)
            self.notebook.select(1)
            self.show_current_frame()
            self.update_frame_counter()
            messagebox.showinfo(
                "Frames prontos",
                f"{self.total_frames} frames foram extraídos sem perda.\n\n"
                "Eles agora aparecem em páginas na árvore de mídia.",
            )

        def extract_failed(error):
            messagebox.showerror("Erro", f"Erro ao extrair frames: {error}")

        job = self._start_ui_job(
            "Extração",
            extract_task,
            extract_complete,
            extract_failed,
            lambda: self.extract_btn.config(
                state=tk.NORMAL, text=self.extract_btn_default_text
            ),
        )
        if job is None:
            self.extract_btn.config(state=tk.NORMAL, text=self.extract_btn_default_text)

    def cut_video_tool(self):
        self.notebook.select(2)

    def extract_frames_tool(self):
        """Extract frames with FFmpeg configuration dialog"""
        if not self.current_video_path:
            messagebox.showerror("Erro", "Nenhum vídeo selecionado!")
            return

        # Show FFmpeg configuration dialog
        dialog = FFmpegConfigDialog(self.root, self.current_video_path, self.project_manager)
        result = dialog.show()

        if result:
            # Extract frames with custom configuration
            self.extract_frames_with_config(result['config'])

    def extract_frames_with_config(self, config):
        """Extract frames using custom FFmpeg configuration"""
        command = config['command']
        self.logger.log_ffmpeg_command(command, "custom frame extraction")

        def extraction_task(context):
            import subprocess

            context.report(5, "Iniciando FFmpeg com configuração personalizada...")
            result = subprocess.run(command, shell=True, capture_output=True, text=True)
            context.check_cancelled()
            if result.returncode != 0:
                raise RuntimeError(result.stderr[-2000:] or "FFmpeg retornou erro")
            context.report(95, "Atualizando índice de frames...")
            return True

        def extraction_complete(_result):
            self.frame_manager.refresh_frame_list()
            self.total_frames = len(self.frame_manager.frames)
            self.project_state.update_video_info(self.current_video_path, self.total_frames)
            self.show_current_frame()
            self.update_frame_counter()

        self._start_ui_job("Extração personalizada", extraction_task, extraction_complete)

    def generate_mask_tool(self):
        """Generate dirt masks for frames"""
        if not self.frame_manager or not self.frame_manager.frames:
            messagebox.showerror("Erro", "Nenhum frame encontrado!")
            return

        def mask_task(context):
            context.report(5, "Analisando frames para detectar sujeiras...")
            success = self.mask_generator.generate_mask_for_project(
                self.project_manager.current_project_path,
                frames_dir=self.frame_manager.frames_dir,
                masks_dir=self.auto_masks_dir,
            )
            context.check_cancelled()
            if not success:
                raise RuntimeError("Não foi possível gerar as máscaras")
            context.report(95, "Organizando máscaras detectadas...")
            return True

        def mask_complete(_result):
            self.show_auto_mask_var.set(True)
            self.show_current_frame()
            self.logger.info("Dirt masks generated successfully")

        self._start_ui_job("Detecção de sujeiras", mask_task, mask_complete)

    def render_tool(self):
        """Render restored video from frames"""
        self.render_restored_video_action()

    def show_render_options(self):
        """Show render options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Opções de Renderização")
        dialog.geometry("560x520")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (250)
        y = (dialog.winfo_screenheight() // 2) - (200)
        dialog.geometry(f"560x520+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Render type
        ttk.Label(main_frame, text="Tipo de Renderização:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        render_type = tk.StringVar(value="full")
        ttk.Radiobutton(main_frame, text="Renderizar Projeto Inteiro", variable=render_type, value="full").pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text="Renderizar Segmento Selecionado", variable=render_type, value="segment").pack(anchor=tk.W, pady=5)
        ttk.Radiobutton(main_frame, text="Preview com Máscaras", variable=render_type, value="preview_masks").pack(anchor=tk.W, pady=5)

        # Output settings
        ttk.Label(main_frame, text="Configurações de Saída:", font=('Arial', 12, 'bold')).pack(pady=(20, 10))

        # Output path
        ttk.Label(main_frame, text="Arquivo de saída:").pack(anchor=tk.W)
        output_path = tk.StringVar()
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(5, 10))

        ttk.Entry(path_frame, textvariable=output_path, width=40).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="...", command=lambda: self.browse_output_file(output_path)).pack(side=tk.RIGHT, padx=(5, 0))

        # Processing options
        ttk.Label(main_frame, text="Opções de Processamento:", font=('Arial', 12, 'bold')).pack(pady=(20, 10))

        apply_processing = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Aplicar restauração temporal", variable=apply_processing).pack(anchor=tk.W, pady=5)

        preserve_audio = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Incluir áudio original", variable=preserve_audio).pack(anchor=tk.W, pady=5)

        ttk.Label(main_frame, text="Perfil de exportação:", font=('Arial', 11, 'bold')).pack(anchor=tk.W, pady=(15, 5))
        export_profile = tk.StringVar(value="delivery")
        ttk.Combobox(
            main_frame,
            textvariable=export_profile,
            state="readonly",
            values=("delivery", "mezzanine", "archive"),
        ).pack(fill=tk.X)
        ttk.Label(
            main_frame,
            text="delivery = MP4 compatível; mezzanine = ProRes; archive = FFV1 sem perda",
            wraplength=500,
        ).pack(anchor=tk.W, pady=(4, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(
            button_frame,
            text="Renderizar",
            command=lambda: self.start_render(
                render_type.get(),
                output_path.get(),
                apply_processing.get(),
                dialog,
                export_profile.get(),
                preserve_audio.get(),
            ),
        ).pack(side=tk.RIGHT)

    def browse_output_file(self, path_var):
        """Browse for output file"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".mp4",
            filetypes=[("MP4 files", "*.mp4"), ("AVI files", "*.avi"), ("All files", "*.*")]
        )
        if file_path:
            path_var.set(file_path)

    def start_render(
        self,
        render_type,
        output_path,
        apply_processing,
        dialog,
        export_profile="delivery",
        preserve_audio=True,
    ):
        """Start rendering process"""
        if not output_path:
            messagebox.showerror("Erro", "Selecione um arquivo de saída!")
            return
        if render_type == "segment":
            messagebox.showinfo("Info", "Use a seleção de frames e a opção Preview para gerar um segmento.")
            return
        extension = {"delivery": ".mp4", "mezzanine": ".mov", "archive": ".mkv"}.get(
            export_profile, ".mp4"
        )
        output_path = os.path.splitext(output_path)[0] + extension
        dialog.destroy()
        processing_settings = self.project_state.get_processing_settings()

        def render_task(context):
            context.report(10, "Preparando fontes para renderização...")
            if render_type == "full":
                render_frames = self.restored_dir if os.path.isdir(self.restored_dir) else self.frame_manager.frames_dir
                success = self.video_renderer.render_full_project(
                    self.project_manager.current_project_path,
                    output_path,
                    apply_processing,
                    processing_settings,
                    frames_dir=render_frames,
                    profile=export_profile,
                    audio_source=self._original_video_path(),
                    preserve_audio=preserve_audio,
                    progress_callback=lambda progress: context.report(
                        10.0 + progress * 0.85,
                        f"Codificando vídeo e áudio — {progress:.0f}%",
                    ),
                    cancel_callback=lambda: context.cancellation_requested,
                )
            else:
                success = self.video_renderer.create_preview_with_masks(
                    self.frame_manager.frames_dir, self.masks_dir, output_path
                )
            context.check_cancelled()
            if not success:
                raise RuntimeError("Falha na renderização")
            context.report(95, "Finalizando arquivo renderizado...")
            return output_path

        def render_complete(path):
            self.logger.info(f"Video rendered to {path}")
            messagebox.showinfo("Renderização concluída", f"Vídeo salvo em:\n{path}")

        self._start_ui_job("Renderização", render_task, render_complete)

    def preview_tool(self):
        """Create preview from frames (original/restored)"""
        self.preview_from_frames_action()

    def show_preview_options(self):
        """Show preview options dialog"""
        dialog = tk.Toplevel(self.root)
        dialog.title("Opções de Preview")
        dialog.geometry("400x300")
        dialog.transient(self.root)
        dialog.grab_set()

        # Center dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (200)
        y = (dialog.winfo_screenheight() // 2) - (150)
        dialog.geometry(f"400x300+{x}+{y}")

        main_frame = ttk.Frame(dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Time selection
        ttk.Label(main_frame, text="Segmento para Preview:", font=('Arial', 12, 'bold')).pack(pady=(0, 10))

        time_frame = ttk.Frame(main_frame)
        time_frame.pack(fill=tk.X, pady=(0, 20))

        ttk.Label(time_frame, text="Início (segundos):").grid(row=0, column=0, sticky=tk.W)
        start_time = tk.DoubleVar(value=0.0)
        ttk.Spinbox(time_frame, from_=0, to=3600, textvariable=start_time, width=10).grid(row=0, column=1, padx=(10, 0))

        ttk.Label(time_frame, text="Duração (segundos):").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        duration = tk.DoubleVar(value=10.0)
        ttk.Spinbox(time_frame, from_=1, to=60, textvariable=duration, width=10).grid(row=1, column=1, padx=(10, 0), pady=(10, 0))

        # Processing options
        apply_processing = tk.BooleanVar(value=True)
        ttk.Checkbutton(main_frame, text="Aplicar processamento", variable=apply_processing).pack(anchor=tk.W, pady=(0, 20))

        # Output path
        ttk.Label(main_frame, text="Arquivo de preview:").pack(anchor=tk.W)
        preview_path = tk.StringVar()
        path_frame = ttk.Frame(main_frame)
        path_frame.pack(fill=tk.X, pady=(5, 20))

        ttk.Entry(path_frame, textvariable=preview_path, width=30).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(path_frame, text="...", command=lambda: self.browse_output_file(preview_path)).pack(side=tk.RIGHT, padx=(5, 0))

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(button_frame, text="Cancelar", command=dialog.destroy).pack(side=tk.RIGHT, padx=(10, 0))
        ttk.Button(button_frame, text="Gerar Preview", command=lambda: self.generate_preview(start_time.get(), duration.get(), preview_path.get(), apply_processing.get(), dialog)).pack(side=tk.RIGHT)

    def generate_preview(self, start_time, duration, output_path, apply_processing, dialog):
        """Generate preview of video segment"""
        if not output_path:
            messagebox.showerror("Erro", "Selecione um arquivo de saída!")
            return
        dialog.destroy()
        processing_config = self.project_state.get_processing_settings() if apply_processing else None
        video_path = self.current_video_path
        if not video_path and self.current_video:
            video_path = os.path.join(self.project_manager.get_originals_dir(), self.current_video)

        def preview_task(context):
            context.report(10, "Preparando segmento de preview...")
            success = self.video_renderer.render_segment_preview(
                video_path,
                start_time,
                duration,
                output_path,
                apply_processing,
                processing_config,
            )
            context.check_cancelled()
            if not success:
                raise RuntimeError("Falha ao gerar preview")
            context.report(95, "Finalizando preview...")
            return output_path

        def preview_complete(path):
            self.logger.info(f"Preview generated: {path}")
            messagebox.showinfo("Preview concluído", f"Preview salvo em:\n{path}")

        self._start_ui_job("Preview de vídeo", preview_task, preview_complete)

    def restore_project_state(self):
        """Restore project state on startup"""
        try:
            # Restore current frame
            if self.total_frames > 0:
                self.current_frame = self.project_state.get_current_frame()
                if self.frame_manager:
                    self.frame_manager.current_frame_index = self.current_frame
                    self.frame_manager.display_current_frame()

                # Update UI
                self.update_frame_display()
                self.logger.info(f"Restored to frame {self.current_frame}")

        except Exception as e:
            self.logger.error(f"Error restoring project state: {e}")

    def update_frame_display(self):
        """Update frame display information"""
        if hasattr(self, 'frame_info_label'):
            self.frame_info_label.config(text=f"Frame: {self.current_frame + 1}/{self.total_frames}")

        if hasattr(self, 'frame_spinbox'):
            self.frame_spinbox.delete(0, tk.END)
            self.frame_spinbox.insert(0, str(self.current_frame + 1))

    def jump_to_frame(self, frame_number):
        """Jump to specific frame"""
        try:
            if 0 <= frame_number < self.total_frames:
                self.current_frame = frame_number
                self.project_state.update_current_frame(frame_number)

                if self.frame_manager:
                    self.frame_manager.current_frame_index = frame_number
                    self.frame_manager.display_current_frame()

                self.update_frame_display()
                self.logger.log_frame_operation(frame_number, "jump")
            else:
                messagebox.showerror("Erro", f"Frame {frame_number + 1} fora do intervalo!")

        except Exception as e:
            self.logger.error(f"Error jumping to frame {frame_number}: {e}")

    def save_project_state(self):
        """Save current project state"""
        try:
            self.project_state.update_current_frame(self.current_frame, self.total_frames)
            self.logger.info("Project state saved")
        except Exception as e:
            self.logger.error(f"Error saving project state: {e}")

    def on_closing(self):
        """Cleanup when closing"""
        try:
            if self._active_job_id:
                self.job_manager.cancel(self._active_job_id)
            self._thumb_worker_stop.set()
            if self._thumb_ready_job:
                self.root.after_cancel(self._thumb_ready_job)
                self._thumb_ready_job = None
            if self.progress_dialog:
                self.progress_dialog.close()
            # Save project state
            self.save_project_state()

            # Cleanup resources
            if self.video_player:
                self.video_player.release()
            if self._playback_ui_job:
                self.root.after_cancel(self._playback_ui_job)
                self._playback_ui_job = None
            self._stop_play_pulse()
            if self.video_renderer:
                self.video_renderer.cleanup_temp_directory()
            if self.project_manager:
                self.project_manager.close_project()

            self.logger.log_project_action("CLOSED", self.project['name'])

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
        finally:
            self.root.destroy()
