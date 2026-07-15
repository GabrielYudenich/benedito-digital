"""Film perforation detection and frame registration helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

import cv2
import numpy as np


@dataclass(frozen=True)
class FilmPerforation:
    side: str
    bbox: Tuple[int, int, int, int]
    center: Tuple[float, float]
    score: float
    polarity: str


@dataclass(frozen=True)
class PerforationDetection:
    perforations: Tuple[FilmPerforation, ...]
    confidence: float
    left_count: int
    right_count: int


@dataclass(frozen=True)
class FilmRegistration:
    dx: float
    dy: float
    confidence: float
    matches: int


class FilmPerforationDetector:
    """Detect rectangular sprocket holes inside configurable side bands."""

    def __init__(self, border_ratio: float = 0.18):
        if not 0.05 <= border_ratio <= 0.35:
            raise ValueError("border_ratio must be between 0.05 and 0.35")
        self.border_ratio = border_ratio

    def detect(self, frame: np.ndarray) -> PerforationDetection:
        if frame is None or frame.size == 0:
            raise ValueError("Frame is empty")
        gray = self._gray(frame)
        height, width = gray.shape
        band_width = max(8, int(round(width * self.border_ratio)))
        candidates: List[FilmPerforation] = []
        for side, start, stop in (
            ("left", 0, band_width),
            ("right", width - band_width, width),
        ):
            candidates.extend(self._detect_band(gray[:, start:stop], side, start, width, height))

        selected = self._deduplicate(candidates)
        selected.sort(key=lambda item: (item.side, item.center[1]))
        left_count = sum(item.side == "left" for item in selected)
        right_count = len(selected) - left_count
        balance = 1.0
        if left_count and right_count:
            balance = min(left_count, right_count) / max(left_count, right_count)
        elif not selected:
            balance = 0.0
        mean_score = float(np.mean([item.score for item in selected])) if selected else 0.0
        count_score = min(1.0, len(selected) / 6.0)
        confidence = mean_score * 0.55 + count_score * 0.3 + balance * 0.15
        return PerforationDetection(
            perforations=tuple(selected),
            confidence=round(float(confidence), 4),
            left_count=left_count,
            right_count=right_count,
        )

    def estimate_registration(
        self, reference: np.ndarray, current: np.ndarray
    ) -> FilmRegistration:
        reference_detection = self.detect(reference)
        current_detection = self.detect(current)
        offsets = []
        for side in ("left", "right"):
            reference_side = [
                item for item in reference_detection.perforations if item.side == side
            ]
            current_side = [
                item for item in current_detection.perforations if item.side == side
            ]
            for reference_hole, current_hole in self._pair_by_vertical_position(
                reference_side, current_side
            ):
                offsets.append(
                    (
                        reference_hole.center[0] - current_hole.center[0],
                        reference_hole.center[1] - current_hole.center[1],
                    )
                )
        if not offsets:
            return FilmRegistration(0.0, 0.0, 0.0, 0)
        values = np.asarray(offsets, dtype=np.float32)
        median = np.median(values, axis=0)
        residual = np.linalg.norm(values - median, axis=1)
        consistent = residual <= max(2.0, float(np.median(residual)) * 2.5)
        filtered = values[consistent] if np.any(consistent) else values
        dx, dy = np.median(filtered, axis=0)
        detection_confidence = min(
            reference_detection.confidence, current_detection.confidence
        )
        match_confidence = min(1.0, len(filtered) / max(2, len(offsets)))
        confidence = detection_confidence * (0.55 + 0.45 * match_confidence)
        return FilmRegistration(
            dx=round(float(dx), 3),
            dy=round(float(dy), 3),
            confidence=round(float(confidence), 4),
            matches=int(len(filtered)),
        )

    def align_to_reference(
        self, reference: np.ndarray, current: np.ndarray
    ) -> Tuple[np.ndarray, FilmRegistration]:
        registration = self.estimate_registration(reference, current)
        if registration.matches == 0:
            return current.copy(), registration
        matrix = np.float32([[1, 0, registration.dx], [0, 1, registration.dy]])
        aligned = cv2.warpAffine(
            current,
            matrix,
            (current.shape[1], current.shape[0]),
            flags=cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        return aligned, registration

    def _detect_band(
        self,
        band: np.ndarray,
        side: str,
        x_offset: int,
        image_width: int,
        image_height: int,
    ) -> List[FilmPerforation]:
        blurred = cv2.GaussianBlur(band, (3, 3), 0)
        found = []
        for polarity, threshold_type in (
            ("light", cv2.THRESH_BINARY),
            ("dark", cv2.THRESH_BINARY_INV),
        ):
            _, binary = cv2.threshold(
                blurred, 0, 255, threshold_type | cv2.THRESH_OTSU
            )
            binary = cv2.morphologyEx(
                binary, cv2.MORPH_OPEN, np.ones((3, 3), dtype=np.uint8)
            )
            contours, _ = cv2.findContours(
                binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
            )
            for contour in contours:
                x, y, width, height = cv2.boundingRect(contour)
                area = float(cv2.contourArea(contour))
                rectangle_area = float(width * height)
                if not self._valid_geometry(
                    width, height, area, rectangle_area, band.shape[1], image_width, image_height
                ):
                    continue
                contrast = self._local_contrast(band, x, y, width, height)
                if contrast < 12.0:
                    continue
                rectangularity = min(1.0, area / max(1.0, rectangle_area))
                contrast_score = min(1.0, contrast / 80.0)
                score = rectangularity * 0.65 + contrast_score * 0.35
                found.append(
                    FilmPerforation(
                        side=side,
                        bbox=(x + x_offset, y, width, height),
                        center=(x + x_offset + width / 2.0, y + height / 2.0),
                        score=round(float(score), 4),
                        polarity=polarity,
                    )
                )
        return found

    @staticmethod
    def _valid_geometry(
        width: int,
        height: int,
        area: float,
        rectangle_area: float,
        band_width: int,
        image_width: int,
        image_height: int,
    ) -> bool:
        if rectangle_area <= 0:
            return False
        aspect = width / max(1.0, float(height))
        return (
            max(2, int(image_width * 0.006)) <= width <= int(band_width * 0.9)
            and max(3, int(image_height * 0.012)) <= height <= int(image_height * 0.18)
            and 0.2 <= aspect <= 2.5
            and area / rectangle_area >= 0.55
            and area >= image_width * image_height * 0.00006
        )

    @staticmethod
    def _local_contrast(
        image: np.ndarray, x: int, y: int, width: int, height: int
    ) -> float:
        padding = max(3, min(width, height) // 2)
        x0, y0 = max(0, x - padding), max(0, y - padding)
        x1 = min(image.shape[1], x + width + padding)
        y1 = min(image.shape[0], y + height + padding)
        outer = image[y0:y1, x0:x1]
        inner = image[y : y + height, x : x + width]
        if outer.size == 0 or inner.size == 0:
            return 0.0
        return abs(float(np.mean(inner)) - float(np.mean(outer)))

    @staticmethod
    def _deduplicate(candidates: Iterable[FilmPerforation]) -> List[FilmPerforation]:
        selected: List[FilmPerforation] = []
        for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
            if any(
                candidate.side == existing.side
                and abs(candidate.center[0] - existing.center[0]) < max(candidate.bbox[2], existing.bbox[2])
                and abs(candidate.center[1] - existing.center[1]) < max(candidate.bbox[3], existing.bbox[3])
                for existing in selected
            ):
                continue
            selected.append(candidate)
        return selected

    @staticmethod
    def _pair_by_vertical_position(
        reference: Sequence[FilmPerforation], current: Sequence[FilmPerforation]
    ) -> List[Tuple[FilmPerforation, FilmPerforation]]:
        if not reference or not current:
            return []
        remaining = list(current)
        pairs = []
        for reference_hole in reference:
            nearest = min(
                remaining,
                key=lambda item: abs(item.center[1] - reference_hole.center[1]),
            )
            pairs.append((reference_hole, nearest))
            remaining.remove(nearest)
            if not remaining:
                break
        return pairs

    @staticmethod
    def _gray(frame: np.ndarray) -> np.ndarray:
        if frame.ndim == 2:
            return frame.astype(np.uint8, copy=False)
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
