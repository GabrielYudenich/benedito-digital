"""Local RGB histogram, luma waveform, and vectorscope rendering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import cv2
import numpy as np


@dataclass(frozen=True)
class ScopeStatistics:
    luma_min: int
    luma_max: int
    luma_mean: float
    clipped_black: float
    clipped_white: float


class ColorScopeGenerator:
    def __init__(self, width=512, height=256):
        if width < 128 or height < 128:
            raise ValueError("Scope dimensions are too small")
        self.width = int(width)
        self.height = int(height)

    def generate(self, frame: np.ndarray) -> Dict[str, object]:
        if frame is None or frame.size == 0:
            raise ValueError("Frame is empty")
        bgr = self._bgr(frame)
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        statistics = ScopeStatistics(
            luma_min=int(gray.min()),
            luma_max=int(gray.max()),
            luma_mean=round(float(gray.mean()), 3),
            clipped_black=round(float(np.count_nonzero(gray <= 2) / gray.size), 6),
            clipped_white=round(float(np.count_nonzero(gray >= 253) / gray.size), 6),
        )
        return {
            "histogram": self.histogram_rgb(bgr),
            "waveform": self.waveform_luma(gray),
            "vectorscope": self.vectorscope(bgr),
            "statistics": statistics,
        }

    def histogram_rgb(self, frame: np.ndarray) -> np.ndarray:
        canvas = np.full((self.height, self.width, 3), 12, dtype=np.uint8)
        colors = ((255, 90, 70), (80, 230, 100), (70, 100, 255))
        for channel, color in enumerate(colors):
            histogram = cv2.calcHist([frame], [channel], None, [256], [0, 256]).ravel()
            histogram = np.log1p(histogram)
            maximum = float(histogram.max()) or 1.0
            values = histogram / maximum
            points = np.column_stack(
                (
                    np.linspace(0, self.width - 1, 256),
                    (self.height - 1) - values * (self.height - 12),
                )
            ).astype(np.int32)
            cv2.polylines(canvas, [points], False, color, 1, cv2.LINE_AA)
        self._grid(canvas)
        return canvas

    def waveform_luma(self, gray: np.ndarray) -> np.ndarray:
        reduced = cv2.resize(gray, (self.width, max(1, min(gray.shape[0], 360))), interpolation=cv2.INTER_AREA)
        density = np.zeros((256, self.width), dtype=np.float32)
        x_values = np.tile(np.arange(self.width), reduced.shape[0])
        y_values = reduced.reshape(-1)
        np.add.at(density, (255 - y_values, x_values), 1)
        density = np.log1p(density)
        density /= float(density.max()) or 1.0
        density = cv2.resize(density, (self.width, self.height), interpolation=cv2.INTER_LINEAR)
        canvas = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        canvas[:, :, 1] = np.clip(density * 255, 0, 255).astype(np.uint8)
        canvas[:, :, 0] = np.clip(density * 110, 0, 255).astype(np.uint8)
        self._grid(canvas)
        return canvas

    def vectorscope(self, frame: np.ndarray) -> np.ndarray:
        ycrcb = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        sampled = cv2.resize(ycrcb, (min(640, frame.shape[1]), min(360, frame.shape[0])), interpolation=cv2.INTER_AREA)
        cr = sampled[:, :, 1].reshape(-1)
        cb = sampled[:, :, 2].reshape(-1)
        density = np.zeros((256, 256), dtype=np.float32)
        np.add.at(density, (255 - cr, cb), 1)
        density = np.log1p(density)
        density /= float(density.max()) or 1.0
        square = min(self.width, self.height)
        density = cv2.resize(density, (square, square), interpolation=cv2.INTER_LINEAR)
        canvas = np.full((self.height, self.width, 3), 8, dtype=np.uint8)
        x0 = (self.width - square) // 2
        scope = np.zeros((square, square, 3), dtype=np.uint8)
        scope[:, :, 1] = np.clip(density * 245, 0, 255).astype(np.uint8)
        scope[:, :, 2] = np.clip(density * 170, 0, 255).astype(np.uint8)
        canvas[:, x0 : x0 + square] = scope
        center = (self.width // 2, self.height // 2)
        cv2.circle(canvas, center, int(square * 0.38), (80, 80, 80), 1, cv2.LINE_AA)
        cv2.line(canvas, (center[0], 0), (center[0], self.height - 1), (55, 55, 55), 1)
        cv2.line(canvas, (x0, center[1]), (x0 + square - 1, center[1]), (55, 55, 55), 1)
        return canvas

    @staticmethod
    def _grid(canvas):
        for fraction in (0.25, 0.5, 0.75):
            y = int((canvas.shape[0] - 1) * fraction)
            cv2.line(canvas, (0, y), (canvas.shape[1] - 1, y), (45, 45, 45), 1)

    @staticmethod
    def _bgr(frame):
        if frame.ndim == 2:
            return cv2.cvtColor(frame.astype(np.uint8, copy=False), cv2.COLOR_GRAY2BGR)
        if frame.shape[2] == 4:
            return cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
        return frame
