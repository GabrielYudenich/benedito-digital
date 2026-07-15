import os
import json
import shutil
import sys
from pathlib import Path


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
MODULE_DIR = os.path.join(ROOT, "src", "gui", "modules")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

from project_manager_gui import ProjectManagerGUI
from core.media_import import build_import_plan


class FakeLosslessProcessor:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def create_lossless_segment(
        self, input_path, output_path, start_time, end_time,
        progress_callback=None, cancel_callback=None,
        working_format="mkv_lossless", audio_mode="preserve",
    ):
        self.calls.append(
            (input_path, output_path, start_time, end_time, working_format, audio_mode)
        )
        if self.fail:
            Path(output_path).write_bytes(b"partial")
            raise RuntimeError("interrompido")
        Path(output_path).write_bytes(b"lossless segment")
        if progress_callback:
            progress_callback(100)
        return True


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


def test_imports_only_selected_segment_and_records_provenance(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")
    assert manager.create_project_advanced("Trecho")
    assert manager.load_project("Trecho") is not None
    source = tmp_path / "filme.mov"
    source.write_bytes(b"original source")
    info = {"duration": 120, "fps": 1, "width": 16, "height": 16}
    plan = build_import_plan(
        source, "segment", info, start_value="10", end_value="20"
    )
    processor = FakeLosslessProcessor()
    progress = []

    assert manager.add_video_to_project(
        str(source),
        import_plan=plan,
        video_processor=processor,
        progress_callback=progress.append,
    )

    imported = Path(manager.get_originals_dir()) / plan.destination_name
    record = next(iter(manager.workspace.data["originals"].values()))
    assert imported.read_bytes() == b"lossless segment"
    assert manager.last_imported_video_name == plan.destination_name
    assert manager.get_project_videos() == [plan.destination_name]
    assert record["provenance"]["kind"] == "lossless-segment"
    assert record["provenance"]["start_time"] == 10
    assert record["provenance"]["end_time"] == 20
    assert record["provenance"]["working_format"] == "mkv_lossless"
    assert record["provenance"]["audio_mode"] == "preserve"
    assert record["provenance"]["container"] == "mkv"
    assert progress[-1] == 100


def test_mov_segment_records_format_and_audio_treatment(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")
    assert manager.create_project_advanced("MOV")
    assert manager.load_project("MOV") is not None
    source = tmp_path / "filme.mov"
    source.write_bytes(b"original source")
    plan = build_import_plan(
        source,
        "segment",
        {"duration": 20, "fps": 1, "width": 16, "height": 16},
        start_value="1",
        end_value="2",
        working_format="mov_prores",
        audio_mode="dual_mono_right",
    )
    processor = FakeLosslessProcessor()

    assert manager.add_video_to_project(
        str(source), import_plan=plan, video_processor=processor
    )

    imported = Path(manager.get_originals_dir()) / plan.destination_name
    record = next(iter(manager.workspace.data["originals"].values()))
    assert imported.suffix == ".mov"
    assert processor.calls[0][1].endswith(".mov")
    assert processor.calls[0][4:] == ("mov_prores", "dual_mono_right")
    assert record["provenance"]["container"] == "mov"
    assert record["provenance"]["video_codec"] == "prores_ks"
    assert record["provenance"]["audio_mode"] == "dual_mono_right"


def test_failed_segment_import_removes_partial_files(tmp_path):
    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")
    assert manager.create_project_advanced("Falha")
    assert manager.load_project("Falha") is not None
    source = tmp_path / "filme.mov"
    source.write_bytes(b"original source")
    plan = build_import_plan(
        source,
        "segment",
        {"duration": 20, "fps": 1, "width": 16, "height": 16},
        start_value="1",
        end_value="2",
    )

    assert not manager.add_video_to_project(
        str(source), import_plan=plan, video_processor=FakeLosslessProcessor(fail=True)
    )

    assert not (Path(manager.get_originals_dir()) / plan.destination_name).exists()
    assert list(Path(manager.get_originals_dir()).glob(".*.mkv")) == []
    assert manager.workspace.data["originals"] == {}


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
