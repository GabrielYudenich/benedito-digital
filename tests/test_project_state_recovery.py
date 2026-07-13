import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.modules.project.state.project_state import (
    FutureProjectStateVersion,
    ProjectStateManager,
)


def test_legacy_state_is_migrated_and_defaults_are_added(tmp_path):
    state_file = tmp_path / "project" / "metadata" / "project_state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({"current_frame": 12, "total_frames": 100, "version": "2.0.0"}),
        encoding="utf-8",
    )

    manager = ProjectStateManager(str(tmp_path / "project"))

    assert manager.get_current_frame() == 12
    assert manager.state["schema_version"] == 2
    assert manager.recovery_report["migrations"] == [2]
    assert manager.get_ui_state()["selected_tab"] == "video"


def test_corrupt_state_recovers_previous_saved_position(tmp_path):
    manager = ProjectStateManager(str(tmp_path / "project"))
    manager.update_current_frame(10, 100)
    manager.update_current_frame(20, 100)
    manager.state_file.write_text("{gravação-interrompida", encoding="utf-8")

    recovered = ProjectStateManager(str(tmp_path / "project"))

    assert recovered.get_current_frame() == 10
    assert recovered.recovery_report["recovered"] is True
    assert recovered.recovery_report["source"] == "backup"
    assert Path(recovered.recovery_report["quarantined"]).is_file()


def test_unrecoverable_state_is_preserved_and_writes_are_blocked(tmp_path):
    state_file = tmp_path / "project" / "metadata" / "project_state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text("{sem-backup", encoding="utf-8")

    manager = ProjectStateManager(str(tmp_path / "project"))

    assert manager.persistence_available is False
    assert manager.save_state() is False
    assert state_file.read_text(encoding="utf-8") == "{sem-backup"
    assert manager.recovery_report["error"]


def test_future_state_schema_requires_newer_application(tmp_path):
    state_file = tmp_path / "project" / "metadata" / "project_state.json"
    state_file.parent.mkdir(parents=True)
    state_file.write_text(
        json.dumps({"schema_version": 999, "current_frame": 0, "total_frames": 0}),
        encoding="utf-8",
    )

    with pytest.raises(FutureProjectStateVersion, match="suporta até"):
        ProjectStateManager(str(tmp_path / "project"))


def test_checkpoint_names_and_locations_are_restricted(tmp_path):
    manager = ProjectStateManager(str(tmp_path / "project"))

    assert manager.create_checkpoint("Antes da limpeza") is True
    assert manager.create_checkpoint("../fora") is False
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(manager.state), encoding="utf-8")
    assert manager.restore_checkpoint(str(outside)) is False
