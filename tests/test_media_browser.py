import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.media_browser import (
    list_frame_files,
    media_frame_directory_name,
    paginate_frame_files,
)


def test_media_sources_receive_distinct_stable_frame_directories():
    first = media_frame_directory_name("Rolo 1.mov")
    second = media_frame_directory_name("Rolo 1.mkv")

    assert first == media_frame_directory_name("Rolo 1.mov")
    assert first != second
    assert first.startswith("Rolo_1-")


def test_frame_tree_pages_are_natural_and_limited_to_one_hundred(tmp_path):
    for number in range(1, 206):
        (tmp_path / f"frame_{number}.png").write_bytes(b"frame")
    (tmp_path / "ignore.txt").write_text("not a frame", encoding="utf-8")

    files = list_frame_files(tmp_path)
    pages = paginate_frame_files(tmp_path, page_size=100)

    assert files[:3] == ["frame_1.png", "frame_2.png", "frame_3.png"]
    assert [len(page.files) for page in pages] == [100, 100, 5]
    assert pages[1].start_index == 100
    assert pages[-1].end_index == 204
