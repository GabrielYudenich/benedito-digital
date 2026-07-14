import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.media_import import (
    MediaImportPlanError,
    build_import_plan,
    build_import_selection,
    format_timecode,
    parse_timecode,
)
from core.storage import (
    InsufficientStorageError,
    estimate_lossless_frames_bytes,
    format_bytes,
    require_free_space,
)


def test_timecodes_accept_seconds_minutes_and_hours():
    assert parse_timecode("12.5") == 12.5
    assert parse_timecode("02:03") == 123
    assert parse_timecode("01:02:03,500") == 3723.5
    assert format_timecode(3723.5, milliseconds=True) == "01:02:03.500"


def test_invalid_timecodes_are_rejected():
    for value in ("", "00:61", "00:00:60", "-1", "texto"):
        with pytest.raises(MediaImportPlanError):
            parse_timecode(value)


def test_segment_minutagem_is_validated_before_analysis():
    selection = build_import_selection(
        "segment", start_value="00:12:30", end_value="00:18:45"
    )

    assert selection.is_segment
    assert selection.start_time == 750
    assert selection.end_time == 1125

    with pytest.raises(MediaImportPlanError, match="posterior"):
        build_import_selection(
            "segment", start_value="00:18:45", end_value="00:12:30"
        )


def test_builds_complete_and_exact_segment_plans(tmp_path):
    source = tmp_path / "Filme Original.mov"
    source.write_bytes(b"source" * 100)
    info = {"duration": 600, "fps": 24, "width": 1920, "height": 1080}

    complete = build_import_plan(source, "full", info)
    segment = build_import_plan(
        source, "segment", info, start_value="00:01:00", end_value="00:02:30"
    )

    assert complete.destination_name == source.name
    assert complete.estimated_bytes == source.stat().st_size
    assert segment.is_segment
    assert segment.start_time == 60
    assert segment.end_time == 150
    assert segment.duration == 90
    assert segment.destination_name == "Filme_Original_trecho_00-01-00_a_00-02-30.mkv"
    assert segment.estimated_bytes > source.stat().st_size


def test_segment_cannot_exceed_source_duration(tmp_path):
    source = tmp_path / "film.mov"
    source.write_bytes(b"source")

    with pytest.raises(MediaImportPlanError, match="ultrapassa"):
        build_import_plan(
            source,
            "segment",
            {"duration": 10, "fps": 24, "width": 720, "height": 576},
            start_value="5",
            end_value="11",
        )


def test_storage_preflight_blocks_impossible_operations(tmp_path):
    with pytest.raises(InsufficientStorageError, match="Espaço insuficiente"):
        require_free_space(tmp_path, 10**30)


def test_frame_storage_estimate_is_conservative():
    estimated = estimate_lossless_frames_bytes(10, 24, 1920, 1080)

    assert estimated > 1920 * 1080 * 3 * 240
    assert format_bytes(estimated).endswith("GiB")
