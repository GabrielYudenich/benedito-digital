"""Temporally stable luminance and contrast normalization."""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class LumaProfile:
    low: float
    middle: float
    high: float


def measure_luma_profile(frame: np.ndarray) -> LumaProfile:
    """Measure robust shadow, midpoint and highlight levels."""
    luminance = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)[..., 0]
    height, width = luminance.shape
    margin_y = max(0, int(height * 0.04))
    margin_x = max(0, int(width * 0.04))
    sample = luminance[
        margin_y : max(margin_y + 1, height - margin_y),
        margin_x : max(margin_x + 1, width - margin_x),
    ].reshape(-1)
    useful = sample[(sample > 2) & (sample < 253)]
    if useful.size >= 256:
        sample = useful
    low, middle, high = np.percentile(sample, (5, 50, 95))
    return LumaProfile(float(low), float(middle), float(high))


def median_luma_profile(profiles: list[LumaProfile]) -> LumaProfile:
    """Return one stable target profile for a complete shot or position."""
    if not profiles:
        raise ValueError("At least one luminance profile is required")
    return LumaProfile(
        float(np.median([profile.low for profile in profiles])),
        float(np.median([profile.middle for profile in profiles])),
        float(np.median([profile.high for profile in profiles])),
    )


def smooth_luma_profiles(
    profiles: list[LumaProfile],
    *,
    radius: int = 4,
) -> list[LumaProfile]:
    """Suppress subject-driven exposure jumps before normalizing frames."""
    if not profiles:
        return []
    radius = max(0, int(radius))
    smoothed = []
    for index in range(len(profiles)):
        start = max(0, index - radius)
        end = min(len(profiles), index + radius + 1)
        smoothed.append(median_luma_profile(profiles[start:end]))
    return smoothed


def normalize_frame_luma(
    frame: np.ndarray,
    target: LumaProfile,
    *,
    source: LumaProfile | None = None,
    strength: float = 0.85,
) -> np.ndarray:
    """Match one frame to a target profile while preserving color channels."""
    source = source or measure_luma_profile(frame)
    strength = float(np.clip(strength, 0.0, 1.0))
    if strength <= 0:
        return frame.copy()
    source_points = _strict_points(source)
    target_points = _strict_points(target)
    lookup = np.interp(
        np.arange(256, dtype=np.float32),
        source_points,
        target_points,
    )
    lookup = (
        np.arange(256, dtype=np.float32) * (1.0 - strength)
        + lookup * strength
    )
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    lab[..., 0] = np.clip(lookup[lab[..., 0]], 0, 255).astype(np.uint8)
    return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)


def _strict_points(profile: LumaProfile) -> np.ndarray:
    low = float(np.clip(profile.low, 1.0, 248.0))
    middle = float(np.clip(profile.middle, low + 1.0, 250.0))
    high = float(np.clip(profile.high, middle + 1.0, 254.0))
    return np.array((0.0, low, middle, high, 255.0), dtype=np.float32)
