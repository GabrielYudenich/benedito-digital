import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.jobs import JobSnapshot, JobState
from gui.screens.editor_screen import EditorScreen


class FakeVariable:
    def __init__(self, value=None):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeWidget:
    def __init__(self):
        self.values = {}

    def config(self, **values):
        self.values.update(values)


class FakeProgress(dict):
    pass


class FakeDialog:
    def __init__(self):
        self.snapshot = None

    def update(self, snapshot):
        self.snapshot = snapshot

    def exists(self):
        return True


def test_cancelled_job_clears_status_bar_processing_indicator():
    screen = object.__new__(EditorScreen)
    screen._active_job_id = "job-1"
    screen._active_job_callbacks = {"job-1": (None, None, None)}
    screen.progress_dialog = FakeDialog()
    screen.progress_var_main = FakeVariable(22)
    screen.restore_progress_var = FakeVariable(22)
    screen.status_var = FakeVariable("")
    screen.cancel_job_btn = FakeWidget()
    screen.show_job_btn = FakeWidget()
    screen.status_progress = FakeProgress(value=22)
    screen.status_percent_var = FakeVariable("22%")
    screen._stop_status_animation = lambda: None
    snapshot = JobSnapshot(
        id="job-1",
        name="Estabilização",
        state=JobState.CANCELLED,
        progress=22,
    )

    screen._apply_job_snapshot(snapshot)

    assert screen._active_job_id is None
    assert screen.progress_var_main.get() == 0
    assert screen.restore_progress_var.get() == 0
    assert screen.status_progress["value"] == 0
    assert screen.status_percent_var.get() == "0%"
    assert screen.cancel_job_btn.values["state"] == "disabled"
    assert screen.show_job_btn.values["text"] == "Ver resultado"
    assert screen.status_var.get() == "Estabilização cancelada"
