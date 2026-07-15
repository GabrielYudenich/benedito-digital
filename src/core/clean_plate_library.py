"""Discovery helpers for editable clean plates stored in a project worktree."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
from pathlib import Path
from typing import Iterable, Mapping


@dataclass(frozen=True)
class CleanPlateRecord:
    plate_id: str
    directory: Path
    plate_path: Path
    static_mask_path: Path
    transparent_plate_path: Path | None
    application_region_path: Path | None
    layer_metadata_path: Path | None
    source: str
    start: int
    end: int
    diagnostics: Mapping[str, object]
    created_at: str
    modified_frames: int
    edited: bool

    @property
    def frame_count(self) -> int:
        return max(0, self.end - self.start + 1)


def make_clean_plate_id(source: str, start: int, end: int, branch: str) -> str:
    value = f"{source}:{int(start)}:{int(end)}:{branch}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def discover_clean_plates(
    clean_plates_dir: str | Path,
    branch: str,
    operations: Iterable[Mapping[str, object]],
) -> list[CleanPlateRecord]:
    root = Path(clean_plates_dir)
    operation_list = [
        operation
        for operation in operations
        if operation.get("branch", branch) == branch
    ]
    build_by_id = {}
    edited_ids = set()
    modified_by_id: dict[str, set[str]] = {}
    for operation in operation_list:
        payload = operation.get("payload") or {}
        if not isinstance(payload, Mapping):
            continue
        operation_type = str(operation.get("type") or "")
        if operation_type == "clean_plate.build":
            source = str(payload.get("source") or "Mídia não identificada")
            start = int(payload.get("start", 0))
            end = int(payload.get("end", start))
            plate_id = str(
                payload.get("plate_id")
                or make_clean_plate_id(source, start, end, branch)
            )
            build_by_id[plate_id] = operation
        elif operation_type == "clean_plate.edit":
            plate_id = str(payload.get("plate_id") or "")
            if plate_id:
                edited_ids.add(plate_id)
        elif operation_type in {"clean_plate.apply", "clean_plate.reapply"}:
            plate_id = str(payload.get("plate_id") or "")
            artifacts = operation.get("artifacts") or {}
            if plate_id and isinstance(artifacts, Mapping):
                modified_by_id.setdefault(plate_id, set()).update(
                    str(label) for label in artifacts
                )

    records = []
    if not root.is_dir():
        return records
    for directory in sorted(root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True):
        if not directory.is_dir():
            continue
        plate_path = directory / "plate.png"
        static_mask_path = directory / "static_background.png"
        if not plate_path.is_file() or not static_mask_path.is_file():
            continue
        operation = build_by_id.get(directory.name, {})
        payload = operation.get("payload") or {}
        source = str(payload.get("source") or "Mídia não identificada")
        start = int(payload.get("start", 0))
        end = int(payload.get("end", start))
        records.append(
            CleanPlateRecord(
                plate_id=directory.name,
                directory=directory,
                plate_path=plate_path,
                static_mask_path=static_mask_path,
                transparent_plate_path=(
                    directory / "plate_rgba.png"
                    if (directory / "plate_rgba.png").is_file()
                    else None
                ),
                application_region_path=(
                    directory / "application_region.png"
                    if (directory / "application_region.png").is_file()
                    else None
                ),
                layer_metadata_path=(
                    root.parent / "clean_plate_layers" / directory.name / "layer.json"
                    if (
                        root.parent
                        / "clean_plate_layers"
                        / directory.name
                        / "layer.json"
                    ).is_file()
                    else None
                ),
                source=source,
                start=start,
                end=end,
                diagnostics=dict(payload.get("diagnostics") or {}),
                created_at=str(operation.get("created_at") or ""),
                modified_frames=len(modified_by_id.get(directory.name, set())),
                edited=directory.name in edited_ids or (directory / "plate_original.png").is_file(),
            )
        )
    return records
