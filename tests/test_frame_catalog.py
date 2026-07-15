import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.frame_catalog import catalog_page, filter_frame_indices


def test_catalog_searches_exact_frame_number_and_status():
    frames = [f"frame_{index + 1:06d}.png" for index in range(20)]
    statuses = {4: {"status": "dust"}, 9: {"status": "scratch"}}

    assert filter_frame_indices(frames, statuses, query="5") == [4]
    assert filter_frame_indices(frames, statuses, status_filter="scratch") == [9]
    assert filter_frame_indices(
        frames, statuses, query="10", status_filter="scratch"
    ) == [9]
    assert filter_frame_indices(
        frames,
        statuses,
        status_filter="excluded",
        excluded_indices={0, 1, 2},
    ) == [0, 1, 2]


def test_catalog_pages_filtered_results_without_loading_every_widget():
    page = catalog_page(list(range(125)), page=2, page_size=50)

    assert page.number == 2
    assert page.total_pages == 3
    assert page.indices == tuple(range(100, 125))
    assert page.total_matches == 125
