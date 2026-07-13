"""Spatial selection masks for frame editing."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

from PIL import Image, ImageDraw


Point = Tuple[int, int]


def rectangle_mask(size: Tuple[int, int], start: Point, end: Point) -> Image.Image:
    """Create a clipped rectangular grayscale selection."""
    width, height = _validate_size(size)
    x1, y1 = _clip_point(start, width, height)
    x2, y2 = _clip_point(end, width, height)
    left, right = sorted((x1, x2))
    top, bottom = sorted((y1, y2))
    mask = Image.new("L", (width, height), 0)
    ImageDraw.Draw(mask).rectangle((left, top, right, bottom), fill=255)
    return mask


def polygon_mask(size: Tuple[int, int], points: Sequence[Point]) -> Image.Image:
    """Create a clipped freehand polygon selection."""
    width, height = _validate_size(size)
    mask = Image.new("L", (width, height), 0)
    if len(points) < 3:
        return mask
    clipped = [_clip_point(point, width, height) for point in points]
    ImageDraw.Draw(mask).polygon(clipped, fill=255)
    return mask


def selection_bounds(mask: Image.Image):
    """Return the non-empty selection bounding box or None."""
    return mask.convert("L").getbbox()


def _validate_size(size: Tuple[int, int]) -> Tuple[int, int]:
    width, height = int(size[0]), int(size[1])
    if width <= 0 or height <= 0:
        raise ValueError("Selection size must be positive")
    return width, height


def _clip_point(point: Point, width: int, height: int) -> Point:
    x = max(0, min(width - 1, int(point[0])))
    y = max(0, min(height - 1, int(point[1])))
    return x, y
