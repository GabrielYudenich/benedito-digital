"""Repeatable memory/checkpoint stress test for very long projects."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.chunks import ChunkedFrameRunner
from core.jobs import JobContext


def main():
    parser = argparse.ArgumentParser(description="Stress test do processamento em chunks")
    parser.add_argument("--frames", type=int, default=250_000)
    parser.add_argument("--chunk-size", type=int, default=1_000)
    parser.add_argument("--max-peak-mb", type=float, default=32.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.frames < 1:
        raise SystemExit("--frames deve ser positivo")
    with tempfile.TemporaryDirectory(prefix="benedito-stress-") as temporary:
        checkpoint = Path(temporary) / "checkpoint.json"
        context = JobContext(__import__("threading").Event(), lambda _value, _message: None)
        runner = ChunkedFrameRunner(args.chunk_size)
        tracemalloc.start()
        started = time.perf_counter()
        result = runner.run(range(args.frames), lambda _index, _item: None, context, checkpoint, "stress-v1")
        elapsed = time.perf_counter() - started
        _current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        report = {
            **result,
            "elapsed_seconds": round(elapsed, 3),
            "peak_memory_mb": round(peak / (1024 * 1024), 3),
            "checkpoint_bytes": checkpoint.stat().st_size,
            "frames_per_second": round(args.frames / max(elapsed, 0.0001), 1),
            "passed": peak <= args.max_peak_mb * 1024 * 1024,
        }
        payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        print(payload, end="")
        if not report["passed"]:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
