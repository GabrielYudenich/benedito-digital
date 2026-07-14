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


def test_segment_commands_support_mov_mp4_and_centered_audio():
    processor = make_processor()
    mov_command = processor._build_lossless_segment_command(
        "source.mov",
        "segment.mov",
        1,
        2,
        working_format="mov_prores",
        audio_mode="dual_mono_right",
    )
    mp4_command = processor._build_lossless_segment_command(
        "source.mov", "segment.mp4", 1, 2, working_format="mp4_hq"
    )

    assert mov_command[mov_command.index("-c:v") + 1] == "prores_ks"
    assert mov_command[mov_command.index("-profile:v") + 1] == "3"
    assert mov_command[mov_command.index("-c:a") + 1] == "pcm_s24le"
    assert mov_command[mov_command.index("-af") + 1] == "pan=stereo|c0=c1|c1=c1"
    assert mov_command[-1] == "segment.mov"
    assert mp4_command[mp4_command.index("-c:a") + 1] == "aac"
    assert mp4_command[mp4_command.index("-b:a") + 1] == "320k"
    assert mp4_command[-1] == "segment.mp4"


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


def test_audio_analysis_detects_and_repairs_right_only_audio(tmp_path):
    ffmpeg = executable_path("ffmpeg")
    if not Path(ffmpeg).is_file():
        return
    source = tmp_path / "right-only.mov"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10:duration=2",
            "-f", "lavfi", "-i",
            "aevalsrc=0|sin(2*PI*440*t):s=48000:d=2",
            "-c:v", "prores_ks", "-profile:v", "3",
            "-c:a", "pcm_s16le", "-shortest", "-y", str(source),
        ],
        check=True,
    )
    processor = make_processor()

    before = processor.analyze_audio_balance(str(source), 0, 2)
    output = tmp_path / "centered.mov"
    assert processor.create_lossless_segment(
        str(source),
        str(output),
        0,
        2,
        working_format="mov_prores",
        audio_mode=before["suggested_mode"],
    )
    after = processor.analyze_audio_balance(str(output), 0, 2)

    assert before["suggested_mode"] == "dual_mono_right"
    assert after["suggested_mode"] == "preserve"
    assert len(after["rms_db"]) == 2
    assert abs(after["rms_db"][0] - after["rms_db"][1]) < 0.1


def test_high_quality_mp4_renders_h264_and_aac(tmp_path):
    ffmpeg = executable_path("ffmpeg")
    ffprobe = executable_path("ffprobe")
    if not (Path(ffmpeg).is_file() and Path(ffprobe).is_file()):
        return
    source = tmp_path / "source.mkv"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=10:duration=1",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000:duration=1",
            "-c:v", "ffv1", "-c:a", "pcm_s16le", "-shortest", "-y", str(source),
        ],
        check=True,
    )
    output = tmp_path / "segment.mp4"

    assert make_processor("libopenh264").create_lossless_segment(
        str(source), str(output), 0, 1, working_format="mp4_hq"
    )

    probe = subprocess.run(
        [
            ffprobe, "-v", "error", "-show_entries", "stream=codec_name,codec_type",
            "-show_entries", "format=format_name", "-of", "json", str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    codecs = {stream["codec_type"]: stream["codec_name"] for stream in metadata["streams"]}
    assert codecs == {"video": "h264", "audio": "aac"}
    assert "mp4" in metadata["format"]["format_name"]


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
