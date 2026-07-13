"""Typed keyframe curves with deterministic interpolation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List


@dataclass(frozen=True, order=True)
class Keyframe:
    time: float
    value: float
    interpolation: str = "linear"

    def __post_init__(self):
        if self.time < 0:
            raise ValueError("Keyframe time cannot be negative")
        if self.interpolation not in {"step", "linear", "smooth"}:
            raise ValueError("Unsupported keyframe interpolation")


class KeyframeCurve:
    def __init__(self, keyframes: Iterable[Keyframe] = ()):
        self._keyframes: List[Keyframe] = []
        for keyframe in keyframes:
            self.set(keyframe.time, keyframe.value, keyframe.interpolation)

    @property
    def keyframes(self):
        return tuple(self._keyframes)

    def set(self, time: float, value: float, interpolation: str = "linear") -> Keyframe:
        keyframe = Keyframe(float(time), float(value), interpolation)
        self._keyframes = [item for item in self._keyframes if item.time != keyframe.time]
        self._keyframes.append(keyframe)
        self._keyframes.sort(key=lambda item: item.time)
        return keyframe

    def remove(self, time: float) -> bool:
        before = len(self._keyframes)
        self._keyframes = [item for item in self._keyframes if item.time != float(time)]
        return len(self._keyframes) != before

    def evaluate(self, time: float, default: float = 0.0) -> float:
        if not self._keyframes:
            return float(default)
        value_time = float(time)
        if value_time <= self._keyframes[0].time:
            return self._keyframes[0].value
        if value_time >= self._keyframes[-1].time:
            return self._keyframes[-1].value
        for left, right in zip(self._keyframes, self._keyframes[1:]):
            if left.time <= value_time <= right.time:
                if left.interpolation == "step":
                    return left.value
                position = (value_time - left.time) / (right.time - left.time)
                if left.interpolation == "smooth":
                    position = position * position * (3.0 - 2.0 * position)
                return left.value + (right.value - left.value) * position
        return self._keyframes[-1].value

    def to_list(self):
        return [
            {"time": item.time, "value": item.value, "interpolation": item.interpolation}
            for item in self._keyframes
        ]

    @classmethod
    def from_list(cls, values):
        if not isinstance(values, list):
            raise ValueError("Keyframe payload must be a list")
        return cls(
            Keyframe(
                float(item["time"]),
                float(item["value"]),
                str(item.get("interpolation", "linear")),
            )
            for item in values
        )
