import os
import sys
import json
import subprocess
from pathlib import Path


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
MODULE_DIR = os.path.join(ROOT, "src", "gui", "modules")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

import video_processor
from video_processor import VideoProcessor
from core.paths import executable_path


def make_processor(encoder="libx264"):
    processor = VideoProcessor.__new__(VideoProcessor)
    processor.use_gpu = encoder != "libx264"
    processor.gpu_available = encoder != "libx264"
    processor.gpu_encoders = [encoder]
    processor.preferred_encoder = encoder
    return processor


def test_cut_command_is_argument_list_without_shell_quoting():
    processor = make_processor()
    command = processor._build_cut_command(
        r"C:\Media Files\source.mov", r"C:\Output Files\cut.mp4", 10.5, 20.5
    )

    assert isinstance(command, list)
    assert r"C:\Media Files\source.mov" in command
    assert r"C:\Output Files\cut.mp4" in command
    assert os.path.basename(command[0]).lower() in {"ffmpeg", "ffmpeg.exe"}


def test_lossless_segment_uses_exact_range_and_intraframe_codecs():
    processor = make_processor()
    command = processor._build_lossless_segment_command(
        r"C:\Acervo\filme.mov",
        r"C:\Projeto\trecho.mkv",
        60.25,
        90.75,
    )

    assert command.index("-ss") > command.index("-i")
    assert command[command.index("-ss") + 1] == "60.25"
    assert command[command.index("-t") + 1] == "30.5"
    assert command[command.index("-c:v") + 1] == "ffv1"
    assert command[command.index("-g") + 1] == "1"
    assert command[command.index("-c:a") + 1] == "pcm_s24le"
    assert command[-1] == r"C:\Projeto\trecho.mkv"


def test_lossless_segment_renders_real_video_and_audio(tmp_path):
    ffmpeg = executable_path("ffmpeg")
    ffprobe = executable_path("ffprobe")
    if not (Path(ffmpeg).is_file() and Path(ffprobe).is_file()):
        return
    source = tmp_path / "source.mkv"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "2", "-c:v", "ffv1", "-c:a", "pcm_s16le", "-y", str(source),
        ],
        check=True,
    )
    output = tmp_path / "segment.mkv"
    progress = []

    assert make_processor().create_lossless_segment(
        str(source), str(output), 0.5, 1.5, progress_callback=progress.append
    )

    probe = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "stream=codec_name,codec_type",
            "-show_entries", "format=duration", "-of", "json", str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    codecs = {stream["codec_type"]: stream["codec_name"] for stream in metadata["streams"]}
    assert codecs == {"video": "ffv1", "audio": "pcm_s24le"}
    assert 0.9 <= float(metadata["format"]["duration"]) <= 1.1
    assert progress[-1] == 100.0


def test_extraction_defaults_to_lossless_png():
    processor = make_processor()
    command = processor._build_extraction_command(
        "source.mov", "frames", 24.0, 2, None, lossless=True
    )

    assert "fps=24.0" in command
    assert command[-1].endswith("frame_%06d.png")
    assert "-q:v" not in command


def test_structured_progress_time_parsing():
    assert VideoProcessor._parse_progress_time("out_time_us", "2500000") == 2.5
    assert VideoProcessor._parse_progress_time("out_time_ms", "2500000") == 2.5
    assert VideoProcessor._parse_progress_time("out_time", "01:02:03.500") == 3723.5
    assert VideoProcessor._parse_progress_time("frame", "120") is None


def test_proxy_rejects_invalid_width_before_running_ffmpeg():
    processor = make_processor()

    try:
        processor.create_proxy("source.mov", "proxy.mp4", max_width=100)
    except ValueError as error:
        assert "between 320 and 3840" in str(error)
    else:
        raise AssertionError("Expected invalid proxy width to fail")


def test_vhs_filter_chain_is_explicit_and_configurable():
    filters = VideoProcessor._build_vhs_filters(True, "medium", True)

    assert filters[0].startswith("bwdif=")
    assert any(value.startswith("hqdn3d=") for value in filters)
    assert any(value.startswith("deshake=") for value in filters)
    assert filters[-1].startswith("eq=")


def test_gpu_encoder_requires_successful_runtime_probe(monkeypatch):
    processor = VideoProcessor.__new__(VideoProcessor)
    processor.use_gpu = True
    processor.gpu_encoders = ["h264_nvenc", "libopenh264"]
    monkeypatch.setattr(
        video_processor, "_hardware_encoder_is_usable", lambda *_args: False
    )

    assert processor._select_encoder() == "libopenh264"


def test_usable_gpu_encoder_is_preferred(monkeypatch):
    processor = VideoProcessor.__new__(VideoProcessor)
    processor.use_gpu = True
    processor.gpu_encoders = ["h264_qsv", "libopenh264"]
    monkeypatch.setattr(
        video_processor,
        "_hardware_encoder_is_usable",
        lambda _path, encoder: encoder == "h264_qsv",
    )

    assert processor._select_encoder() == "h264_qsv"
