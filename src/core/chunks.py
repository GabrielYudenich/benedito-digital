"""Resumable chunk execution for long frame sequences."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from .jobs import JobContext
from lib.modules.project.recovery import (
    JsonRecoveryError,
    atomic_write_json,
    load_json_with_recovery,
)


PathLike = Union[str, os.PathLike]


class CheckpointMismatch(Exception):
    """Raised when a checkpoint belongs to another operation configuration."""


class ChunkedFrameRunner:
    """Processes bounded frame ranges and checkpoints completed chunks."""

    SCHEMA_VERSION = 2

    def __init__(self, chunk_size: int = 24):
        if chunk_size < 1:
            raise ValueError("Chunk size must be positive")
        self.chunk_size = chunk_size
        self.last_recovery = None

    def run(
        self,
        items: Sequence[Any],
        process_item: Callable[[int, Any], None],
        context: JobContext,
        checkpoint_path: PathLike,
        fingerprint: str,
        message: str = "Processando frames",
        on_chunk_complete: Optional[Callable[[int, int], None]] = None,
    ) -> Dict[str, int]:
        """Process items in chunks, resuming only matching checkpoints."""
        checkpoint_file = Path(checkpoint_path)
        checkpoint = self._load_checkpoint(checkpoint_file, fingerprint, len(items))
        completed_through = int(checkpoint["completed_through"])
        processed_items = completed_through
        total_items = len(items)

        if total_items == 0:
            context.report(100.0, message)
            return {"processed": 0, "skipped": 0, "total": 0}

        skipped_items = processed_items
        for start in range(0, total_items, self.chunk_size):
            end = min(total_items, start + self.chunk_size)
            chunk_key = (start, end)
            if end <= completed_through:
                context.report(end * 100.0 / total_items, message)
                continue

            context.check_cancelled()
            for index in range(start, end):
                context.check_cancelled()
                process_item(index, items[index])
                processed_items += 1
                context.report(
                    (index + 1) * 100.0 / total_items,
                    f"{message} — {index + 1}/{total_items}",
                )

            if on_chunk_complete:
                on_chunk_complete(start, end)
            completed_through = end
            checkpoint["completed_through"] = completed_through
            self._atomic_write_json(checkpoint_file, checkpoint)

        return {
            "processed": processed_items - skipped_items,
            "skipped": skipped_items,
            "total": total_items,
        }

    def _load_checkpoint(
        self, checkpoint_path: Path, fingerprint: str, item_count: int
    ) -> Dict[str, Any]:
        if not checkpoint_path.exists():
            return {
                "schema_version": self.SCHEMA_VERSION,
                "fingerprint": fingerprint,
                "item_count": item_count,
                "chunk_size": self.chunk_size,
                "completed_through": 0,
            }

        try:
            loaded = load_json_with_recovery(checkpoint_path)
        except JsonRecoveryError as error:
            raise CheckpointMismatch(
                "Checkpoint is damaged and no valid recovery copy exists"
            ) from error
        checkpoint = loaded.data
        self.last_recovery = loaded if loaded.recovered else None
        expected = (
            checkpoint.get("schema_version") == self.SCHEMA_VERSION
            and checkpoint.get("fingerprint") == fingerprint
            and checkpoint.get("item_count") == item_count
            and checkpoint.get("chunk_size") == self.chunk_size
            and isinstance(checkpoint.get("completed_through"), int)
            and 0 <= checkpoint.get("completed_through") <= item_count
        )
        if not expected:
            raise CheckpointMismatch("Checkpoint does not match this operation")
        return checkpoint

    @staticmethod
    def _atomic_write_json(path: Path, data: Dict[str, Any]) -> None:
        atomic_write_json(path, data)
