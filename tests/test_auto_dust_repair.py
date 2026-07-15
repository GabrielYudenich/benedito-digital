import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens.editor_screen import EditorScreen


class FakeRestorer:
    def __init__(self):
        self.received_mask = None
        self.fallback_called = False

    def build_automask(self, current):
        self.fallback_called = True
        return np.zeros(current.shape[:2], dtype=np.uint8)

    def restore_triplet(self, previous, current, following, mask=None):
        self.received_mask = mask.copy() if mask is not None else None
        return np.full_like(current, 240), {}


def test_restore_uses_saved_auto_dust_mask(tmp_path):
    frame = np.full((48, 64, 3), 90, dtype=np.uint8)
    frame_paths = []
    for name in ("previous.png", "current.png", "following.png"):
        path = tmp_path / name
        assert cv2.imwrite(str(path), frame)
        frame_paths.append(str(path))
    auto_mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    auto_mask[12:17, 30:35] = 255
    auto_mask_path = tmp_path / "auto_current.png"
    assert cv2.imwrite(str(auto_mask_path), auto_mask)

    screen = object.__new__(EditorScreen)
    screen.restorer = FakeRestorer()
    screen.model_pipeline = object()
    screen._mask_path_for_frame = lambda _path: str(tmp_path / "manual_missing.png")
    screen._auto_mask_path_for_frame = lambda _path: str(auto_mask_path)
    screen._load_selection_cv = lambda _path, _index: None
    output_path = tmp_path / "restored" / "current.png"

    screen._restore_triplet_to_path(
        frame_paths[0],
        frame_paths[1],
        frame_paths[2],
        str(output_path),
        options={
            "model_name": "",
            "show_auto_mask": True,
            "double_pass": False,
            "frame_index": 1,
            "limit_output_to_mask": True,
        },
    )

    restored = cv2.imread(str(output_path), cv2.IMREAD_COLOR)
    assert np.array_equal(screen.restorer.received_mask, auto_mask)
    assert screen.restorer.fallback_called is False
    assert output_path.is_file()
    assert np.all(restored[14, 32] == 240)
    assert np.all(restored[2, 2] == 90)
