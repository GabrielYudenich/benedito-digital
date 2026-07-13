import os
import json
import shutil
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
MODULE_DIR = os.path.join(ROOT, "src", "gui", "modules")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from project_manager_gui import ProjectManagerGUI


def test_new_project_uses_remodeled_layout(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")

    assert manager.create_project_advanced(
        "Rolo 1",
        author="Equipe",
        settings={"experience_level": "guided"},
    )
    project = manager.load_project("Rolo 1")

    assert project["project_format_version"] == 3
    assert os.path.isdir(manager.get_originals_dir())
    assert os.path.isdir(manager.get_frames_dir())
    assert os.path.isdir(os.path.join(manager.get_exports_dir(), "renders"))
    assert not os.path.exists(os.path.join(manager.current_project_path, "videos"))


def test_project_creation_rejects_unsafe_or_duplicate_names(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")

    assert not manager.create_project_advanced("../fora")
    assert manager.create_project_advanced("Seguro")
    assert not manager.create_project_advanced("Seguro")


def test_loading_old_workspace_reports_friendly_migration_notice(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")
    assert manager.create_project_advanced("Acervo")
    workspace_file = tmp_path / "projects" / "Acervo" / "metadata" / "workspace.json"
    workspace = json.loads(workspace_file.read_text(encoding="utf-8"))
    workspace["schema_version"] = 1
    workspace.pop("format")
    workspace.pop("schema_migrations")
    workspace_file.write_text(json.dumps(workspace), encoding="utf-8")

    assert manager.load_project("Acervo") is not None

    assert manager.last_project_notice["kind"] == "migrated"
    assert "preservados" in manager.last_project_notice["message"]


def test_external_project_is_registered_without_copying_media(tmp_path):
    external_manager = ProjectManagerGUI()
    external_manager.project_path = str(tmp_path / "external")
    assert external_manager.create_project_advanced("Rolo Externo", author="Equipe")
    external_path = tmp_path / "external" / "Rolo Externo"
    large_marker = external_path / "media" / "originals" / "filme.mov"
    large_marker.write_bytes(b"original")

    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "local")
    project = manager.register_external_project(str(external_path))

    assert project["name"] == "Rolo Externo"
    assert manager.current_project_path == str(external_path.resolve())
    assert large_marker.is_file()
    assert not (tmp_path / "local" / "Rolo Externo").exists()
    listed = manager.list_projects_in_path()
    assert listed[0]["external"] is True
    assert listed[0]["project_path"] == str(external_path.resolve())


def test_stale_external_project_reference_is_removed(tmp_path):
    source_manager = ProjectManagerGUI()
    source_manager.project_path = str(tmp_path / "external")
    assert source_manager.create_project_advanced("Temporário")
    external_path = tmp_path / "external" / "Temporário"

    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "local")
    assert manager.register_external_project(str(external_path)) is not None
    shutil.rmtree(external_path)

    assert manager.list_projects_in_path() == []
    assert manager._read_external_project_paths() == []


def test_external_project_rejects_folder_without_metadata(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "local")
    invalid = tmp_path / "not-a-project"
    invalid.mkdir()

    assert manager.register_external_project(str(invalid)) is None
