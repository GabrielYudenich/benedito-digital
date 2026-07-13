"""Deterministic, bounded-memory clone and healing operations for frame retouching."""

from __future__ import annotations

from typing import Iterable, Sequence, Tuple

import numpy as np


Point = Tuple[int, int]


def apply_retouch_dab(
    image: np.ndarray,
    source_center: Point,
    target_center: Point,
    radius: int,
    mode: str = "clone",
    opacity: float = 1.0,
    hardness: float = 0.65,
    source_image: np.ndarray | None = None,
) -> np.ndarray:
    """Apply one clone/healing dab without changing pixels outside its circle."""
    if mode not in {"clone", "heal"}:
        raise ValueError("Retouch mode must be clone or heal")
    if image.ndim != 3 or image.shape[2] not in {3, 4}:
        raise ValueError("Retouch image must have three or four channels")
    sampling_image = image if source_image is None else source_image
    if sampling_image.shape != image.shape or sampling_image.dtype != image.dtype:
        raise ValueError("Source image must match target image shape and dtype")
    radius = int(radius)
    if radius < 1:
        raise ValueError("Retouch radius must be positive")
    opacity = float(np.clip(opacity, 0.0, 1.0))
    hardness = float(np.clip(hardness, 0.0, 1.0))
    if opacity == 0:
        return image.copy()

    height, width = image.shape[:2]
    target_x, target_y = map(int, target_center)
    source_x, source_y = map(int, source_center)
    left = max(0, target_x - radius)
    right = min(width, target_x + radius + 1)
    top = max(0, target_y - radius)
    bottom = min(height, target_y + radius + 1)
    if left >= right or top >= bottom:
        return image.copy()

    target_grid_x, target_grid_y = np.meshgrid(
        np.arange(left, right), np.arange(top, bottom)
    )
    source_grid_x = source_x + (target_grid_x - target_x)
    source_grid_y = source_y + (target_grid_y - target_y)
    valid_source = (
        (source_grid_x >= 0)
        & (source_grid_x < width)
        & (source_grid_y >= 0)
        & (source_grid_y < height)
    )
    distance = np.sqrt((target_grid_x - target_x) ** 2 + (target_grid_y - target_y) ** 2)
    hard_radius = radius * hardness
    feather = max(1e-6, radius - hard_radius)
    alpha = np.where(
        distance <= hard_radius,
        1.0,
        np.clip((radius - distance) / feather, 0.0, 1.0),
    )
    alpha *= valid_source.astype(np.float32) * opacity
    if not np.any(alpha > 0):
        return image.copy()

    safe_source_x = np.clip(source_grid_x, 0, width - 1)
    safe_source_y = np.clip(source_grid_y, 0, height - 1)
    source_patch = sampling_image[safe_source_y, safe_source_x].astype(np.float32)
    target_patch = image[top:bottom, left:right].astype(np.float32)
    color_channels = min(3, image.shape[2])
    if mode == "heal":
        weights = alpha[..., None]
        denominator = max(float(weights.sum()), 1e-6)
        source_mean = (source_patch[..., :color_channels] * weights).sum(axis=(0, 1)) / denominator
        target_mean = (target_patch[..., :color_channels] * weights).sum(axis=(0, 1)) / denominator
        source_patch[..., :color_channels] += target_mean - source_mean

    blended = target_patch * (1.0 - alpha[..., None]) + source_patch * alpha[..., None]
    result = image.copy()
    if np.issubdtype(image.dtype, np.integer):
        limits = np.iinfo(image.dtype)
        blended = np.clip(np.rint(blended), limits.min, limits.max).astype(image.dtype)
    else:
        blended = blended.astype(image.dtype)
    result[top:bottom, left:right] = blended
    return result


def apply_retouch_stroke(
    image: np.ndarray,
    source_anchor: Point,
    target_points: Iterable[Sequence[int]],
    radius: int,
    mode: str = "clone",
    opacity: float = 1.0,
    hardness: float = 0.65,
) -> np.ndarray:
    """Apply a stroke while preserving a fixed source-to-target offset."""
    points = [(int(point[0]), int(point[1])) for point in target_points]
    if not points:
        return image.copy()
    target_anchor = points[0]
    result = image.copy()
    previous = None
    for target_point in points:
        if target_point == previous:
            continue
        source_point = (
            int(source_anchor[0]) + target_point[0] - target_anchor[0],
            int(source_anchor[1]) + target_point[1] - target_anchor[1],
        )
        result = apply_retouch_dab(
            result,
            source_point,
            target_point,
            radius,
            mode=mode,
            opacity=opacity,
            hardness=hardness,
            source_image=image,
        )
        previous = target_point
    return result
