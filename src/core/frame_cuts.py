"""Non-destructive useful-range metadata for frame sequences."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UsefulFrameRange:
    start: int
    end: int

    def normalized(self, total: int) -> "UsefulFrameRange":
        last = max(0, int(total) - 1)
        start = max(0, min(int(self.start), last))
        end = max(start, min(int(self.end), last))
        return UsefulFrameRange(start, end)

    def contains(self, frame_index: int) -> bool:
        return self.start <= int(frame_index) <= self.end


class FrameCutStore:
    VERSION = 1

    def __init__(self, project_path):
        self.path = Path(project_path) / "metadata" / "frame_cuts.json"

    def get(self, source_name: str, total: int) -> UsefulFrameRange:
        default = UsefulFrameRange(0, max(0, int(total) - 1))
        value = self._read()["sources"].get(source_name)
        if not isinstance(value, dict):
            return default
        try:
            return UsefulFrameRange(int(value["start"]), int(value["end"])).normalized(
                total
            )
        except (KeyError, TypeError, ValueError):
            return default

    def set(self, source_name: str, start: int, end: int, total: int) -> UsefulFrameRange:
        useful_range = UsefulFrameRange(start, end).normalized(total)
        data = self._read()
        data["sources"][source_name] = {
            "start": useful_range.start,
            "end": useful_range.end,
        }
        self._write(data)
        return useful_range

    def reset(self, source_name: str) -> None:
        data = self._read()
        data["sources"].pop(source_name, None)
        self._write(data)

    def _read(self):
        if not self.path.exists():
            return {"version": self.VERSION, "sources": {}}
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if value.get("version") == self.VERSION and isinstance(
                value.get("sources"), dict
            ):
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
