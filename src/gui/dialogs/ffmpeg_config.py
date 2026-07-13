"""
FFmpeg Configuration Dialog
Advanced FFmpeg settings configuration for video processing
"""

import tkinter as tk
from tkinter import ttk, messagebox
import json
import os
import subprocess
from typing import Dict, Optional

from core.paths import executable_path

class FFmpegConfigDialog:
    """Dialog for configuring FFmpeg settings"""

    def __init__(self, parent, video_path: str, project_manager):
        self.parent = parent
        self.video_path = video_path
        self.project_manager = project_manager
        self.result = None
        self.dialog = None

        # Default configuration
        project_path = getattr(self.project_manager, "current_project_path", None) or getattr(self.project_manager, "project_path", "projects")
        default_output_pattern = os.path.join(project_path, "frames", "frame_%06d.png")
        self.default_config = {
            'input': video_path,
            'qscale_v': 1,
            'scale_filter': 'lanczos',
            'width': 3840,
            'height': 2160,
            'fps': 60,
            'output_pattern': default_output_pattern,
            'custom_command': '',
            'use_custom': False
        }

        # Load saved config if exists
        self.config = self.load_config()

    def load_config(self) -> Dict:
        """Load saved configuration"""
        try:
            config_file = os.path.join(self.project_manager.project_path, 'ffmpeg_config.json')
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    saved_config = json.load(f)
                # Merge with defaults
                config = self.default_config.copy()
                config.update(saved_config)
                return config
        except Exception as e:
            pass
        return self.default_config.copy()

    def save_config(self):
        """Save current configuration"""
        try:
            config_file = os.path.join(self.project_manager.project_path, 'ffmpeg_config.json')
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            pass

    def generate_command(self) -> str:
        """Generate FFmpeg command from configuration"""
        if self.config.get('use_custom', False) and self.config.get('custom_command'):
            return self.config['custom_command']

        cmd_parts = [subprocess.list2cmdline([executable_path('ffmpeg')])]

        # Input
        cmd_parts.append(f"-i \"{self.config['input']}\"")

        # Quality
        cmd_parts.append(f"-qscale:v {self.config['qscale_v']}")

        # Video filter
        scale_filter = f"scale={self.config['width']}:{self.config['height']}:flags={self.config['scale_filter']}"
        fps_filter = f"fps={self.config['fps']}"
        vf_filter = f'"{scale_filter},{fps_filter}"'
        cmd_parts.append(f"-vf {vf_filter}")

        # Sync
        cmd_parts.append("-vsync 0")

        # Output
        cmd_parts.append(f"\"{self.config['output_pattern']}\"")

        return ' '.join(cmd_parts)

    def show(self) -> Optional[Dict]:
        """Show the configuration dialog"""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Configurações FFmpeg")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"800x600+{x}+{y}")

        self.setup_ui()

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def setup_ui(self):
        """Setup the dialog UI"""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Configurações de Processamento FFmpeg",
            font=('Arial', 14, 'bold')
        )
        title_label.pack(pady=(0, 20))

        # Video info
        video_info = ttk.Label(
            main_frame,
            text=f"Vídeo: {os.path.basename(self.video_path)}",
            font=('Arial', 10)
        )
        video_info.pack(pady=(0, 20))

        # Notebook for tabs
        notebook = ttk.Notebook(main_frame)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 20))

        # Presets tab
        presets_frame = ttk.Frame(notebook)
        notebook.add(presets_frame, text="Presets")
        self.setup_presets_tab(presets_frame)

        # Advanced tab
        advanced_frame = ttk.Frame(notebook)
        notebook.add(advanced_frame, text="Avançado")
        self.setup_advanced_tab(advanced_frame)

        # Custom command tab
        custom_frame = ttk.Frame(notebook)
        notebook.add(custom_frame, text="Comando Personalizado")
        self.setup_custom_tab(custom_frame)

        # Command preview
        self.setup_command_preview(main_frame)

        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))

        ttk.Button(
            button_frame,
            text="Cancelar",
            command=self.cancel
        ).pack(side=tk.RIGHT, padx=(10, 0))

        ttk.Button(
            button_frame,
            text="Processar",
            command=self.process
        ).pack(side=tk.RIGHT)

    def setup_presets_tab(self, parent):
        """Setup presets tab"""
        # Preset options
        presets_frame = ttk.LabelFrame(parent, text="Presets", padding="10")
        presets_frame.pack(fill=tk.X, padx=10, pady=10)

        # Preset selection
        ttk.Label(presets_frame, text="Selecione um preset:").pack(anchor=tk.W)

        self.preset_var = tk.StringVar(value="4K Ultra HD")
        presets = [
            ("4K Ultra HD (3840x2160)", "4K Ultra HD"),
            ("Full HD (1920x1080)", "Full HD"),
            ("HD (1280x720)", "HD"),
            ("SD (720x480)", "SD"),
            ("Personalizado", "Custom")
        ]

        for text, value in presets:
            ttk.Radiobutton(
                presets_frame,
                text=text,
                variable=self.preset_var,
                value=value,
                command=self.on_preset_change
            ).pack(anchor=tk.W, pady=2)

        # Quality settings
        quality_frame = ttk.LabelFrame(parent, text="Qualidade", padding="10")
        quality_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(quality_frame, text="Qualidade (qscale):").grid(row=0, column=0, sticky=tk.W)
        self.qscale_var = tk.IntVar(value=self.config['qscale_v'])
        qscale_scale = ttk.Scale(
            quality_frame,
            from_=1, to=31,
            variable=self.qscale_var,
            orient=tk.HORIZONTAL,
            length=200
        )
        qscale_scale.grid(row=0, column=1, padx=(10, 0))

        self.qscale_label = ttk.Label(quality_frame, text=str(self.qscale_var.get()))
        self.qscale_label.grid(row=0, column=2, padx=(10, 0))

        qscale_scale.configure(command=lambda v: self.qscale_label.configure(text=str(int(float(v)))))

        # FPS
        ttk.Label(quality_frame, text="FPS:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.fps_var = tk.IntVar(value=self.config['fps'])
        fps_spinbox = ttk.Spinbox(
            quality_frame,
            from_=1, to=60,
            textvariable=self.fps_var,
            width=10
        )
        fps_spinbox.grid(row=1, column=1, sticky=tk.W, padx=(10, 0), pady=(10, 0))

    def setup_advanced_tab(self, parent):
        """Setup advanced settings tab"""
        # Resolution
        resolution_frame = ttk.LabelFrame(parent, text="Resolução", padding="10")
        resolution_frame.pack(fill=tk.X, padx=10, pady=10)

        # Width
        ttk.Label(resolution_frame, text="Largura:").grid(row=0, column=0, sticky=tk.W)
        self.width_var = tk.IntVar(value=self.config['width'])
        ttk.Spinbox(
            resolution_frame,
            from_=320, to=7680,
            textvariable=self.width_var,
            width=15
        ).grid(row=0, column=1, padx=(10, 0))

        # Height
        ttk.Label(resolution_frame, text="Altura:").grid(row=1, column=0, sticky=tk.W, pady=(10, 0))
        self.height_var = tk.IntVar(value=self.config['height'])
        ttk.Spinbox(
            resolution_frame,
            from_=240, to=4320,
            textvariable=self.height_var,
            width=15
        ).grid(row=1, column=1, padx=(10, 0), pady=(10, 0))

        # Scale filter
        ttk.Label(resolution_frame, text="Filtro de Escala:").grid(row=2, column=0, sticky=tk.W, pady=(10, 0))
        self.scale_filter_var = tk.StringVar(value=self.config['scale_filter'])
        scale_combo = ttk.Combobox(
            resolution_frame,
            textvariable=self.scale_filter_var,
            values=['lanczos', 'bicubic', 'bilinear', 'neighbor', 'area'],
            state='readonly'
        )
        scale_combo.grid(row=2, column=1, padx=(10, 0), pady=(10, 0))

        # Output pattern
        output_frame = ttk.LabelFrame(parent, text="Padrão de Saída", padding="10")
        output_frame.pack(fill=tk.X, padx=10, pady=10)

        ttk.Label(output_frame, text="Padrão dos frames:").pack(anchor=tk.W)
        self.output_pattern_var = tk.StringVar(value=self.config['output_pattern'])
        ttk.Entry(
            output_frame,
            textvariable=self.output_pattern_var,
            width=50
        ).pack(fill=tk.X, pady=(5, 0))

    def setup_custom_tab(self, parent):
        """Setup custom command tab"""
        custom_frame = ttk.LabelFrame(parent, text="Comando FFmpeg Personalizado", padding="10")
        custom_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Enable custom command
        self.use_custom_var = tk.BooleanVar(value=self.config.get('use_custom', False))
        ttk.Checkbutton(
            custom_frame,
            text="Usar comando personalizado",
            variable=self.use_custom_var,
            command=self.on_custom_toggle
        ).pack(anchor=tk.W)

        # Custom command text
        ttk.Label(custom_frame, text="Comando FFmpeg:").pack(anchor=tk.W, pady=(10, 0))

        self.custom_text = tk.Text(custom_frame, height=10, wrap=tk.WORD)
        self.custom_text.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        self.custom_text.insert('1.0', self.config.get('custom_command', ''))

        # Enable/disable based on checkbox
        self.on_custom_toggle()

    def setup_command_preview(self, parent):
        """Setup command preview section"""
        preview_frame = ttk.LabelFrame(parent, text="Prévia do Comando", padding="10")
        preview_frame.pack(fill=tk.X, pady=(10, 0))

        self.command_preview = tk.Text(preview_frame, height=3, wrap=tk.WORD)
        self.command_preview.pack(fill=tk.X)

        # Update preview initially
        self.update_command_preview()

    def on_preset_change(self):
        """Handle preset selection change"""
        preset = self.preset_var.get()

        presets_config = {
            "4K Ultra HD": {'width': 3840, 'height': 2160, 'fps': 30},
            "Full HD": {'width': 1920, 'height': 1080, 'fps': 30},
            "HD": {'width': 1280, 'height': 720, 'fps': 30},
            "SD": {'width': 720, 'height': 480, 'fps': 30}
        }

        if preset in presets_config:
            config = presets_config[preset]
            self.width_var.set(config['width'])
            self.height_var.set(config['height'])
            self.fps_var.set(config['fps'])

        self.update_command_preview()

    def on_custom_toggle(self):
        """Handle custom command toggle"""
        use_custom = self.use_custom_var.get()
        self.custom_text.configure(state=tk.NORMAL if use_custom else tk.DISABLED)
        self.update_command_preview()

    def update_command_preview(self):
        """Update command preview"""
        # Update config from UI
        if not self.use_custom_var.get():
            self.config.update({
                'qscale_v': self.qscale_var.get(),
                'scale_filter': self.scale_filter_var.get(),
                'width': self.width_var.get(),
                'height': self.height_var.get(),
                'fps': self.fps_var.get(),
                'output_pattern': self.output_pattern_var.get(),
                'use_custom': False,
                'custom_command': ''
            })
        else:
            self.config.update({
                'use_custom': True,
                'custom_command': self.custom_text.get('1.0', tk.END).strip()
            })

        # Generate and display command
        command = self.generate_command()
        self.command_preview.delete('1.0', tk.END)
        self.command_preview.insert('1.0', command)

    def process(self):
        """Process with current configuration"""
        self.update_command_preview()

        # Validate configuration
        if self.use_custom_var.get():
            custom_cmd = self.custom_text.get('1.0', tk.END).strip()
            if not custom_cmd:
                messagebox.showerror("Erro", "Digite um comando FFmpeg personalizado.")
                return

        # Save configuration
        self.save_config()

        # Return result
        self.result = {
            'config': self.config.copy(),
            'command': self.generate_command()
        }

        self.dialog.destroy()

    def cancel(self):
        """Cancel dialog"""
        self.result = None
        self.dialog.destroy()
