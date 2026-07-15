import json
import shutil
import subprocess
import sys
from pathlib import Path

import cv2
import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
for path in (
    SRC_DIR,
    SRC_DIR / "lib" / "modules" / "video" / "renderer",
):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.paths import executable_path
from gui.modules.project_manager_gui import ProjectManagerGUI
from gui.modules.video_processor import VideoProcessor
from video_renderer import VideoRenderer


def available_executable(name):
    value = executable_path(name)
    return value if Path(value).is_file() or shutil.which(value) else None


def test_complete_local_restoration_journey(tmp_path):
    ffmpeg = available_executable("ffmpeg")
    ffprobe = available_executable("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("FFmpeg integration tools are unavailable")
    encoders = subprocess.run(
        [ffmpeg, "-hide_banner", "-encoders"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    if "libx264" not in encoders and "libopenh264" not in encoders:
        pytest.skip("No supported software H.264 encoder is available")

    source_encoder = "libx264" if "libx264" in encoders else "libopenh264"
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x120:rate=6",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:sample_rate=48000",
            "-vf",
            "setsar=4/3",
            "-t",
            "1",
            "-c:v",
            source_encoder,
            "-b:v",
            "2M",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-colorspace",
            "bt709",
            "-bsf:v",
            "h264_metadata=colour_primaries=1:transfer_characteristics=1:matrix_coefficients=1",
            "-c:a",
            "aac",
            "-y",
            str(source),
        ],
        check=True,
    )

    manager = ProjectManagerGUI()
    manager.project_path = str(tmp_path / "projects")
    assert manager.create_project_advanced("Rolo 1", author="Equipe")
    assert manager.load_project("Rolo 1")
    import_progress = []
    assert manager.add_video_to_project(
        str(source), progress_callback=import_progress.append
    )
    assert import_progress[-1] == 100.0
    original = Path(manager.get_originals_dir()) / source.name
    assert original.is_file()
    assert manager.workspace.verify_original(
        next(iter(manager.workspace.data["originals"]))
    )

    processor = VideoProcessor(use_gpu=False)
    proxy = manager.workspace.proxies_dir / "source_proxy.mp4"
    proxy_progress = []
    assert processor.create_proxy(
        str(original), str(proxy), max_width=320, progress_callback=proxy_progress.append
    )
    manager.workspace.register_proxy(source.name, proxy, 320)
    assert proxy_progress[-1] == 100.0

    frames_dir = Path(manager.get_frames_dir())
    extraction_progress = []
    assert processor.extract_frames(
        str(original),
        str(frames_dir),
        progress_callback=extraction_progress.append,
    )
    frames = sorted(frames_dir.glob("*.png"))
    assert len(frames) == 6
    assert extraction_progress[-1] == 100.0

    manager.workspace.create_branch("limpeza")
    manager.workspace.checkout("limpeza")
    restored_dir = manager.workspace.branch_worktree() / "restored"
    restored_dir.mkdir(parents=True, exist_ok=True)
    restored = restored_dir / frames[0].name
    image = cv2.imread(str(frames[0]), cv2.IMREAD_COLOR)
    assert image is not None
    image[20:40, 20:40] = 0
    assert cv2.imwrite(str(restored), image)
    manager.workspace.commit_operation(
        "filter.local",
        payload={"selection": [20, 20, 40, 40]},
        frame_number=0,
        artifacts={"result": restored},
    )
    package = tmp_path / "limpeza.bdpack"
    manifest = manager.workspace.export_branch(package)
    assert manifest["branch"] == "limpeza"
    manager.workspace.checkout("principal")
    imported_branch = manager.workspace.import_branch(package)
    assert imported_branch.startswith("limpeza")

    render_frames = tmp_path / "render-frames"
    shutil.copytree(frames_dir, render_frames)
    shutil.copy2(restored, render_frames / restored.name)
    output = Path(manager.get_exports_dir()) / "renders" / "final.mp4"
    renderer = VideoRenderer(use_gpu=False)
    render_progress = []
    assert renderer.render_frames_to_video(
        str(render_frames),
        str(output),
        fps=6,
        profile="delivery",
        audio_source=str(original),
        progress_callback=render_progress.append,
    )
    assert render_progress[-1] == 100.0

    probe = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,sample_aspect_ratio,color_primaries",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    streams = metadata["streams"]
    video = next(stream for stream in streams if stream["codec_type"] == "video")
    audio = next(stream for stream in streams if stream["codec_type"] == "audio")
    assert video["codec_name"] == "h264"
    assert video["sample_aspect_ratio"] == "4:3"
    assert video["color_primaries"] == "bt709"
    assert audio["codec_name"] == "aac"
    assert float(metadata["format"]["duration"]) == pytest.approx(1.0, abs=0.05)
