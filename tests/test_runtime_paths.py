import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.paths import (
    default_models_dir,
    default_projects_dir,
    executable_path,
    resource_path,
    resource_root,
)


def test_source_checkout_paths_resolve_from_repository():
    assert resource_root().resolve() == __import__("pathlib").Path(ROOT).resolve()
    assert resource_path("config.json").is_file()
    assert default_projects_dir() == resource_root() / "projects"


def test_bundled_ffmpeg_is_preferred_when_available(monkeypatch, tmp_path):
    binary = tmp_path / "ffmpeg" / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"tool")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert executable_path("ffmpeg") == str(binary.resolve())


def test_optional_models_directory_can_be_configured(monkeypatch, tmp_path):
    target = tmp_path / "modelos locais"
    monkeypatch.setenv("BENEDITO_MODELS_DIR", str(target))

    assert default_models_dir() == target.resolve()
