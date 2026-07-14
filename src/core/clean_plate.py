"""Conservative clean-plate generation with foreground protection."""

from __future__ import annotations

from typing import Callable

import cv2
import numpy as np


def detect_transient_defects(
    previous: np.ndarray | None,
    current: np.ndarray,
    following: np.ndarray | None,
    *,
    maximum_component_ratio: float = 0.002,
) -> np.ndarray:
    """Detect small temporal defects while rejecting edges and large motion."""
    if previous is None or following is None:
        return np.zeros(current.shape[:2], dtype=np.uint8)
    height, width = current.shape[:2]
    previous = cv2.resize(previous, (width, height), interpolation=cv2.INTER_AREA)
    following = cv2.resize(following, (width, height), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
    previous_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
    following_gray = cv2.cvtColor(following, cv2.COLOR_BGR2GRAY)
    temporal_median = np.median(
        np.stack([previous_gray, gray, following_gray], axis=0), axis=0
    ).astype(np.uint8)
    transient = cv2.absdiff(gray, temporal_median)
    blackhat = cv2.morphologyEx(
        gray,
        cv2.MORPH_BLACKHAT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    tophat = cv2.morphologyEx(
        gray,
        cv2.MORPH_TOPHAT,
        cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
    )
    spatial = cv2.max(blackhat, tophat)
    transient_threshold = max(10, int(np.percentile(transient, 96)))
    spatial_threshold = max(7, int(np.percentile(spatial, 90)))
    candidate = np.where(
        (transient >= transient_threshold) & (spatial >= spatial_threshold), 255, 0
    ).astype(np.uint8)
    candidate = cv2.morphologyEx(
        candidate, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8)
    )
    maximum_area = max(24, int(height * width * maximum_component_ratio))
    return _keep_components(candidate, 1, maximum_area, dilate=1)


def build_clean_plate(
    frames: list[np.ndarray],
    *,
    maximum_samples: int = 15,
    progress_callback: Callable[[float], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build a median plate and identify pixels belonging to a stable background."""
    if len(frames) < 3:
        raise ValueError("At least three frames are required for a clean plate")
    indices = np.linspace(
        0, len(frames) - 1, min(maximum_samples, len(frames)), dtype=int
    )
    reference = frames[len(frames) // 2]
    height, width = reference.shape[:2]
    aligned = []
    motions = []
    for position, index in enumerate(indices):
        frame = cv2.resize(frames[index], (width, height), interpolation=cv2.INTER_AREA)
        registered, motion, _warp = _align_translation(frame, reference)
        aligned.append(registered)
        motions.append(motion)
        if progress_callback:
            progress_callback((position + 1) * 55.0 / len(indices))
    stack = np.stack(aligned, axis=0)
    plate = np.median(stack, axis=0).astype(np.uint8)
    gray_stack = np.stack(
        [cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) for frame in aligned], axis=0
    ).astype(np.float32)
    gray_median = np.median(gray_stack, axis=0)
    deviation = np.median(np.abs(gray_stack - gray_median), axis=0)
    stability_threshold = max(5.0, min(16.0, float(np.percentile(deviation, 68)) + 2.0))
    static_mask = np.where(deviation <= stability_threshold, 255, 0).astype(np.uint8)
    static_mask = cv2.morphologyEx(
        static_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8)
    )
    static_mask = cv2.morphologyEx(
        static_mask, cv2.MORPH_CLOSE, np.ones((7, 7), np.uint8)
    )
    static_ratio = float(np.count_nonzero(static_mask)) / static_mask.size
    mean_motion = float(np.mean(motions)) if motions else 0.0
    diagnostics = {
        "samples": len(aligned),
        "static_ratio": static_ratio,
        "mean_camera_motion": mean_motion,
        "camera_static": static_ratio >= 0.45 and mean_motion <= max(width, height) * 0.025,
        "stability_threshold": stability_threshold,
    }
    if progress_callback:
        progress_callback(100.0)
    return plate, static_mask, diagnostics


def apply_clean_plate(
    current: np.ndarray,
    plate: np.ndarray,
    static_mask: np.ndarray,
    defect_mask: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Replace only detected background defects and protect large foreground motion."""
    height, width = current.shape[:2]
    plate = cv2.resize(plate, (width, height), interpolation=cv2.INTER_CUBIC)
    static_mask = cv2.resize(
        static_mask, (width, height), interpolation=cv2.INTER_NEAREST
    )
    defect_mask = cv2.resize(
        defect_mask, (width, height), interpolation=cv2.INTER_NEAREST
    )
    plate, plate_motion, warp = _align_translation(plate, current)
    if warp is not None:
        static_mask = cv2.warpAffine(
            static_mask,
            warp,
            (width, height),
            flags=cv2.INTER_NEAREST | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
    difference = cv2.absdiff(current, plate)
    difference_gray = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY)
    foreground_candidate = np.where(difference_gray >= 24, 255, 0).astype(np.uint8)
    minimum_foreground_area = max(96, int(height * width * 0.0006))
    foreground = _keep_components(
        foreground_candidate,
        minimum_foreground_area,
        height * width,
        dilate=4,
    )
    effective = cv2.bitwise_and(defect_mask, static_mask)
    effective = cv2.bitwise_and(effective, cv2.bitwise_not(foreground))
    effective = cv2.dilate(effective, np.ones((3, 3), np.uint8), iterations=1)
    alpha = cv2.GaussianBlur(effective, (0, 0), sigmaX=1.1).astype(np.float32) / 255.0
    output = (
        current.astype(np.float32) * (1.0 - alpha[..., None])
        + plate.astype(np.float32) * alpha[..., None]
    )
    diagnostics = {
        "replaced_pixels": int(np.count_nonzero(effective)),
        "protected_foreground_pixels": int(np.count_nonzero(foreground)),
        "plate_alignment_motion": plate_motion,
    }
    return np.clip(output, 0, 255).astype(np.uint8), diagnostics


def _align_translation(frame: np.ndarray, reference: np.ndarray):
    height, width = reference.shape[:2]
    scale = min(1.0, 320.0 / max(width, height))
    small_size = (max(16, int(width * scale)), max(16, int(height * scale)))
    reference_gray = cv2.resize(
        cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY), small_size
    ).astype(np.float32)
    frame_gray = cv2.resize(
        cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), small_size
    ).astype(np.float32)
    warp = np.eye(2, 3, dtype=np.float32)
    try:
        cv2.findTransformECC(
            reference_gray,
            frame_gray,
            warp,
            cv2.MOTION_TRANSLATION,
            (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 30, 1e-5),
        )
        warp[0, 2] /= scale
        warp[1, 2] /= scale
        aligned = cv2.warpAffine(
            frame,
            warp,
            (width, height),
            flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP,
            borderMode=cv2.BORDER_REFLECT,
        )
        motion = float(np.hypot(warp[0, 2], warp[1, 2]))
        return aligned, motion, warp
    except cv2.error:
        return frame, 0.0, None


def _keep_components(mask, minimum_area, maximum_area, *, dilate=0):
    count, labels, stats, _centroids = cv2.connectedComponentsWithStats(
        (mask > 0).astype(np.uint8), connectivity=8
    )
    output = np.zeros(mask.shape, dtype=np.uint8)
    for label in range(1, count):
        area = int(stats[label, cv2.CC_STAT_AREA])
        if minimum_area <= area <= maximum_area:
            output[labels == label] = 255
    if dilate:
        output = cv2.dilate(
            output, np.ones((3, 3), np.uint8), iterations=int(dilate)
        )
    return output
