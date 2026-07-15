import sys
from pathlib import Path

import cv2
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.tone_normalization import (
    measure_luma_profile,
    median_luma_profile,
    normalize_frame_luma,
    smooth_luma_profiles,
)


def _frame(offset):
    gradient = np.tile(np.linspace(25, 220, 240, dtype=np.float32), (140, 1))
    image = np.clip(gradient + offset, 0, 255).astype(np.uint8)
    return cv2.merge((image, image, image))


def test_temporal_normalization_reduces_luminance_variation():
    frames = [_frame(offset) for offset in (-22, -10, 0, 13, 25)]
    profiles = [measure_luma_profile(frame) for frame in frames]
    target = median_luma_profile(profiles)
    smoothed = smooth_luma_profiles(profiles, radius=1)

    normalized = [
        normalize_frame_luma(frame, target, source=profile, strength=1.0)
        for frame, profile in zip(frames, smoothed)
    ]
    before = np.std([profile.middle for profile in profiles])
    after = np.std(
        [measure_luma_profile(frame).middle for frame in normalized]
    )

    assert after < before * 0.35


def test_zero_strength_preserves_frame_exactly():
    frame = _frame(18)
    target = measure_luma_profile(_frame(-12))

    normalized = normalize_frame_luma(frame, target, strength=0.0)

    assert np.array_equal(normalized, frame)


def test_profile_smoothing_rejects_single_exposure_spike():
    profiles = [measure_luma_profile(_frame(0)) for _ in range(7)]
    profiles[3] = measure_luma_profile(_frame(55))

    smoothed = smooth_luma_profiles(profiles, radius=2)

    assert abs(smoothed[3].middle - profiles[0].middle) < 1.0
