import os
import sys

import pytest


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.chunks import CheckpointMismatch, ChunkedFrameRunner
from core.jobs import JobManager, JobState


def run_job(runner, items, process_item, checkpoint, fingerprint="operation-a"):
    manager = JobManager()
    job = manager.submit(
        "Chunks",
        lambda context: runner.run(
            items,
            process_item,
            context,
            checkpoint,
            fingerprint,
        ),
    )
    return manager.wait(job.id, timeout=2)


def test_completed_chunks_are_skipped_on_resume(tmp_path):
    runner = ChunkedFrameRunner(chunk_size=2)
    checkpoint = tmp_path / "checkpoint.json"
    first_pass = []

    def fail_in_second_chunk(index, item):
        first_pass.append(item)
        if index == 3:
            raise RuntimeError("interrupted")

    failed = run_job(runner, list(range(6)), fail_in_second_chunk, checkpoint)
    assert failed.state == JobState.FAILED
    assert first_pass == [0, 1, 2, 3]

    resumed = []
    completed = run_job(
        runner, list(range(6)), lambda _index, item: resumed.append(item), checkpoint
    )

    assert completed.state == JobState.COMPLETED
    assert resumed == [2, 3, 4, 5]
    assert completed.result == {"processed": 4, "skipped": 2, "total": 6}


def test_mismatched_checkpoint_fails_safely(tmp_path):
    runner = ChunkedFrameRunner(chunk_size=2)
    checkpoint = tmp_path / "checkpoint.json"
    first = run_job(runner, [1, 2], lambda _index, _item: None, checkpoint)
    assert first.state == JobState.COMPLETED

    second = run_job(
        runner,
        [1, 2],
        lambda _index, _item: None,
        checkpoint,
        fingerprint="different-operation",
    )

    assert second.state == JobState.FAILED
    assert "Checkpoint does not match" in second.error


def test_invalid_chunk_size_is_rejected():
    with pytest.raises(ValueError):
        ChunkedFrameRunner(chunk_size=0)


def test_corrupt_checkpoint_recovers_last_confirmed_chunk(tmp_path):
    runner = ChunkedFrameRunner(chunk_size=2)
    checkpoint = tmp_path / "checkpoint.json"
    first = run_job(runner, list(range(4)), lambda _index, _item: None, checkpoint)
    assert first.state == JobState.COMPLETED
    checkpoint.write_text("{queda-de-energia", encoding="utf-8")
    resumed_items = []

    resumed = run_job(
        runner,
        list(range(4)),
        lambda _index, item: resumed_items.append(item),
        checkpoint,
    )

    assert resumed.state == JobState.COMPLETED
    assert resumed_items == [2, 3]
    assert resumed.result == {"processed": 2, "skipped": 2, "total": 4}
    assert runner.last_recovery is not None
    assert runner.last_recovery.source == "backup"
