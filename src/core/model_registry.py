"""Native model and weight registry with explicit attribution metadata."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Union


PathLike = Union[str, os.PathLike]


@dataclass(frozen=True)
class WeightRecord:
    id: str
    name: str
    family: str
    task: str
    path: str
    size: int
    scale: Optional[int]
    license: str
    source: str
    attribution: str
    sha256: Optional[str] = None


class ModelRegistry:
    """Discovers weights without importing entire external repositories."""

    EXTENSIONS = {".pth", ".pt", ".ckpt", ".onnx", ".safetensors", ".mat"}

    def __init__(self, registry_path: PathLike, weight_roots: Iterable[PathLike]):
        self.registry_path = Path(registry_path)
        with self.registry_path.open("r", encoding="utf-8") as file_handle:
            data = json.load(file_handle)
        if data.get("schema_version") != 1 or not isinstance(data.get("families"), dict):
            raise ValueError("Unsupported model registry")
        self.families = data["families"]
        self.weight_roots = [Path(root).resolve() for root in weight_roots]

    def discover(self) -> List[WeightRecord]:
        records = []
        seen = set()
        for root in self.weight_roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in self.EXTENSIONS:
                    continue
                resolved = str(path.resolve())
                if resolved in seen:
                    continue
                seen.add(resolved)
                family, task = self._infer_family_task(path.name)
                family_data = self.families[family]
                records.append(
                    WeightRecord(
                        id=hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16],
                        name=path.name,
                        family=family,
                        task=task,
                        path=resolved,
                        size=path.stat().st_size,
                        scale=self._infer_scale(path.name),
                        license=family_data["license"],
                        source=family_data["source"],
                        attribution=family_data["attribution"],
                    )
                )
        return sorted(records, key=lambda record: (record.family, record.task, record.name.lower()))

    def import_weight(
        self,
        source_path: PathLike,
        destination_root: PathLike,
        family: str,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> WeightRecord:
        if family not in self.families:
            raise ValueError(f"Unknown model family: {family}")
        source = Path(source_path)
        if not source.is_file() or source.suffix.lower() not in self.EXTENSIONS:
            raise ValueError("Unsupported or missing weight file")
        destination_dir = Path(destination_root) / family
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / source.name
        if destination.exists():
            raise FileExistsError(f"Weight already exists: {destination.name}")
        temporary = destination.with_name(f".{destination.name}.{uuid.uuid4().hex}.tmp")
        total = source.stat().st_size
        processed = 0
        digest = hashlib.sha256()
        try:
            with source.open("rb") as input_file, temporary.open("xb") as output_file:
                while True:
                    if cancel_callback and cancel_callback():
                        raise InterruptedError("Weight import cancelled")
                    chunk = input_file.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
                    output_file.write(chunk)
                    processed += len(chunk)
                    if progress_callback:
                        progress_callback(100.0 if total == 0 else processed * 100.0 / total)
            os.replace(temporary, destination)
        finally:
            if temporary.exists():
                temporary.unlink()
        family_data = self.families[family]
        inferred_family, task = self._infer_family_task(destination.name, preferred=family)
        return WeightRecord(
            id=hashlib.sha1(str(destination.resolve()).encode("utf-8")).hexdigest()[:16],
            name=destination.name,
            family=inferred_family,
            task=task,
            path=str(destination.resolve()),
            size=destination.stat().st_size,
            scale=self._infer_scale(destination.name),
            license=family_data["license"],
            source=family_data["source"],
            attribution=family_data["attribution"],
            sha256=digest.hexdigest(),
        )

    @staticmethod
    def verify_weight(path: PathLike, expected_sha256: str) -> bool:
        digest = hashlib.sha256()
        with Path(path).open("rb") as file_handle:
            while True:
                chunk = file_handle.read(8 * 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest() == expected_sha256

    def _infer_family_task(self, filename: str, preferred: Optional[str] = None):
        lower = filename.lower()
        if preferred:
            family = preferred
        elif "swinir" in lower:
            family = "swinir"
        elif "restormer" in lower:
            family = "restormer"
        elif "unet" in lower or "dust" in lower:
            family = "unet_dust"
        elif any(value in lower for value in ("bsrgan", "esrgan", "rrdb", "realsr", "fssr")):
            family = "bsrgan"
        else:
            family = "dncnn_kair"
        task = "super_resolution" if self._infer_scale(filename) else "denoise"
        if family == "unet_dust":
            task = "dust_mask"
        elif family == "restormer" and "deblur" in lower:
            task = "deblur"
        return family, task

    @staticmethod
    def _infer_scale(filename: str) -> Optional[int]:
        match = re.search(r"(?:x|scale)([2348])|([2348])x", filename.lower())
        if not match:
            return None
        return int(match.group(1) or match.group(2))
