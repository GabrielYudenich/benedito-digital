"""Runtime paths for source checkouts and packaged Windows builds."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    if bundled:
        return Path(bundled)
    return Path(__file__).resolve().parents[2]


def resource_path(*parts: str) -> Path:
    return resource_root().joinpath(*parts)


def executable_path(name: str) -> str:
    """Resolve bundled multimedia tools before falling back to PATH."""
    executable_name = name
    if os.name == "nt" and not executable_name.lower().endswith(".exe"):
        executable_name += ".exe"
    configured = os.environ.get("BENEDITO_FFMPEG_DIR")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser() / executable_name)
    candidates.extend(
        [
            resource_path("ffmpeg", "bin", executable_name),
            resource_path("vendor", "ffmpeg", "bin", executable_name),
            resource_path(executable_name),
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate.resolve())
    return shutil.which(executable_name) or shutil.which(name) or name


def default_projects_dir() -> Path:
    configured = os.environ.get("BENEDITO_PROJECTS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if getattr(sys, "frozen", False):
        documents = Path(os.environ.get("USERPROFILE", Path.home())) / "Documents"
        return documents / "Benedito Digital" / "Projetos"
    return resource_root() / "projects"


def default_models_dir() -> Path:
    """Return a writable per-user directory for optional model weights."""
    configured = os.environ.get("BENEDITO_MODELS_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    else:
        base = Path(
            os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")
        )
    return base / "Benedito Digital" / "Models"
