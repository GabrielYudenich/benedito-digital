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

    def __init__(self, worktree=None):
        self.operations = []
        self.worktree = worktree

    def commit_operation(self, operation_type, **kwargs):
        self.operations.append((operation_type, kwargs))

    def branch_worktree(self):
        return self.worktree


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
    derived_directories = {}
    for attribute in (
        "manual_stab_dir",
        "auto_stab_dir",
        "upscaled_dir",
        "auto_masks_dir",
        "selections_dir",
        "clean_plate_layers_dir",
    ):
        directory = tmp_path / attribute
        directory.mkdir()
        derived_directories[attribute] = directory
    automatic = derived_directories["auto_stab_dir"] / frame.name
    automatic.write_bytes(b"stabilized")
    layer_composite = (
        derived_directories["clean_plate_layers_dir"]
        / "plate-a"
        / "composite"
        / frame.name
    )
    layer_composite.parent.mkdir(parents=True)
    layer_composite.write_bytes(b"plate")

    editor = type("Editor", (), {})()
    editor.workspace = Workspace()
    editor.frame_manager = FrameManager(
        {"index": 0, "path": str(frame), "filename": frame.name}
    )
    editor.restored_dir = str(restored_dir)
    editor.manual_stab_dir = str(derived_directories["manual_stab_dir"])
    editor.auto_stab_dir = str(derived_directories["auto_stab_dir"])
    editor.upscaled_dir = str(derived_directories["upscaled_dir"])
    editor.auto_masks_dir = str(derived_directories["auto_masks_dir"])
    editor.selections_dir = str(derived_directories["selections_dir"])
    editor.clean_plate_layers_dir = str(
        derived_directories["clean_plate_layers_dir"]
    )
    editor._mask_path_for_frame = lambda _path: str(mask)
    editor._legacy_mask_path_for_frame = lambda _path: str(tmp_path / "legacy.png")
    editor._auto_mask_path_for_frame = lambda _path: str(tmp_path / "auto.png")
    editor._selection_path_for_frame = lambda _path: str(tmp_path / "selection.png")
    editor._current_mask = object()
    editor._current_mask_path = str(mask)
    editor._selection_mask = object()
    editor._selection_frame_path = str(frame)
    editor._clean_plate_layers_cache = [object()]
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
    assert editor.workspace.operations[0][1]["artifacts"]["previous_mask"] == str(mask)
    assert editor.workspace.operations[0][1]["artifacts"]["previous_result"] == str(restored)
    assert editor.workspace.operations[0][1]["artifacts"][
        "previous_auto_stabilization"
    ] == str(automatic)
    assert not mask.exists()
    assert not restored.exists()
    assert not automatic.exists()
    assert not layer_composite.exists()
    assert frame.read_bytes() == b"original"
    assert editor.view_mode == "original"
    assert editor.shown == 1


def test_total_reset_removes_only_derived_branch_files(monkeypatch, tmp_path):
    worktree = tmp_path / "worktrees" / "principal"
    worktree.mkdir(parents=True)
    original_frames = tmp_path / "sources" / "frames"
    original_frames.mkdir(parents=True)
    original = original_frames / "frame_000001.png"
    original.write_bytes(b"original")
    clean_plates = worktree / "clean_plates"
    clean_plates.mkdir()
    plate = clean_plates / "plate.png"
    plate.write_bytes(b"plate")

    directory_attributes = {
        "restored_dir": "restored",
        "manual_stab_dir": "stabilized_manual",
        "auto_stab_dir": "stabilized_auto",
        "upscaled_dir": "upscaled",
        "masks_dir": "masks",
        "auto_masks_dir": "masks_auto",
        "selections_dir": "selections",
        "clean_plate_layers_dir": "clean_plate_layers",
    }
    editor = type("Editor", (), {})()
    for attribute, directory_name in directory_attributes.items():
        directory = worktree / directory_name
        directory.mkdir()
        (directory / "derived.dat").write_bytes(b"derived")
        setattr(editor, attribute, str(directory))
    jobs = worktree / ".jobs" / "restoration"
    jobs.mkdir(parents=True)
    (jobs / "checkpoint.json").write_text("{}", encoding="utf-8")

    editor.workspace = Workspace(worktree)
    editor._active_job_id = None
    editor.status_var = Value()
    editor._current_mask = object()
    editor._current_mask_path = "mask"
    editor._selection_mask = object()
    editor._selection_frame_path = "selection"
    editor._clean_plate_layers_cache = [object()]
    editor._review_preview_cache = {"frame": object()}
    editor._review_preview_order = ["frame"]
    editor.view_mode = "restored"
    editor.shown = 0
    editor.show_current_frame = lambda: setattr(editor, "shown", editor.shown + 1)
    for attribute in (
        "use_manual_stab_var",
        "use_auto_stab_var",
        "view_upscale_var",
        "use_upscale_render_var",
    ):
        variable = Value()
        variable.set(True)
        setattr(editor, attribute, variable)

    class Context:
        def check_cancelled(self):
            pass

        def report(self, *_args):
            pass

    editor._start_ui_job = lambda _title, task, complete: complete(task(Context()))
    monkeypatch.setattr(
        "gui.controllers.project_version_controller.messagebox.askyesno",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "gui.controllers.project_version_controller.messagebox.showinfo",
        lambda *_args, **_kwargs: None,
    )

    ProjectVersionController(editor).reset_all_results_to_original()

    assert original.read_bytes() == b"original"
    assert plate.read_bytes() == b"plate"
    for attribute in directory_attributes:
        assert list(Path(getattr(editor, attribute)).iterdir()) == []
    assert list((worktree / ".jobs").iterdir()) == []
    assert editor.workspace.operations[-1][0] == "project.reset_results"
    assert editor.workspace.operations[-1][1]["payload"]["removed_files"] == 9
    assert editor.view_mode == "original"
    assert editor.shown == 1


