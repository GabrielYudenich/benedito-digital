import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens.editor_screen import EditorScreen


class FakeVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class FakeFrameManager:
    def __init__(self, frames_dir):
        self.frames = ["frame_000001.png"]
        self.frames_dir = str(frames_dir)


def test_source_frame_prefers_active_auto_stabilization(tmp_path):
    original_dir = tmp_path / "originals"
    restored_dir = tmp_path / "restored"
    manual_dir = tmp_path / "manual"
    automatic_dir = tmp_path / "automatic"
    upscaled_dir = tmp_path / "upscaled"
    for directory in (
        original_dir,
        restored_dir,
        manual_dir,
        automatic_dir,
        upscaled_dir,
    ):
        directory.mkdir()
    frame_name = "frame_000001.png"
    (original_dir / frame_name).write_bytes(b"original")
    (restored_dir / frame_name).write_bytes(b"restored")
    (automatic_dir / frame_name).write_bytes(b"stabilized")

    screen = object.__new__(EditorScreen)
    screen.frame_manager = FakeFrameManager(original_dir)
    screen.restored_dir = str(restored_dir)
    screen.manual_stab_dir = str(manual_dir)
    screen.auto_stab_dir = str(automatic_dir)
    screen.upscaled_dir = str(upscaled_dir)
    screen.view_upscale_var = FakeVariable(False)
    screen.use_manual_stab_var = FakeVariable(False)
    screen.use_auto_stab_var = FakeVariable(True)

    assert screen._get_source_frame_path(0) == str(automatic_dir / frame_name)
