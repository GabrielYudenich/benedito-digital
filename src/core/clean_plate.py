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
    base_frame: np.ndarray | None = None,
    base_strategy: str = "median",
    progress_callback: Callable[[float], None] | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build a sharp clean plate and identify pixels belonging to a stable background."""
    if len(frames) < 3:
        raise ValueError("At least three frames are required for a clean plate")
    if base_strategy not in {"sharpest", "selected", "median"}:
        raise ValueError("Clean-plate base strategy is invalid")
    indices = np.linspace(
        0, len(frames) - 1, min(maximum_samples, len(frames)), dtype=int
    )
    sampled_frames = [frames[index] for index in indices]
    selected_sample = None
    if base_frame is not None:
        reference = base_frame
        effective_strategy = "selected"
    elif base_strategy == "sharpest":
        sharpness_scores = [_sharpness_score(frame) for frame in sampled_frames]
        selected_sample = int(np.argmax(sharpness_scores))
        reference = sampled_frames[selected_sample]
        effective_strategy = "sharpest"
    else:
        reference = frames[len(frames) // 2]
        effective_strategy = "median"
    height, width = reference.shape[:2]
    reference = cv2.resize(reference, (width, height), interpolation=cv2.INTER_AREA)
    aligned = []
    motions = []
    for position, frame in enumerate(sampled_frames):
        frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
        registered, motion, _warp = _align_translation(frame, reference)
        aligned.append(registered)
        motions.append(motion)
        if progress_callback:
            progress_callback((position + 1) * 55.0 / len(indices))
    stack = np.stack(aligned, axis=0)
    median_plate = np.median(stack, axis=0).astype(np.uint8)
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
    static_mask = _keep_components(
        static_mask,
        max(64, int(static_mask.size * 0.002)),
        static_mask.size,
    )
    nonstatic_mask = _keep_components(
        cv2.bitwise_not(static_mask),
        max(96, int(static_mask.size * 0.0015)),
        static_mask.size,
    )
    static_mask = cv2.bitwise_not(nonstatic_mask)
    static_mask = cv2.erode(static_mask, np.ones((5, 5), np.uint8), iterations=1)
    repaired_pixels = 0
    if effective_strategy == "median":
        plate = median_plate
        base = median_plate
    else:
        base = reference if base_frame is not None else sampled_frames[selected_sample]
        base = cv2.resize(base, (width, height), interpolation=cv2.INTER_AREA)
        plate = base.copy()
    static_ratio = float(np.count_nonzero(static_mask)) / static_mask.size
    mean_motion = float(np.mean(motions)) if motions else 0.0
    static_pixels = static_mask > 0
    diagnostics = {
        "samples": len(aligned),
        "static_ratio": static_ratio,
        "mean_camera_motion": mean_motion,
        "camera_static": static_ratio >= 0.45 and mean_motion <= max(width, height) * 0.025,
        "stability_threshold": stability_threshold,
        "base_strategy": effective_strategy,
        "base_sample": selected_sample,
        "base_sharpness": _sharpness_score(base, static_pixels),
        "median_sharpness": _sharpness_score(median_plate, static_pixels),
        "plate_sharpness": _sharpness_score(plate, static_pixels),
        "base_repaired_pixels": repaired_pixels,
    }
    if progress_callback:
        progress_callback(100.0)
    return plate, static_mask, diagnostics


def apply_clean_plate(
    current: np.ndarray,
    plate: np.ndarray,
    static_mask: np.ndarray,
    defect_mask: np.ndarray,
    *,
    application_mode: str = "defects",
) -> tuple[np.ndarray, dict]:
    """Replace only detected background defects and protect large foreground motion."""
    if application_mode not in {"defects", "background"}:
        raise ValueError("Clean-plate application mode is invalid")
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
    if application_mode == "background":
        plate = _match_plate_tone(plate, current, static_mask)
    difference = cv2.absdiff(current, plate)
    difference_gray = cv2.cvtColor(difference, cv2.COLOR_BGR2GRAY)
    dynamic_foreground = np.zeros(static_mask.shape, dtype=np.uint8)
    if application_mode == "background":
        foreground_candidate = np.where(
            difference_gray >= 28, 255, 0
        ).astype(np.uint8)
        foreground_candidate = cv2.morphologyEx(
            foreground_candidate,
            cv2.MORPH_CLOSE,
            np.ones((5, 5), np.uint8),
        )
        dynamic_foreground = _keep_components(
            foreground_candidate,
            max(192, int(height * width * 0.0007)),
            height * width,
            dilate=6,
        )
        foreground = cv2.bitwise_or(
            cv2.bitwise_not(static_mask), dynamic_foreground
        )
    else:
        foreground_candidate = np.where(
            difference_gray >= 24, 255, 0
        ).astype(np.uint8)
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
    feather = 6.0 if application_mode == "background" else 1.1
    alpha = cv2.GaussianBlur(effective, (0, 0), sigmaX=feather).astype(np.float32) / 255.0
    output = (
        current.astype(np.float32) * (1.0 - alpha[..., None])
        + plate.astype(np.float32) * alpha[..., None]
    )
    diagnostics = {
        "replaced_pixels": int(np.count_nonzero(effective)),
        "protected_foreground_pixels": int(np.count_nonzero(foreground)),
        "dynamic_foreground_pixels": int(np.count_nonzero(dynamic_foreground)),
        "plate_alignment_motion": plate_motion,
        "application_mode": application_mode,
    }
    return np.clip(output, 0, 255).astype(np.uint8), diagnostics


def make_transparent_plate(
    plate: np.ndarray,
    static_mask: np.ndarray,
) -> np.ndarray:
    """Return a BGRA plate whose alpha keeps only proven static background."""
    if plate.ndim != 3 or plate.shape[2] != 3:
        raise ValueError("Clean plate must be a three-channel image")
    alpha = cv2.resize(
        static_mask,
        (plate.shape[1], plate.shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )
    return np.dstack((plate, alpha.astype(np.uint8)))


def compose_plate_layer(
    source: np.ndarray,
    composite: np.ndarray,
    reveal_mask: np.ndarray | None = None,
    *,
    feather: float = 3.0,
) -> np.ndarray:
    """Reveal the untouched source through a reversible clean-plate layer mask."""
    height, width = composite.shape[:2]
    source = cv2.resize(source, (width, height), interpolation=cv2.INTER_CUBIC)
    if reveal_mask is None or not np.any(reveal_mask):
        return composite.copy()
    reveal_mask = cv2.resize(
        reveal_mask,
        (width, height),
        interpolation=cv2.INTER_NEAREST,
    )
    alpha = cv2.GaussianBlur(
        reveal_mask,
        (0, 0),
        sigmaX=max(0.1, float(feather)),
    ).astype(np.float32) / 255.0
    output = (
        composite.astype(np.float32) * (1.0 - alpha[..., None])
        + source.astype(np.float32) * alpha[..., None]
    )
    return np.clip(output, 0, 255).astype(np.uint8)


def restrict_defect_mask(
    defect_mask: np.ndarray,
    *,
    frame_selection: np.ndarray | None = None,
    application_region: np.ndarray | None = None,
) -> np.ndarray:
    """Limit plate application to a shared region or the current frame selection."""
    region = application_region if application_region is not None else frame_selection
    if region is None:
        return defect_mask
    region = cv2.resize(
        region,
        (defect_mask.shape[1], defect_mask.shape[0]),
        interpolation=cv2.INTER_NEAREST,
    )
    return cv2.bitwise_and(defect_mask, region)


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


def _sharpness_score(image: np.ndarray, mask: np.ndarray | None = None) -> float:
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    values = laplacian[mask] if mask is not None and np.any(mask) else laplacian
    return float(values.var())


def _match_plate_tone(
    plate: np.ndarray,
    current: np.ndarray,
    static_mask: np.ndarray,
) -> np.ndarray:
    valid = static_mask > 0
    if np.count_nonzero(valid) < 256:
        return plate
    matched = plate.astype(np.float32)
    current_float = current.astype(np.float32)
    for channel in range(min(3, plate.shape[2])):
        plate_values = matched[..., channel][valid]
        current_values = current_float[..., channel][valid]
        plate_mean = float(np.mean(plate_values))
        current_mean = float(np.mean(current_values))
        plate_std = max(1.0, float(np.std(plate_values)))
        current_std = max(1.0, float(np.std(current_values)))
        scale = float(np.clip(current_std / plate_std, 0.82, 1.22))
        matched[..., channel] = (
            matched[..., channel] - plate_mean
        ) * scale + current_mean
    return np.clip(matched, 0, 255).astype(np.uint8)


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
