"""Geometry helpers for the responsive frame restoration viewer."""

from __future__ import annotations


def filmstrip_window_indices(total: int, center: int, limit: int = 11) -> list[int]:
    """Return a small contiguous thumbnail window around the current frame."""
    total = max(0, int(total))
    if total == 0:
        return []
    limit = max(1, min(int(limit), total))
    center = max(0, min(int(center), total - 1))
    start = max(0, center - limit // 2)
    start = min(start, total - limit)
    return list(range(start, start + limit))


def clamp_view_pan(
    image_size: tuple[int, int],
    canvas_size: tuple[int, int],
    scale: float,
    pan: tuple[float, float],
) -> tuple[float, float]:
    """Keep a zoomed image inside the viewport while allowing edge inspection."""
    image_width, image_height = image_size
    canvas_width, canvas_height = canvas_size
    rendered_width = max(0.0, image_width * scale)
    rendered_height = max(0.0, image_height * scale)
    max_x = max(0.0, (rendered_width - canvas_width) / 2.0)
    max_y = max(0.0, (rendered_height - canvas_height) / 2.0)
    pan_x = max(-max_x, min(max_x, float(pan[0]))) if max_x else 0.0
    pan_y = max(-max_y, min(max_y, float(pan[1]))) if max_y else 0.0
    return pan_x, pan_y


def anchored_zoom_pan(
    canvas_size: tuple[int, int],
    pointer: tuple[float, float],
    old_scale: float,
    new_scale: float,
    pan: tuple[float, float],
) -> tuple[float, float]:
    """Preserve the image point below the pointer while changing zoom."""
    if old_scale <= 0 or new_scale <= 0:
        return pan
    center_x = canvas_size[0] / 2.0
    center_y = canvas_size[1] / 2.0
    relative_x = (pointer[0] - center_x - pan[0]) / old_scale
    relative_y = (pointer[1] - center_y - pan[1]) / old_scale
    return (
        pointer[0] - center_x - relative_x * new_scale,
        pointer[1] - center_y - relative_y * new_scale,
    )
