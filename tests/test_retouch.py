import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.retouch import apply_retouch_dab, apply_retouch_stroke


def test_clone_copies_source_texture_and_preserves_outside_circle():
    image = np.zeros((30, 30, 3), dtype=np.uint8)
    image[4:9, 4:9] = (20, 80, 220)

    result = apply_retouch_dab(image, (6, 6), (20, 20), radius=3, hardness=1.0)

    assert tuple(result[20, 20]) == (20, 80, 220)
    assert np.array_equal(result[0:15, 15:30], image[0:15, 15:30])
    assert np.array_equal(image[18:23, 18:23], np.zeros((5, 5, 3), dtype=np.uint8))


def test_healing_adapts_brightness_while_preserving_source_detail():
    image = np.full((40, 40, 3), 180, dtype=np.uint8)
    image[5:12, 5:12] = 40
    image[8, 8] = 80

    cloned = apply_retouch_dab(image, (8, 8), (28, 28), radius=4, mode="clone", hardness=1.0)
    healed = apply_retouch_dab(image, (8, 8), (28, 28), radius=4, mode="heal", hardness=1.0)

    assert int(cloned[28, 28, 0]) == 80
    assert int(healed[28, 28, 0]) > int(cloned[28, 28, 0])
    assert int(healed[28, 28, 0]) <= 255


def test_stroke_keeps_constant_source_offset():
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[4, 4] = (10, 20, 30)
    image[6, 6] = (40, 50, 60)

    result = apply_retouch_stroke(
        image,
        source_anchor=(4, 4),
        target_points=[(20, 20), (22, 22)],
        radius=1,
        hardness=1.0,
    )

    assert tuple(result[20, 20]) == (10, 20, 30)
    assert tuple(result[22, 22]) == (40, 50, 60)


def test_invalid_mode_is_rejected():
    image = np.zeros((4, 4, 3), dtype=np.uint8)

    try:
        apply_retouch_dab(image, (1, 1), (2, 2), 1, mode="blur")
    except ValueError as error:
        assert "clone or heal" in str(error)
    else:
        raise AssertionError("Expected invalid retouch mode to fail")
