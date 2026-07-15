"""Durable JSON persistence with local recovery copies."""

from __future__ import annotations

import json
import os
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Type


JsonValidator = Callable[[Dict[str, Any]], None]


class JsonRecoveryError(Exception):
    """Raised when no trustworthy JSON copy can be loaded."""


@dataclass(frozen=True)
class JsonLoadResult:
    data: Dict[str, Any]
    source: str
    recovered: bool = False
    recovered_from: Optional[Path] = None
    quarantined: Optional[Path] = None


def backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def temporary_paths(path: Path) -> Tuple[Path, ...]:
    pattern = f".{path.name}.*.tmp"
    return tuple(
        sorted(
            path.parent.glob(pattern),
            key=lambda candidate: candidate.stat().st_mtime_ns,
            reverse=True,
        )
    )


def atomic_write_json(
    path: Path,
    data: Mapping[str, Any],
    *,
    keep_backup: bool = True,
) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    backup_temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.bak.tmp")
    try:
        _write_json_file(temporary, data)
        if keep_backup and path.is_file():
            shutil.copyfile(path, backup_temporary)
            _flush_file(backup_temporary)
            os.replace(backup_temporary, backup_path(path))
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
        backup_temporary.unlink(missing_ok=True)


def load_json_with_recovery(
    path: Path,
    *,
    validator: Optional[JsonValidator] = None,
    fatal_exceptions: Tuple[Type[BaseException], ...] = (),
) -> JsonLoadResult:
    path = Path(path)
    candidates = (("primary", path),) + tuple(
        ("temporary", candidate) for candidate in temporary_paths(path)
    ) + (("backup", backup_path(path)),)
    failures = []

    for source, candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            data = _read_json_file(candidate)
            if validator:
                validator(data)
        except fatal_exceptions:
            raise
        except (OSError, json.JSONDecodeError, UnicodeDecodeError, ValueError, TypeError) as error:
            failures.append(f"{candidate.name}: {error}")
            continue

        if source == "primary":
            _discard_temporaries(path)
            return JsonLoadResult(data=data, source=source)

        quarantined = _quarantine_primary(path)
        atomic_write_json(path, data, keep_backup=False)
        _discard_temporaries(path)
        return JsonLoadResult(
            data=data,
            source=source,
            recovered=True,
            recovered_from=candidate,
            quarantined=quarantined,
        )

    details = "; ".join(failures) if failures else "nenhuma cópia encontrada"
    raise JsonRecoveryError(f"Não foi possível recuperar {path.name}: {details}")


def _read_json_file(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as file_handle:
        data = json.load(file_handle)
    if not isinstance(data, dict):
        raise ValueError("o conteúdo JSON precisa ser um objeto")
    return data


def _write_json_file(path: Path, data: Mapping[str, Any]) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as file_handle:
        json.dump(data, file_handle, ensure_ascii=False, indent=2)
        file_handle.write("\n")
        file_handle.flush()
        os.fsync(file_handle.fileno())


def _flush_file(path: Path) -> None:
    with path.open("r+b") as file_handle:
        file_handle.flush()
        os.fsync(file_handle.fileno())


def _discard_temporaries(path: Path) -> None:
    for temporary in temporary_paths(path):
        temporary.unlink(missing_ok=True)


def _quarantine_primary(path: Path) -> Optional[Path]:
    if not path.exists():
        return None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination = path.with_name(f"{path.name}.corrupt-{timestamp}")
    os.replace(path, destination)
    return destination
