import os
import sys

import numpy as np


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.damage_analysis import FrameDamageAnalyzer


def test_flags_nearly_empty_frame_as_missing():
    analyzer = FrameDamageAnalyzer()
    frame = np.zeros((80, 120, 3), dtype=np.uint8)

    result = analyzer.analyze(frame)

    assert result.status == "missing"


def test_flags_identical_neighbor_as_possible_duplicate():
    analyzer = FrameDamageAnalyzer()
    frame = np.full((80, 120, 3), 90, dtype=np.uint8)

    result = analyzer.analyze(frame, previous=frame.copy())

    assert result.status == "review"
    assert result.possible_duplicate is True


def test_flags_prominent_line_as_scratch():
    analyzer = FrameDamageAnalyzer(sensitivity="high")
    previous = np.full((100, 160, 3), 80, dtype=np.uint8)
    current = previous.copy()
    current[:, 70:73] = 255

    result = analyzer.analyze(current, previous=previous, following=previous)

    assert result.status in {"scratch", "dust"}
