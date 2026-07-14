"""Detection and local persistence of camera-position frame ranges."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

import cv2
import numpy as np


@dataclass(frozen=True)
class CameraSegment:
    id: str
    name: str
    start: int
    end: int
    kind: str = "camera_position"
    confidence: float = 1.0

    @classmethod
    def create(cls, name: str, start: int, end: int, confidence: float = 1.0):
        if start < 0 or end < start:
            raise ValueError("Invalid camera-position range")
        return cls(
            uuid.uuid4().hex,
            name.strip() or "Posicionamento",
            start,
            end,
            "camera_position",
            confidence,
        )


class CameraSegmentStore:
    VERSION = 1

    def __init__(self, project_path):
        self.path = Path(project_path) / "metadata" / "camera_segments.json"

    def list(self, source_name: str) -> list[CameraSegment]:
        data = self._read()
        result = []
        for value in data["sources"].get(source_name, []):
            try:
                result.append(CameraSegment(**value))
            except (TypeError, ValueError):
                continue
        return sorted(result, key=lambda item: (item.start, item.end, item.name))

    def replace(self, source_name: str, segments: Iterable[CameraSegment]) -> None:
        data = self._read()
        data["sources"][source_name] = [asdict(segment) for segment in segments]
        self._write(data)

    def add(self, source_name: str, segment: CameraSegment) -> None:
        segments = [item for item in self.list(source_name) if item.id != segment.id]
        segments.append(segment)
        self.replace(source_name, segments)

    def delete(self, source_name: str, segment_id: str) -> None:
        self.replace(
            source_name,
            [item for item in self.list(source_name) if item.id != segment_id],
        )

    def _read(self):
        if not self.path.exists():
            return {"version": self.VERSION, "sources": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("version") == self.VERSION and isinstance(value.get("sources"), dict):
                return value
        except (OSError, json.JSONDecodeError):
            pass
        return {"version": self.VERSION, "sources": {}}

    def _write(self, value):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f".{self.path.name}.{uuid.uuid4().hex}.tmp")
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(temporary, self.path)


def detect_camera_segments(
    frame_paths: list[str],
    *,
    threshold: float = 0.16,
    minimum_length: int = 12,
    progress_callback: Callable[[float], None] | None = None,
    cancel_callback: Callable[[], bool] | None = None,
) -> list[CameraSegment]:
    """Find strong visual cuts without loading the full sequence into memory."""
    total = len(frame_paths)
    if total == 0:
        return []
    if total == 1:
        return [CameraSegment.create("Posicionamento 1", 0, 0)]
    sample_step = max(1, total // 360)
    sampled = list(range(0, total, sample_step))
    if sampled[-1] != total - 1:
        sampled.append(total - 1)
    signatures = {}
    for position, index in enumerate(sampled):
        if cancel_callback and cancel_callback():
            raise RuntimeError("Detecção de posicionamentos cancelada")
        signatures[index] = _frame_signature(frame_paths[index])
        if progress_callback:
            progress_callback((position + 1) * 65.0 / len(sampled))

    sampled_scores = [
        _signature_distance(signatures[previous_index], signatures[index])
        for previous_index, index in zip(sampled, sampled[1:])
    ]
    median_score = float(np.median(sampled_scores)) if sampled_scores else 0.0
    mad = (
        float(np.median(np.abs(np.asarray(sampled_scores) - median_score)))
        if sampled_scores
        else 0.0
    )
    effective_threshold = max(float(threshold), median_score + max(0.025, mad * 3.0))
    candidates = []
    sampled_pairs = list(zip(sampled, sampled[1:]))
    for pair_position, (previous_index, index) in enumerate(sampled_pairs):
        if cancel_callback and cancel_callback():
            raise RuntimeError("Detecção de posicionamentos cancelada")
        score = sampled_scores[pair_position]
        previous_score = sampled_scores[pair_position - 1] if pair_position else -1.0
        next_score = (
            sampled_scores[pair_position + 1]
            if pair_position + 1 < len(sampled_scores)
            else -1.0
        )
        if score >= effective_threshold and score >= previous_score and score >= next_score:
            search_start = max(previous_index + 1, index - sample_step + 1)
            search_end = min(total - 1, index)
            best_index = index
            best_score = -1.0
            previous_signature = _frame_signature(frame_paths[search_start - 1])
            for candidate in range(search_start, search_end + 1):
                if cancel_callback and cancel_callback():
                    raise RuntimeError("Detecção de posicionamentos cancelada")
                current_signature = _frame_signature(frame_paths[candidate])
                candidate_score = _signature_distance(previous_signature, current_signature)
                if candidate_score > best_score:
                    best_index, best_score = candidate, candidate_score
                previous_signature = current_signature
            candidates.append((best_index, max(score, best_score)))
        if progress_callback:
            progress_callback(
                65.0 + (pair_position + 1) * 30.0 / max(1, len(sampled_pairs))
            )

    boundaries = [0]
    for index, score in sorted(candidates):
        if (
            index - boundaries[-1] >= minimum_length
            and total - index >= minimum_length
            and score >= effective_threshold * 0.72
        ):
            boundaries.append(index)
    boundaries.append(total)
    segments = []
    for position, (start, stop) in enumerate(zip(boundaries, boundaries[1:]), 1):
        if stop <= start:
            continue
        segments.append(
            CameraSegment.create(
                f"Posicionamento {position}",
                start,
                stop - 1,
                confidence=min(0.99, max(0.55, effective_threshold + 0.55)),
            )
        )
    if progress_callback:
        progress_callback(100.0)
    return segments


def _frame_signature(path: str):
    image = cv2.imread(path, cv2.IMREAD_REDUCED_GRAYSCALE_8)
    if image is None:
        raise FileNotFoundError(path)
    thumbnail = cv2.resize(image, (96, 54), interpolation=cv2.INTER_AREA)
    layout = cv2.GaussianBlur(thumbnail, (9, 9), 0)
    edges = cv2.Canny(layout, 35, 100)
    histogram = cv2.calcHist([thumbnail], [0], None, [32], [0, 256])
    cv2.normalize(histogram, histogram)
    return layout, edges, histogram


def _signature_distance(first, second) -> float:
    first_image, first_edges, first_histogram = first
    second_image, second_edges, second_histogram = second
    image_difference = float(
        np.mean(cv2.absdiff(first_image, second_image)) / 255.0
    )
    histogram_difference = float(
        cv2.compareHist(first_histogram, second_histogram, cv2.HISTCMP_BHATTACHARYYA)
    )
    edge_difference = float(
        np.mean(cv2.absdiff(first_edges, second_edges)) / 255.0
    )
    correlation = float(
        cv2.matchTemplate(first_image, second_image, cv2.TM_CCOEFF_NORMED)[0, 0]
    )
    correlation_difference = max(0.0, min(1.0, 1.0 - correlation))
    return (
        image_difference * 0.46
        + correlation_difference * 0.29
        + edge_difference * 0.18
        + histogram_difference * 0.07
    )
