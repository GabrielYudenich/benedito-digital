import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.controllers.project_version_controller import ProjectVersionController


class Value:
    def __init__(self):
        self.value = None

    def set(self, value):
        self.value = value


class Workspace:
    active_branch = "rolo-2"

    def __init__(self):
        self.operations = []

    def commit_operation(self, operation_type, **kwargs):
        self.operations.append((operation_type, kwargs))


class Retouch:
    def __init__(self):
        self.resets = 0

    def reset_for_branch(self):
        self.resets += 1


class FrameManager:
    def __init__(self, info):
        self.info = info

    def get_current_frame_info(self):
        return self.info


def test_branch_change_resets_transient_editor_state():
    editor = type("Editor", (), {})()
    editor.workspace = Workspace()
    editor.retouch_controller = Retouch()
    editor.status_var = Value()
    editor._current_mask = object()
    editor._current_mask_path = "mask"
    editor._selection_mask = object()
    editor._selection_frame_path = "selection"
    editor.view_mode = "restored"
    editor.configured = 0
    editor.shown = 0
    editor._configure_branch_paths = lambda: setattr(editor, "configured", editor.configured + 1)
    editor.show_current_frame = lambda: setattr(editor, "shown", editor.shown + 1)

    ProjectVersionController(editor).on_branch_changed()

    assert editor.configured == 1
    assert editor.retouch_controller.resets == 1
    assert editor._current_mask is None
    assert editor._selection_mask is None
    assert editor.view_mode == "original"
    assert editor.status_var.value == "Branch atual: rolo-2"
    assert editor.shown == 1


def test_frame_reset_commits_artifacts_and_removes_branch_files(monkeypatch, tmp_path):
    frame = tmp_path / "frame_000001.png"
    frame.write_bytes(b"original")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask")
    restored_dir = tmp_path / "restored"
    restored_dir.mkdir()
    restored = restored_dir / frame.name
    restored.write_bytes(b"edited")

    editor = type("Editor", (), {})()
    editor.workspace = Workspace()
    editor.frame_manager = FrameManager(
        {"index": 0, "path": str(frame), "filename": frame.name}
    )
    editor.restored_dir = str(restored_dir)
    editor._mask_path_for_frame = lambda _path: str(mask)
    editor._legacy_mask_path_for_frame = lambda _path: str(tmp_path / "legacy.png")
    editor._current_mask = object()
    editor._current_mask_path = str(mask)
    editor.view_mode = "restored"
    editor.status_var = Value()
    editor.shown = 0
    editor.show_current_frame = lambda: setattr(editor, "shown", editor.shown + 1)
    monkeypatch.setattr(
        "gui.controllers.project_version_controller.messagebox.askyesno",
        lambda *_args, **_kwargs: True,
    )

    ProjectVersionController(editor).reset_current_frame_to_original()

    assert editor.workspace.operations[0][0] == "frame.reset"
    assert editor.workspace.operations[0][1]["artifacts"] == {
        "previous_mask": str(mask),
        "previous_result": str(restored),
    }
    assert not mask.exists()
    assert not restored.exists()
    assert frame.read_bytes() == b"original"
    assert editor.view_mode == "original"
    assert editor.shown == 1
