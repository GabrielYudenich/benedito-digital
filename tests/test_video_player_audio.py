import sys
import threading
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.modules import video_player
from gui.modules.video_player import VideoPlayer
from gui.screens.editor_screen import EditorScreen


class FakeProcess:
    def __init__(self, command):
        self.command = command
        self.pid = 1234
        self.terminated = False

    def poll(self):
        return None if not self.terminated else 0

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        return 0


def test_reference_audio_uses_bundled_ffplay_and_current_position(monkeypatch):
    processes = []

    def fake_popen(command, **_options):
        process = FakeProcess(command)
        processes.append(process)
        return process

    monkeypatch.setattr(video_player, "executable_path", lambda name: f"bundled/{name}")
    monkeypatch.setattr(video_player.subprocess, "Popen", fake_popen)

    player = VideoPlayer(use_gpu=False)
    player.video_path = str(ROOT / "media.mov")
    player.fps = 25.0
    player.current_frame = 250
    player.audio_enabled = True

    player._start_audio_playback()

    assert processes[0].command[0] == "bundled/ffplay"
    assert processes[0].command[processes[0].command.index("-ss") + 1] == "10.000000"
    assert processes[0].command[-1] == "-vn"

    player._stop_audio_playback()
    assert processes[0].terminated


def test_playback_worker_callbacks_only_update_thread_safe_pending_state():
    editor = object.__new__(EditorScreen)
    editor._playback_ui_lock = threading.Lock()
    editor._pending_playback_frame = None
    editor._pending_playback_progress = None
    editor._pending_playback_finished = False
    frame = object()

    editor._queue_video_frame(frame)
    editor._queue_playback_progress(42.5)
    editor._queue_playback_finished()

    assert editor._pending_playback_frame is frame
    assert editor._pending_playback_progress == 42.5
    assert editor._pending_playback_finished is True
