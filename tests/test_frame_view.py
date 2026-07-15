import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.frame_view import anchored_zoom_pan, clamp_view_pan, filmstrip_window_indices


def test_filmstrip_limits_large_projects_to_nearby_frames():
    indices = filmstrip_window_indices(3927, 60, limit=11)

    assert indices == list(range(55, 66))
    assert filmstrip_window_indices(3927, 0, limit=11) == list(range(11))
    assert filmstrip_window_indices(3927, 3926, limit=11) == list(range(3916, 3927))


def test_pan_is_clamped_to_visible_image_edges():
    assert clamp_view_pan((1920, 1080), (960, 540), 1.0, (900, -900)) == (
        480.0,
        -270.0,
    )
    assert clamp_view_pan((1920, 1080), (960, 540), 0.5, (100, 100)) == (
        0.0,
        0.0,
    )


def test_zoom_keeps_pointer_anchor_stable():
    pan = anchored_zoom_pan(
        (1000, 600),
        (750, 300),
        old_scale=0.5,
        new_scale=1.0,
        pan=(0, 0),
    )

    assert pan == (-250.0, 0.0)
