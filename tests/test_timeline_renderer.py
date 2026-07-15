import sys
import json
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.edit_timeline import EditTimeline
from lib.modules.video.renderer.timeline_renderer import TimelineRenderer
from core.paths import executable_path


def test_timeline_command_contains_tracks_transitions_and_safe_arguments(tmp_path):
    video = tmp_path / "video source.mp4"
    audio = tmp_path / "audio source.wav"
    video.write_bytes(b"video")
    audio.write_bytes(b"audio")
    timeline = EditTimeline(fps=25, width=720, height=576)
    first = timeline.add_clip("video-1", video, 0, 2, 0)
    second = timeline.add_clip("video-1", video, 2, 4, 1.5)
    timeline.add_clip("audio-1", audio, 0, 3.5, 0)
    timeline.add_transition(first.id, second.id, duration=0.5)
    timeline.set_keyframe(first.id, "opacity", 0, 0.8)
    timeline.set_keyframe(first.id, "x", 0, 0)
    timeline.set_keyframe(first.id, "x", 1, 20)

    command = TimelineRenderer().build_command(timeline, tmp_path / "result.mp4")
    filters = command[command.index("-filter_complex") + 1]

    assert isinstance(command, list)
    assert "video source.mp4" in " ".join(command)
    assert "overlay=" in filters
    assert "fade=t=out" in filters
    assert "amix=inputs=1" in filters
    assert "if(lte(" in filters
    assert "[vout]" in command


def test_timeline_renders_real_video_and_audio(tmp_path):
    ffmpeg = executable_path("ffmpeg")
    ffprobe = executable_path("ffprobe")
    if not (Path(ffmpeg).is_file() and Path(ffprobe).is_file()):
        return
    source = tmp_path / "source.mp4"
    subprocess.run(
        [
            ffmpeg, "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "testsrc2=size=160x120:rate=6",
            "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000",
            "-t", "2", "-c:v", "libopenh264", "-b:v", "1M", "-c:a", "aac",
            "-y", str(source),
        ],
        check=True,
    )
    timeline = EditTimeline(fps=6, width=160, height=120)
    first = timeline.add_clip("video-1", source, 0, 1.2, 0)
    second = timeline.add_clip("video-1", source, 0.8, 2, 1.0)
    timeline.set_keyframe(first.id, "x", 0, 0)
    timeline.set_keyframe(first.id, "x", 1, 12, "smooth")
    timeline.add_transition(first.id, second.id, duration=0.2)
    timeline.add_clip("audio-1", source, 0, 2, 0)
    output = tmp_path / "timeline.mp4"
    progress = []

    TimelineRenderer().render(timeline, output, progress_callback=progress.append)

    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type", "-show_entries", "format=duration", "-of", "json", str(output)],
        capture_output=True,
        text=True,
        check=True,
    )
    metadata = json.loads(probe.stdout)
    assert {stream["codec_type"] for stream in metadata["streams"]} == {"video", "audio"}
    assert abs(float(metadata["format"]["duration"]) - timeline.duration) < 0.15
    assert progress[-1] == 100.0
