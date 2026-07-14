"""
Project Manager GUI Module
Enhanced project management with GUI integration
"""

import os
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from lib.modules.project.manage import ProjectManager as BaseProjectManager
from lib.modules.project.workspace import ProjectWorkspace
from core.media_import import MediaImportPlan, WORKING_FORMATS
from core.storage import require_free_space

class ProjectManagerGUI(BaseProjectManager):
    """Enhanced Project Manager with GUI-specific features"""

    def __init__(self):
        super().__init__()
        self.current_project: Optional[Dict] = None
        self.current_project_path: Optional[str] = None
        self.workspace = None
        self.last_project_notice: Optional[Dict] = None
        self.last_imported_video_name: Optional[str] = None
        self.last_import_error: Optional[str] = None

    @property
    def external_projects_registry(self) -> Path:
        return Path(self.project_path) / ".external-projects.json"

    def list_projects_in_path(self) -> List[Dict]:
        """List local projects and registered external workspaces."""
        local_projects = super().list_projects_in_path()
        for project in local_projects:
            project["external"] = False

        external_projects = []
        valid_paths = []
        for registered_path in self._read_external_project_paths():
            project_path = Path(registered_path)
            metadata = self._read_project_metadata(project_path)
            if metadata is None:
                continue
            resolved_path = str(project_path.resolve())
            valid_paths.append(resolved_path)
            external_projects.append(
                {
                    "project_name": metadata["name"],
                    "project_path": resolved_path,
                    "created_at": metadata.get("created_at", ""),
                    "updated_at": metadata.get("updated_at", metadata.get("created_at", "")),
                    "creator": metadata.get("creator", "Desconhecido"),
                    "external": True,
                }
            )
        if valid_paths != self._read_external_project_paths():
            self._write_external_project_paths(valid_paths)
        projects = local_projects + external_projects
        projects.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
        return projects

    def register_external_project(self, project_folder: str) -> Optional[Dict]:
        """Register and load an existing workspace without copying its media."""
        project_path = Path(project_folder).expanduser().resolve()
        metadata = self._read_project_metadata(project_path)
        if metadata is None:
            return None

        projects_root = Path(self.project_path).expanduser().resolve()
        is_local = project_path.parent == projects_root
        if not is_local:
            registered = self._read_external_project_paths()
            path_value = str(project_path)
            if path_value not in registered:
                registered.append(path_value)
                self._write_external_project_paths(registered)
        return self.load_project(str(project_path))

    def _read_external_project_paths(self) -> List[str]:
        registry = self.external_projects_registry
        if not registry.is_file():
            return []
        try:
            data = json.loads(registry.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []
        values = data.get("projects", []) if isinstance(data, dict) else []
        return [value for value in values if isinstance(value, str)]

    def _write_external_project_paths(self, paths: List[str]) -> None:
        registry = self.external_projects_registry
        registry.parent.mkdir(parents=True, exist_ok=True)
        unique_paths = list(dict.fromkeys(paths))
        temporary = registry.with_suffix(".tmp")
        temporary.write_text(
            json.dumps({"schema_version": 1, "projects": unique_paths}, indent=2),
            encoding="utf-8",
        )
        temporary.replace(registry)

    @staticmethod
    def _read_project_metadata(project_path: Path) -> Optional[Dict]:
        metadata_path = project_path / "metadata" / "project.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        required_fields = {"name", "id", "created_at"}
        if not isinstance(metadata, dict) or not required_fields.issubset(metadata):
            return None
        return metadata

    def create_project_advanced(self, project_name: str, author: str = 'Anonymous',
                              description: str = '', settings: Dict = None) -> bool:
        """Create project with advanced options"""
        try:
            project_name = project_name.strip()
            if (
                not project_name
                or len(project_name) > 80
                or project_name in {'.', '..'}
                or os.path.basename(project_name) != project_name
                or '/' in project_name
                or '\\' in project_name
            ):
                return False
            # Create basic project structure
            success = self.create_project(project_name, author)
            if not success:
                return False

            # Add advanced settings
            project_path = os.path.join(self.project_path, project_name)
            metadata_path = os.path.join(project_path, 'metadata', 'project.json')

            # Load existing metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Add advanced fields
            metadata['description'] = description
            metadata['settings'] = settings or {}
            metadata['settings']['video_quality'] = metadata['settings'].get('video_quality', 'high')
            metadata['settings']['frame_extraction_fps'] = metadata['settings'].get('frame_extraction_fps', 1.0)
            metadata['settings']['output_resolution'] = metadata['settings'].get('output_resolution', 'original')
            metadata['settings']['gpu_acceleration'] = metadata['settings'].get('gpu_acceleration', True)
            metadata['project_format_version'] = 3
            metadata['workspace'] = 'metadata/workspace.json'

            # Save updated metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            if ProjectWorkspace is not None:
                ProjectWorkspace.initialize(project_path)

            return True

        except Exception as e:
            print(f"Error creating advanced project: {e}")
            return False

    def load_project(self, project_name: str) -> Optional[Dict]:
        """Load project and set as current"""
        try:
            reference = Path(project_name).expanduser()
            if reference.is_absolute():
                project_path = reference.resolve()
            else:
                project_path = (Path(self.project_path) / project_name).resolve()
            project_data = self._read_project_metadata(project_path)
            if project_data is None:
                return None

            if ProjectWorkspace is not None:
                self.workspace = ProjectWorkspace.initialize(str(project_path))
                self.last_project_notice = self._workspace_notice(self.workspace)

            self.current_project = project_data
            self.current_project_path = str(project_path)

            return project_data

        except Exception as e:
            print(f"Error loading project: {e}")
            return None

    @staticmethod
    def _workspace_notice(workspace) -> Optional[Dict]:
        report = getattr(workspace, "recovery_report", {})
        if report.get("recovered"):
            return {
                "kind": "recovered",
                "title": "Projeto recuperado com segurança",
                "message": (
                    "Uma gravação interrompida foi detectada. O Benedito restaurou "
                    "a última cópia íntegra e preservou o arquivo danificado para diagnóstico."
                ),
            }
        if report.get("migrations"):
            return {
                "kind": "migrated",
                "title": "Projeto atualizado",
                "message": (
                    "O formato deste projeto foi atualizado automaticamente. "
                    "O histórico, os frames e o material original foram preservados."
                ),
            }
        return None

    def get_current_project(self) -> Optional[Dict]:
        """Get currently loaded project"""
        return self.current_project

    def get_current_project_path(self) -> Optional[str]:
        """Get current project path"""
        return self.current_project_path

    def get_originals_dir(self) -> Optional[str]:
        if self.workspace is not None:
            return str(self.workspace.originals_dir)
        if self.current_project_path:
            return os.path.join(self.current_project_path, 'videos', 'original')
        return None

    def get_frames_dir(self, video_name: str = None) -> Optional[str]:
        if self.workspace is not None:
            if video_name:
                legacy_frames = any(
                    path.is_file()
                    and path.suffix.lower() in {'.jpg', '.jpeg', '.png'}
                    for path in self.workspace.frames_dir.iterdir()
                )
                if legacy_frames and len(self.get_project_videos()) <= 1:
                    return str(self.workspace.frames_dir)
            return str(self.workspace.get_frames_dir(video_name))
        if self.current_project_path:
            frames_dir = os.path.join(self.current_project_path, 'frames')
            if video_name:
                from core.media_browser import media_frame_directory_name

                frames_dir = os.path.join(
                    frames_dir, media_frame_directory_name(video_name)
                )
            os.makedirs(frames_dir, exist_ok=True)
            return frames_dir
        return None

    def get_exports_dir(self) -> Optional[str]:
        if self.workspace is not None:
            return str(self.workspace.exports_dir)
        if self.current_project_path:
            return os.path.join(self.current_project_path, 'exports')
        return None

    def add_video_to_project(self, video_path: str, video_name: str = None,
                             progress_callback=None, cancel_callback=None,
                             import_plan: MediaImportPlan = None,
                             video_processor=None) -> bool:
        """Add video to current project"""
        if not self.current_project:
            return False

        try:
            self.last_import_error = None
            self.last_imported_video_name = None
            # Generate video name if not provided
            if video_name is None:
                video_name = os.path.basename(video_path)

            if self.workspace is None and ProjectWorkspace is not None:
                self.workspace = ProjectWorkspace.initialize(self.current_project_path)

            if self.workspace is not None and import_plan and import_plan.is_segment:
                if video_processor is None or import_plan.end_time is None:
                    raise ValueError("Processador de vídeo indisponível para o trecho")
                video_name = import_plan.destination_name
                destination = Path(self.workspace.originals_dir) / video_name
                if destination.exists():
                    raise FileExistsError(f"Já existe um vídeo chamado {video_name}")
                require_free_space(destination.parent, import_plan.estimated_bytes)
                temporary = destination.with_name(
                    f".{destination.stem}.{uuid.uuid4().hex}{destination.suffix}"
                )
                format_info = WORKING_FORMATS[import_plan.working_format]
                try:
                    try:
                        success = video_processor.create_lossless_segment(
                            str(import_plan.source_path),
                            str(temporary),
                            import_plan.start_time,
                            import_plan.end_time,
                            progress_callback=(
                                (lambda value: progress_callback(value * 0.85))
                                if progress_callback else None
                            ),
                            cancel_callback=cancel_callback,
                            working_format=import_plan.working_format,
                            audio_mode=import_plan.audio_mode,
                        )
                        if not success:
                            raise RuntimeError("FFmpeg não conseguiu gerar o trecho")
                        os.replace(temporary, destination)
                        self.workspace.register_original(
                            destination,
                            progress_callback=(
                                (lambda value: progress_callback(85 + value * 0.15))
                                if progress_callback else None
                            ),
                            provenance={
                                "kind": "lossless-segment",
                                "source_name": import_plan.source_path.name,
                                "source_size": import_plan.source_path.stat().st_size,
                                "source_modified_ns": import_plan.source_path.stat().st_mtime_ns,
                                "start_time": import_plan.start_time,
                                "end_time": import_plan.end_time,
                                "working_format": import_plan.working_format,
                                "audio_mode": import_plan.audio_mode,
                                "container": destination.suffix.lower().lstrip("."),
                                "video_codec": format_info["video_codec"],
                                "audio_codec": format_info["audio_codec"],
                            },
                            cancel_callback=cancel_callback,
                        )
                    except Exception:
                        destination.unlink(missing_ok=True)
                        raise
                finally:
                    temporary.unlink(missing_ok=True)
            elif self.workspace is not None:
                self.workspace.import_original(
                    video_path,
                    destination_name=video_name,
                    progress_callback=progress_callback,
                    cancel_callback=cancel_callback,
                )
            else:
                import shutil
                videos_dir = os.path.join(self.current_project_path, 'videos', 'original')
                os.makedirs(videos_dir, exist_ok=True)
                shutil.copy2(video_path, os.path.join(videos_dir, video_name))

            # Update project metadata
            self._update_project_videos_list()
            self.last_imported_video_name = video_name

            return True

        except Exception as e:
            self.last_import_error = str(e)
            print(f"Error adding video to project: {e}")
            return False

    def _update_project_videos_list(self):
        """Update videos list in project metadata"""
        try:
            if not self.current_project_path:
                return

            metadata_path = os.path.join(self.current_project_path, 'metadata', 'project.json')

            # Get videos from directory
            videos_dir = self.get_originals_dir()
            videos = []

            if os.path.exists(videos_dir):
                videos = [f for f in os.listdir(videos_dir)
                         if f.lower().endswith(('.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv'))]

            # Update metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            metadata['videos'] = videos
            metadata['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Update current project
            self.current_project = metadata

        except Exception as e:
            print(f"Error updating videos list: {e}")

    def get_project_videos(self) -> List[str]:
        """Get list of videos in current project"""
        if not self.current_project:
            return []

        return self.current_project.get('videos', [])

    def get_project_settings(self) -> Dict:
        """Get project settings"""
        if not self.current_project:
            return {}

        return self.current_project.get('settings', {})

    def update_project_settings(self, settings: Dict) -> bool:
        """Update project settings"""
        if not self.current_project:
            return False

        try:
            metadata_path = os.path.join(self.current_project_path, 'metadata', 'project.json')

            # Load current metadata
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)

            # Update settings
            metadata['settings'].update(settings)
            metadata['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # Save metadata
            with open(metadata_path, 'w') as f:
                json.dump(metadata, f, indent=2)

            # Update current project
            self.current_project = metadata

            return True

        except Exception as e:
            print(f"Error updating project settings: {e}")
            return False

    def get_project_stats(self) -> Dict:
        """Get project statistics"""
        if not self.current_project:
            return {}

        try:
            stats = {
                'name': self.current_project.get('name', 'Unknown'),
                'created_at': self.current_project.get('created_at', ''),
                'updated_at': self.current_project.get('updated_at', ''),
                'creator': self.current_project.get('creator', 'Unknown'),
                'total_videos': len(self.get_project_videos()),
                'total_frames': 0,
                'project_size_mb': 0
            }

            # Count frames
            frames_dir = self.get_frames_dir()
            if os.path.exists(frames_dir):
                stats['total_frames'] = sum(
                    1
                    for path in Path(frames_dir).rglob("*")
                    if path.is_file()
                    and path.suffix.lower() in {'.jpg', '.jpeg', '.png'}
                )

            # Calculate project size
            project_size = 0
            for root, dirs, files in os.walk(self.current_project_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.exists(file_path):
                        project_size += os.path.getsize(file_path)

            stats['project_size_mb'] = project_size / (1024 * 1024)

            return stats

        except Exception as e:
            print(f"Error getting project stats: {e}")
            return {}

    def export_project_metadata(self, export_path: str) -> bool:
        """Export project metadata to JSON file"""
        if not self.current_project:
            return False

        try:
            with open(export_path, 'w') as f:
                json.dump(self.current_project, f, indent=2)
            return True

        except Exception as e:
            print(f"Error exporting project metadata: {e}")
            return False

    def import_project_metadata(self, import_path: str) -> bool:
        """Import project metadata from JSON file"""
        try:
            with open(import_path, 'r') as f:
                metadata = json.load(f)

            # Validate metadata structure
            required_fields = ['name', 'id', 'created_at']
            if not all(field in metadata for field in required_fields):
                return False

            # Save to current project
            if self.current_project_path:
                metadata_path = os.path.join(self.current_project_path, 'metadata', 'project.json')

                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f, indent=2)

                self.current_project = metadata
                return True

            return False

        except Exception as e:
            print(f"Error importing project metadata: {e}")
            return False

    def cleanup_project(self) -> bool:
        """Clean up project (remove empty directories, optimize storage)"""
        if not self.current_project_path:
            return False

        try:
            # Remove empty directories
            for root, dirs, files in os.walk(self.current_project_path, topdown=False):
                for dir_name in dirs:
                    dir_path = os.path.join(root, dir_name)
                    try:
                        if not os.listdir(dir_path):
                            os.rmdir(dir_path)
                    except:
                        pass

            # Update project metadata
            self._update_project_videos_list()

            return True

        except Exception as e:
            print(f"Error cleaning up project: {e}")
            return False

    def close_project(self):
        """Close current project"""
        self.current_project = None
        self.current_project_path = None
        self.workspace = None
