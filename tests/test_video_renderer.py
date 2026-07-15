import os
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
MODULE_DIR = ROOT / "src" / "lib" / "modules" / "video" / "renderer"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(MODULE_DIR) not in sys.path:
    sys.path.insert(0, str(MODULE_DIR))

from video_renderer import EXPORT_PROFILES, VideoRenderer


def test_manifest_supports_six_digit_and_arbitrary_frame_names(tmp_path):
    frames = [tmp_path / "frame_000001.png", tmp_path / "restored final 000002.png"]
    for frame in frames:
        frame.write_bytes(b"image")
    manifest = tmp_path / "frames.ffconcat"

    VideoRenderer._write_frame_manifest(manifest, frames, 25.0)

    content = manifest.read_text(encoding="utf-8")
    assert content.startswith("ffconcat version 1.0")
    assert "frame_000001.png" in content
    assert "restored final 000002.png" in content
    assert content.count("duration 0.040000000000") == 2
    assert content.count("restored final 000002.png") == 2


def test_delivery_command_maps_optional_audio_and_color_metadata(tmp_path):
    command = VideoRenderer._build_render_command(
        manifest_path=tmp_path / "frames.ffconcat",
        output_path=tmp_path / "result.mp4",
        duration=2.0,
        fps=24.0,
        profile="delivery",
        audio_source=tmp_path / "source with audio.mov",
        audio_start=1.5,
        source_metadata={
            "sample_aspect_ratio": "4:3",
            "color_range": "tv",
            "color_space": "bt709",
            "color_transfer": "bt709",
            "color_primaries": "bt709",
        },
    )

    assert isinstance(command, list)
    assert Path(command[0]).name.lower() in {"ffmpeg", "ffmpeg.exe"}
    assert "1:a?" in command
    assert "source with audio.mov" in " ".join(command)
    assert "setsar=4/3" in command
    assert "-color_primaries" in command
    assert any(encoder in command for encoder in ("libx264", "libopenh264"))
    assert "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1" in command
    assert command[command.index("-r") + 1] == "24"
    assert command[command.index("-fps_mode") + 1] == "cfr"
    assert "shell" not in command


def test_archive_profile_is_lossless_and_does_not_require_audio(tmp_path):
    command = VideoRenderer._build_render_command(
        manifest_path=tmp_path / "frames.ffconcat",
        output_path=tmp_path / "archive.mkv",
        duration=1.0,
        profile="archive",
    )

    assert EXPORT_PROFILES["archive"]["extension"] == ".mkv"
    assert "ffv1" in command
    assert "1:a?" not in command
    assert "rgb24" in command


def test_progress_parser_matches_ffmpeg_machine_output():
    assert VideoRenderer._parse_progress_time("out_time_us", "1500000") == 1.5
    assert VideoRenderer._parse_progress_time("out_time", "00:00:02.250") == 2.25
    assert VideoRenderer._parse_progress_time("frame", "10") is None


def test_stabilization_stops_before_writing_when_cancelled(tmp_path):
    frames_dir = tmp_path / "frames"
    output_dir = tmp_path / "output"
    frames_dir.mkdir()
    image = np.zeros((32, 48, 3), dtype=np.uint8)
    assert cv2.imwrite(str(frames_dir / "frame_000001.png"), image)

    renderer = VideoRenderer(use_gpu=False)
    try:
        success = renderer.stabilize_frames_ecc(
            str(frames_dir),
            str(output_dir),
            cancel_callback=lambda: True,
        )
    finally:
        renderer.cleanup_temp_directory(log_messages=False)

    assert success is False
    assert not list(output_dir.glob("*.png"))
