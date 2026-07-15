"""Storage estimates and preflight checks for large local media."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Union


PathLike = Union[str, Path]
MIB = 1024 * 1024
GIB = 1024 * MIB


class InsufficientStorageError(Exception):
    """Raised before a large operation when free storage is insufficient."""


@dataclass(frozen=True)
class StoragePreflight:
    destination: Path
    payload_bytes: int
    reserve_bytes: int
    available_bytes: int

    @property
    def required_bytes(self) -> int:
        return self.payload_bytes + self.reserve_bytes

    @property
    def enough(self) -> bool:
        return self.available_bytes >= self.required_bytes


def storage_preflight(
    destination: PathLike,
    payload_bytes: int,
    *,
    reserve_bytes: int | None = None,
) -> StoragePreflight:
    destination_path = _existing_parent(Path(destination).expanduser().resolve())
    payload = max(0, int(payload_bytes))
    reserve = (
        max(512 * MIB, round(payload * 0.05))
        if reserve_bytes is None
        else max(0, int(reserve_bytes))
    )
    available = shutil.disk_usage(destination_path).free
    return StoragePreflight(destination_path, payload, reserve, available)


def require_free_space(
    destination: PathLike,
    payload_bytes: int,
    *,
    reserve_bytes: int | None = None,
) -> StoragePreflight:
    result = storage_preflight(
        destination, payload_bytes, reserve_bytes=reserve_bytes
    )
    if not result.enough:
        raise InsufficientStorageError(
            "Espaço insuficiente: a operação precisa de aproximadamente "
            f"{format_bytes(result.required_bytes)}, mas há "
            f"{format_bytes(result.available_bytes)} livres em {result.destination}"
        )
    return result


def estimate_lossless_video_bytes(
    duration: float,
    fps: float,
    width: int,
    height: int,
    *,
    source_size: int = 0,
    source_duration: float = 0,
) -> int:
    seconds = max(0.0, float(duration))
    raw_video = seconds * max(0.0, float(fps)) * max(0, int(width)) * max(0, int(height)) * 3
    proportional_source = (
        max(0, int(source_size)) * seconds / float(source_duration)
        if source_duration > 0
        else 0
    )
    return round(max(proportional_source * 1.25, raw_video * 0.8, 64 * MIB))


def estimate_lossless_frames_bytes(
    duration: float, fps: float, width: int, height: int
) -> int:
    frame_count = max(0.0, float(duration)) * max(0.0, float(fps))
    return round(frame_count * max(0, int(width)) * max(0, int(height)) * 3 * 1.05)


def format_bytes(value: int) -> str:
    size = float(max(0, int(value)))
    for suffix in ("B", "KiB", "MiB", "GiB", "TiB"):
        if size < 1024 or suffix == "TiB":
            return f"{size:.0f} {suffix}" if suffix == "B" else f"{size:.1f} {suffix}"
        size /= 1024
    return f"{size:.1f} TiB"


def _existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    if not candidate.exists():
        raise OSError(f"Não foi possível localizar o disco de destino: {path}")
    return candidate
