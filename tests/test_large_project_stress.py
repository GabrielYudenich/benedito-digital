import json
import sys
import threading
import tracemalloc
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.chunks import ChunkedFrameRunner
from core.jobs import JobContext


def test_hundred_thousand_frame_checkpoint_stays_constant_size(tmp_path):
    checkpoint = tmp_path / "checkpoint.json"
    context = JobContext(threading.Event(), lambda _value, _message: None)
    tracemalloc.start()
    result = ChunkedFrameRunner(2000).run(
        range(100_000),
        lambda _index, _item: None,
        context,
        checkpoint,
        "large-project",
    )
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    data = json.loads(checkpoint.read_text(encoding="utf-8"))
    assert result["processed"] == 100_000
    assert data["completed_through"] == 100_000
    assert checkpoint.stat().st_size < 512
    assert peak < 8 * 1024 * 1024
