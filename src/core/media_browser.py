"""Media-browser helpers for source-specific, paginated frame sequences."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


FRAME_EXTENSIONS = {".jpg", ".jpeg", ".png"}


@dataclass(frozen=True)
class FramePage:
    number: int
    start_index: int
    end_index: int
    files: tuple[str, ...]


def media_frame_directory_name(video_name: str) -> str:
    stem = Path(str(video_name)).stem
    safe_stem = re.sub(r"[^A-Za-z0-9À-ÿ._-]+", "_", stem).strip("._")
    safe_stem = safe_stem[:64] or "midia"
    digest = hashlib.sha256(str(video_name).encode("utf-8")).hexdigest()[:10]
    return f"{safe_stem}-{digest}"


def list_frame_files(frames_dir) -> list[str]:
    directory = Path(frames_dir)
    if not directory.is_dir():
        return []
    files = [
        path.name
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in FRAME_EXTENSIONS
    ]
    return sorted(files, key=_natural_frame_key)


def paginate_frame_files(frames_dir, page_size: int = 100) -> list[FramePage]:
    if page_size <= 0:
        raise ValueError("page_size must be positive")
    files = list_frame_files(frames_dir)
    pages = []
    for offset in range(0, len(files), page_size):
        page_files = tuple(files[offset : offset + page_size])
        pages.append(
            FramePage(
                number=(offset // page_size) + 1,
                start_index=offset,
                end_index=offset + len(page_files) - 1,
                files=page_files,
            )
        )
    return pages


def _natural_frame_key(filename: str):
    parts = re.split(r"(\d+)", filename.lower())
    return tuple(int(part) if part.isdigit() else part for part in parts)
