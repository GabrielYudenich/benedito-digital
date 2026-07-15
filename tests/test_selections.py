import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.selections import polygon_mask, rectangle_mask, selection_bounds


def test_rectangle_selection_is_normalized_and_clipped():
    mask = rectangle_mask((100, 80), (70, 60), (-10, 10))

    assert selection_bounds(mask) == (0, 10, 71, 61)
    assert mask.getpixel((0, 10)) == 255
    assert mask.getpixel((99, 79)) == 0


def test_freehand_selection_requires_polygon_and_fills_inside():
    empty = polygon_mask((50, 50), [(1, 1), (2, 2)])
    triangle = polygon_mask((50, 50), [(5, 5), (40, 5), (5, 40)])

    assert selection_bounds(empty) is None
    assert triangle.getpixel((10, 10)) == 255
    assert triangle.getpixel((45, 45)) == 0
