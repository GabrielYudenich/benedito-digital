import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.frame_cuts import FrameCutStore, UsefulFrameRange


def test_frame_cut_store_preserves_original_and_limits_useful_range(tmp_path):
    store = FrameCutStore(tmp_path)

    assert store.get("rolo.mov", 100) == UsefulFrameRange(0, 99)
    assert store.set("rolo.mov", 60, 99, 100) == UsefulFrameRange(60, 99)
    assert store.get("rolo.mov", 100).contains(59) is False
    assert store.get("rolo.mov", 100).contains(60) is True

    store.reset("rolo.mov")

    assert store.get("rolo.mov", 100) == UsefulFrameRange(0, 99)
