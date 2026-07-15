"""Conservative, local frame damage heuristics for review assistance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Optional

import cv2
import numpy as np

from .film_analysis import FilmPerforationDetector


@dataclass(frozen=True)
class DamageResult:
    status: str
    confidence: float
    note: str
    brightness: float
    contrast: float
    sharpness: float
    temporal_difference: float
    dust_ratio: float
    scratch_ratio: float
    color_cast: float
    possible_duplicate: bool
    perforation_count: int = 0
    perforation_confidence: float = 0.0
    registration_dx: float = 0.0
    registration_dy: float = 0.0
    possible_perforation_damage: bool = False

    def to_dict(self):
        return asdict(self)


class FrameDamageAnalyzer:
    """Flags suspicious frames without modifying image data."""

    SENSITIVITY = {
        "low": 1.45,
        "normal": 1.0,
        "high": 0.7,
    }

    def __init__(self, sensitivity: str = "normal"):
        if sensitivity not in self.SENSITIVITY:
            raise ValueError("Unknown damage sensitivity")
        self.factor = self.SENSITIVITY[sensitivity]
        self.perforation_detector = FilmPerforationDetector()

    def analyze(
        self,
        current: np.ndarray,
        previous: Optional[np.ndarray] = None,
        following: Optional[np.ndarray] = None,
    ) -> DamageResult:
        if current is None or current.size == 0:
            raise ValueError("Current frame is empty")
        gray = cv2.cvtColor(current, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))
        contrast = float(np.std(gray))
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        temporal_difference = 0.0
        dust_ratio = 0.0
        possible_duplicate = False
        reference = None
        if previous is not None and previous.shape == current.shape:
            previous_gray = cv2.cvtColor(previous, cv2.COLOR_BGR2GRAY)
            previous_difference = cv2.absdiff(gray, previous_gray)
            temporal_difference = float(np.mean(previous_difference))
            possible_duplicate = temporal_difference < 0.35 * self.factor
            reference = previous_gray
        if following is not None and following.shape == current.shape:
            following_gray = cv2.cvtColor(following, cv2.COLOR_BGR2GRAY)
            if reference is None:
                reference = following_gray
            else:
                reference = cv2.addWeighted(reference, 0.5, following_gray, 0.5, 0)
        if reference is not None:
            residual = cv2.absdiff(gray, reference)
            dust_ratio = float(np.count_nonzero(residual > 35 * self.factor) / residual.size)

        vertical_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 15))
        horizontal_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 1))
        vertical = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, vertical_kernel)
        horizontal = cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, horizontal_kernel)
        line_response = cv2.max(vertical, horizontal)
        scratch_ratio = float(
            np.count_nonzero(line_response > 28 * self.factor) / line_response.size
        )

        channel_means = np.mean(current.reshape(-1, 3), axis=0)
        color_cast = float(np.max(channel_means) - np.min(channel_means))

        perforations = self.perforation_detector.detect(current)
        registration_dx = 0.0
        registration_dy = 0.0
        possible_perforation_damage = False
        if previous is not None and previous.shape == current.shape:
            previous_perforations = self.perforation_detector.detect(previous)
            registration = self.perforation_detector.estimate_registration(previous, current)
            registration_dx = registration.dx
            registration_dy = registration.dy
            count_drop = (
                len(previous_perforations.perforations) >= 2
                and len(perforations.perforations)
                < max(1, int(len(previous_perforations.perforations) * 0.6))
            )
            large_shift = (
                registration.confidence >= 0.45
                and max(abs(registration.dx), abs(registration.dy)) > 4.0 * self.factor
            )
            possible_perforation_damage = count_drop or large_shift

        status = "unmarked"
        note = ""
        confidence = 0.0
        if brightness < 2.0 * self.factor or brightness > 253.0:
            status, note, confidence = "missing", "Frame quase vazio ou estourado", 0.95
        elif possible_perforation_damage:
            status, note = "perforation", "Perfurações ausentes ou deslocamento de película"
            confidence = max(0.6, perforations.confidence)
        elif scratch_ratio > 0.0025 * self.factor:
            status, note = "scratch", "Possíveis riscos lineares detectados"
            confidence = min(0.95, scratch_ratio / 0.01)
        elif dust_ratio > 0.004 * self.factor:
            status, note = "dust", "Diferenças pontuais em relação aos frames vizinhos"
            confidence = min(0.9, dust_ratio / 0.02)
        elif color_cast > 42 * self.factor:
            status, note = "stain", "Possível dominante de cor ou mancha"
            confidence = min(0.85, color_cast / 100.0)
        elif possible_duplicate:
            status, note, confidence = "review", "Possível frame duplicado", 0.7
        elif contrast < 8 * self.factor or sharpness < 12 * self.factor:
            status, note, confidence = "review", "Baixo contraste ou pouca definição", 0.55

        return DamageResult(
            status=status,
            confidence=round(confidence, 4),
            note=note,
            brightness=round(brightness, 4),
            contrast=round(contrast, 4),
            sharpness=round(sharpness, 4),
            temporal_difference=round(temporal_difference, 4),
            dust_ratio=round(dust_ratio, 6),
            scratch_ratio=round(scratch_ratio, 6),
            color_cast=round(color_cast, 4),
            possible_duplicate=possible_duplicate,
            perforation_count=len(perforations.perforations),
            perforation_confidence=perforations.confidence,
            registration_dx=registration_dx,
            registration_dy=registration_dy,
            possible_perforation_damage=possible_perforation_damage,
        )
