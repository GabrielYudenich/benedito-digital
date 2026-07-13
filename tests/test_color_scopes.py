import sys
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.color_scopes import ColorScopeGenerator


def test_generates_three_scopes_and_luma_statistics():
    frame = np.zeros((120, 160, 3), dtype=np.uint8)
    frame[:, :80] = (0, 0, 255)
    frame[:, 80:] = (255, 255, 255)
    generator = ColorScopeGenerator(320, 192)

    result = generator.generate(frame)

    assert result["histogram"].shape == (192, 320, 3)
    assert result["waveform"].shape == (192, 320, 3)
    assert result["vectorscope"].shape == (192, 320, 3)
    assert result["statistics"].luma_max == 255
    assert result["statistics"].clipped_white == 0.5
    assert np.count_nonzero(result["vectorscope"]) > 0
