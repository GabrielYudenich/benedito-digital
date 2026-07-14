from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.clean_plate_library import discover_clean_plates, make_clean_plate_id


def test_discovers_existing_plate_and_application_history(tmp_path):
    branch = "principal"
    source = "filme.mov"
    plate_id = make_clean_plate_id(source, 60, 817, branch)
    plate_dir = tmp_path / plate_id
    plate_dir.mkdir()
    (plate_dir / "plate.png").write_bytes(b"plate")
    (plate_dir / "static_background.png").write_bytes(b"mask")
    operations = [
        {
            "branch": branch,
            "type": "clean_plate.build",
            "created_at": "2026-07-14T10:00:00Z",
            "payload": {
                "source": source,
                "start": 60,
                "end": 817,
                "diagnostics": {"static_ratio": 0.71},
            },
        },
        {
            "branch": branch,
            "type": "clean_plate.apply",
            "payload": {"plate_id": plate_id},
            "artifacts": {"frame_000000060": {}, "frame_000000061": {}},
        },
        {
            "branch": branch,
            "type": "clean_plate.edit",
            "payload": {"plate_id": plate_id},
        },
    ]

    records = discover_clean_plates(tmp_path, branch, operations)

    assert len(records) == 1
    assert records[0].start == 60
    assert records[0].end == 817
    assert records[0].frame_count == 758
    assert records[0].modified_frames == 2
    assert records[0].edited is True


def test_ignores_incomplete_plate_directories(tmp_path):
    incomplete = tmp_path / "incomplete"
    incomplete.mkdir()
    (incomplete / "plate.png").write_bytes(b"plate")

    assert discover_clean_plates(tmp_path, "principal", []) == []
