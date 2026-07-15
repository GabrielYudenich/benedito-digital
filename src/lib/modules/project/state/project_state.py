"""Project UI state persistence and recovery."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from lib.modules.project.recovery import (
    JsonRecoveryError,
    atomic_write_json,
    backup_path,
    load_json_with_recovery,
    temporary_paths,
)

try:
    from lib.utils.logger import get_logger
except ImportError:
    class _FallbackLogger:
        def info(self, message):
            print(f"INFO: {message}")

        def error(self, message):
            print(f"ERROR: {message}")

        def warning(self, message):
            print(f"WARNING: {message}")

        def debug(self, _message):
            return None

    def get_logger():
        return _FallbackLogger()


class ProjectStateError(Exception):
    """Raised when persisted project state is unsupported."""


class FutureProjectStateVersion(ProjectStateError):
    """Raised when a newer application is required to open the state."""


class ProjectStateManager:
    """Manage recoverable editor state without touching restoration history."""

    SCHEMA_VERSION = 2
    CHECKPOINT_NAME = re.compile(r"^[A-Za-z0-9À-ÿ][A-Za-z0-9À-ÿ._ -]{0,63}$")

    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.logger = get_logger()
        self.state_file = self.project_path / "metadata" / "project_state.json"
        self.persistence_available = True
        self.recovery_report = {
            "recovered": False,
            "source": None,
            "quarantined": None,
            "migrations": [],
            "error": None,
        }
        self.state = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        has_recovery_copy = (
            self.state_file.exists()
            or backup_path(self.state_file).exists()
            or bool(temporary_paths(self.state_file))
        )
        if not has_recovery_copy:
            state = self.get_default_state()
            self.save_state(state)
            return state

        try:
            loaded = load_json_with_recovery(
                self.state_file,
                validator=self._validate_state_candidate,
                fatal_exceptions=(FutureProjectStateVersion,),
            )
            state, migrations = self._migrate_state(loaded.data)
            self._validate_state(state)
        except FutureProjectStateVersion:
            raise
        except (JsonRecoveryError, ProjectStateError) as error:
            self.persistence_available = False
            self.recovery_report["error"] = str(error)
            self.logger.error(f"Estado do projeto indisponível: {error}")
            return self.get_default_state()

        self.recovery_report.update(
            {
                "recovered": loaded.recovered,
                "source": loaded.source,
                "quarantined": str(loaded.quarantined) if loaded.quarantined else None,
                "migrations": migrations,
            }
        )
        if migrations:
            atomic_write_json(self.state_file, state)
        self.logger.info(f"Estado do projeto carregado de {self.state_file}")
        return state

    def get_default_state(self) -> Dict[str, Any]:
        return {
            "schema_version": self.SCHEMA_VERSION,
            "schema_migrations": [],
            "current_frame": 0,
            "total_frames": 0,
            "video_path": None,
            "last_position": 0.0,
            "playback_speed": 1.0,
            "zoom_level": 1.0,
            "pan_offset": {"x": 0, "y": 0},
            "selected_frames": [],
            "deleted_frames": [],
            "processing_settings": {
                "diff_thresh": 25,
                "use_alignment": True,
                "inpaint_if_needed": True,
                "thin_line_boost": True,
                "protect_edges": True,
            },
            "ffmpeg_config": {
                "qscale_v": 1,
                "scale_filter": "lanczos",
                "width": 3840,
                "height": 2160,
                "fps": 60,
                "output_pattern": "frames/frame_%04d.png",
            },
            "ui_state": {
                "selected_tab": "video",
                "timeline_zoom": 1.0,
                "panel_sizes": {},
            },
            "last_saved": self._now(),
            "version": "2.0.0",
        }

    def save_state(self, state: Optional[Dict[str, Any]] = None) -> bool:
        if not self.persistence_available:
            self.logger.error("Gravação bloqueada para preservar o estado danificado")
            return False
        try:
            target = state if state is not None else self.state
            target["last_saved"] = self._now()
            target["schema_version"] = self.SCHEMA_VERSION
            atomic_write_json(self.state_file, target)
            if state is not None:
                self.state = target
            self.logger.info(f"Estado do projeto salvo em {self.state_file}")
            return True
        except (OSError, TypeError, ValueError) as error:
            self.logger.error(f"Erro ao salvar estado do projeto: {error}")
            return False

    def update_current_frame(self, frame_number: int, total_frames: int = None):
        self.state["current_frame"] = frame_number
        if total_frames is not None:
            self.state["total_frames"] = total_frames
        self.save_state()

    def update_video_info(self, video_path: str, total_frames: int, fps: float = None):
        self.state["video_path"] = video_path
        self.state["total_frames"] = total_frames
        if fps is not None:
            self.state["fps"] = fps
        self.save_state()

    def update_playback_position(self, position: float):
        self.state["last_position"] = position
        self.save_state()

    def update_playback_speed(self, speed: float):
        self.state["playback_speed"] = speed
        self.save_state()

    def update_zoom_level(self, zoom: float):
        self.state["zoom_level"] = zoom
        self.save_state()

    def update_pan_offset(self, x: float, y: float):
        self.state["pan_offset"] = {"x": x, "y": y}
        self.save_state()

    def add_selected_frame(self, frame_number: int):
        if frame_number not in self.state["selected_frames"]:
            self.state["selected_frames"].append(frame_number)
            self.save_state()

    def remove_selected_frame(self, frame_number: int):
        if frame_number in self.state["selected_frames"]:
            self.state["selected_frames"].remove(frame_number)
            self.save_state()

    def clear_selected_frames(self):
        self.state["selected_frames"] = []
        self.save_state()

    def add_deleted_frame(self, frame_number: int):
        if frame_number not in self.state["deleted_frames"]:
            self.state["deleted_frames"].append(frame_number)
            self.save_state()

    def remove_deleted_frame(self, frame_number: int):
        if frame_number in self.state["deleted_frames"]:
            self.state["deleted_frames"].remove(frame_number)
            self.save_state()

    def update_processing_settings(self, settings: Dict):
        self.state["processing_settings"].update(settings)
        self.save_state()

    def update_ffmpeg_config(self, config: Dict):
        self.state["ffmpeg_config"].update(config)
        self.save_state()

    def update_ui_state(self, ui_updates: Dict):
        self.state["ui_state"].update(ui_updates)
        self.save_state()

    def get_current_frame(self) -> int:
        return self.state.get("current_frame", 0)

    def get_total_frames(self) -> int:
        return self.state.get("total_frames", 0)

    def get_video_path(self) -> Optional[str]:
        return self.state.get("video_path")

    def get_last_position(self) -> float:
        return self.state.get("last_position", 0.0)

    def get_playback_speed(self) -> float:
        return self.state.get("playback_speed", 1.0)

    def get_zoom_level(self) -> float:
        return self.state.get("zoom_level", 1.0)

    def get_pan_offset(self) -> Dict:
        return self.state.get("pan_offset", {"x": 0, "y": 0})

    def get_selected_frames(self) -> list:
        return self.state.get("selected_frames", [])

    def get_deleted_frames(self) -> list:
        return self.state.get("deleted_frames", [])

    def get_processing_settings(self) -> Dict:
        return self.state.get("processing_settings", {})

    def get_ffmpeg_config(self) -> Dict:
        return self.state.get("ffmpeg_config", {})

    def get_ui_state(self) -> Dict:
        return self.state.get("ui_state", {})

    def restore_to_frame(self, frame_number: int) -> bool:
        if 0 <= frame_number <= self.get_total_frames():
            self.update_current_frame(frame_number)
            return True
        self.logger.warning(f"Frame {frame_number} fora do intervalo")
        return False

    def create_checkpoint(self, name: str) -> bool:
        if not self.CHECKPOINT_NAME.fullmatch(name or ""):
            self.logger.error("Nome de checkpoint inválido")
            return False
        try:
            checkpoint_dir = self.project_path / "checkpoints"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            atomic_write_json(checkpoint_dir / f"{name}_{timestamp}.json", self.state)
            return True
        except (OSError, TypeError, ValueError) as error:
            self.logger.error(f"Erro ao criar checkpoint: {error}")
            return False

    def list_checkpoints(self) -> list:
        checkpoint_dir = self.project_path / "checkpoints"
        if not checkpoint_dir.is_dir():
            return []
        return sorted(
            (
                {
                    "name": path.stem,
                    "file": str(path),
                    "modified": datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                }
                for path in checkpoint_dir.glob("*.json")
            ),
            key=lambda item: item["modified"],
            reverse=True,
        )

    def restore_checkpoint(self, checkpoint_file: str) -> bool:
        try:
            path = Path(checkpoint_file).resolve()
            checkpoint_dir = (self.project_path / "checkpoints").resolve()
            if path.parent != checkpoint_dir:
                raise ProjectStateError("Checkpoint fora da pasta do projeto")
            loaded = load_json_with_recovery(path, validator=self._validate_state_candidate)
            state, _migrations = self._migrate_state(loaded.data)
            self._validate_state(state)
            self.state = state
            return self.save_state()
        except (OSError, JsonRecoveryError, ProjectStateError) as error:
            self.logger.error(f"Erro ao restaurar checkpoint: {error}")
            return False

    def export_state(self, export_path: str) -> bool:
        try:
            atomic_write_json(Path(export_path), self.state)
            return True
        except (OSError, TypeError, ValueError) as error:
            self.logger.error(f"Erro ao exportar estado: {error}")
            return False

    def import_state(self, import_path: str) -> bool:
        try:
            with Path(import_path).open("r", encoding="utf-8") as file_handle:
                imported = json.load(file_handle)
            if not isinstance(imported, dict):
                raise ProjectStateError("Estado importado precisa ser um objeto JSON")
            state, _migrations = self._migrate_state(imported)
            self._validate_state(state)
            self.state = state
            return self.save_state()
        except (OSError, json.JSONDecodeError, ProjectStateError) as error:
            self.logger.error(f"Erro ao importar estado: {error}")
            return False

    def _validate_state_candidate(self, data: Dict[str, Any]) -> None:
        migrated, _migrations = self._migrate_state(data)
        self._validate_state(migrated)

    def _migrate_state(self, source: Dict[str, Any]):
        state = deepcopy(source)
        version = state.get("schema_version", 1)
        if not isinstance(version, int) or version < 1:
            raise ProjectStateError("Schema do estado inválido")
        if version > self.SCHEMA_VERSION:
            raise FutureProjectStateVersion(
                f"Estado usa schema {version}; esta versão suporta até {self.SCHEMA_VERSION}"
            )
        migrations = []
        if version == 1:
            state.setdefault("schema_migrations", []).append(
                {"from": 1, "to": 2, "migrated_at": self._now()}
            )
            state["schema_version"] = 2
            migrations.append(2)
        self._merge_defaults(state, self.get_default_state())
        return state, migrations

    @classmethod
    def _merge_defaults(cls, target: Dict[str, Any], defaults: Dict[str, Any]) -> None:
        for key, value in defaults.items():
            if key not in target:
                target[key] = deepcopy(value)
            elif isinstance(value, dict) and isinstance(target[key], dict):
                cls._merge_defaults(target[key], value)

    def _validate_state(self, state: Dict[str, Any]) -> None:
        if state.get("schema_version") != self.SCHEMA_VERSION:
            raise ProjectStateError("Schema do estado não suportado")
        for key in ("current_frame", "total_frames"):
            if not isinstance(state.get(key), int) or state[key] < 0:
                raise ProjectStateError(f"Campo inválido: {key}")
        for key in ("selected_frames", "deleted_frames"):
            if not isinstance(state.get(key), list):
                raise ProjectStateError(f"Campo inválido: {key}")
        for key in ("processing_settings", "ffmpeg_config", "ui_state", "pan_offset"):
            if not isinstance(state.get(key), dict):
                raise ProjectStateError(f"Campo inválido: {key}")

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
