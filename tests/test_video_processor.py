import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
MODULE_DIR = os.path.join(ROOT, "src", "gui", "modules")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)
if MODULE_DIR not in sys.path:
    sys.path.insert(0, MODULE_DIR)

import video_processor
from video_processor import VideoProcessor


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