def test_segment_reset_preserves_results_outside_selected_position(monkeypatch, tmp_path):
    worktree = tmp_path / "worktrees" / "principal"
    worktree.mkdir(parents=True)
    frames_dir = tmp_path / "sources" / "frames"
    frames_dir.mkdir(parents=True)
    frame_names = [f"frame_{index:06d}.png" for index in range(1, 6)]
    for frame_name in frame_names:
        (frames_dir / frame_name).write_bytes(b"original")

    editor = type("Editor", (), {})()
    editor.workspace = Workspace(worktree)
    editor._active_job_id = None
    editor.frame_manager = type(
        "Frames",
        (),
        {"frames": frame_names, "frames_dir": str(frames_dir)},
    )()
    for attribute, directory_name in {
        "restored_dir": "restored",
        "manual_stab_dir": "stabilized_manual",
        "auto_stab_dir": "stabilized_auto",
        "upscaled_dir": "upscaled",
        "masks_dir": "masks",
        "auto_masks_dir": "masks_auto",
        "selections_dir": "selections",
        "clean_plate_layers_dir": "clean_plate_layers",
    }.items():
        directory = worktree / directory_name
        directory.mkdir()
        setattr(editor, attribute, str(directory))
    for frame_name in frame_names:
        for directory in (
            Path(editor.restored_dir),
            Path(editor.manual_stab_dir),
            Path(editor.auto_stab_dir),
            Path(editor.upscaled_dir),
        ):
            (directory / frame_name).write_bytes(b"derived")
    layer_composite = Path(editor.clean_plate_layers_dir) / "plate-a" / "composite"
    layer_composite.mkdir(parents=True)
    for frame_name in frame_names:
        (layer_composite / frame_name).write_bytes(b"plate")
    editor._mask_path_for_frame = lambda path: str(
        Path(editor.masks_dir) / f"mask_{Path(path).stem}.png"
    )
    editor._legacy_mask_path_for_frame = lambda path: str(
        Path(editor.masks_dir) / f"mask_{Path(path).name}"
    )
    editor._auto_mask_path_for_frame = lambda path: str(
        Path(editor.auto_masks_dir) / f"auto_{Path(path).stem}.png"
    )
    editor._selection_path_for_frame = lambda path: str(
        Path(editor.selections_dir) / f"selection_{Path(path).stem}.png"
    )
    editor._current_mask = None
    editor._current_mask_path = None
    editor._selection_mask = None
    editor._selection_frame_path = None
    editor._clean_plate_layers_cache = None
    editor.view_mode = "restored"
    editor.status_var = Value()
    editor.applied_segment = None
    editor._apply_camera_segment = lambda segment: setattr(
        editor, "applied_segment", segment.id
    )

    class Context:
        def check_cancelled(self):
            pass

        def report(self, *_args):
            pass

    editor._start_ui_job = lambda _title, task, complete: complete(task(Context()))
    monkeypatch.setattr(
        "gui.controllers.project_version_controller.messagebox.askyesno",
        lambda *_args, **_kwargs: True,
    )
    monkeypatch.setattr(
        "gui.controllers.project_version_controller.messagebox.showinfo",
        lambda *_args, **_kwargs: None,
    )
    segment = type(
        "Segment",
        (),
        {"id": "position-1", "name": "Posição 1", "start": 1, "end": 3},
    )()

    ProjectVersionController(editor).reset_camera_segment_results(segment)

    for directory in (
        Path(editor.restored_dir),
        Path(editor.manual_stab_dir),
        Path(editor.auto_stab_dir),
        Path(editor.upscaled_dir),
        layer_composite,
    ):
        assert (directory / frame_names[0]).is_file()
        assert not (directory / frame_names[1]).exists()
        assert not (directory / frame_names[2]).exists()
        assert not (directory / frame_names[3]).exists()
        assert (directory / frame_names[4]).is_file()
    assert all((frames_dir / frame_name).is_file() for frame_name in frame_names)
    assert editor.workspace.operations[-1][0] == "camera_segment.reset_results"
    assert editor.applied_segment == "position-1"
