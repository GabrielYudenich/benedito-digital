import os
import sys
import threading


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.jobs import JobManager, JobState


def test_job_reports_progress_and_completes():
    manager = JobManager()
    updates = []

    def task(context):
        context.report(25, "Lendo")
        context.report(75, "Salvando")
        return {"frames": 3}

    job = manager.submit("Teste", task, updates.append)
    result = manager.wait(job.id, timeout=2)

    assert result.state == JobState.COMPLETED
    assert result.progress == 100
    assert result.result == {"frames": 3}
    assert any(update.progress == 25 and update.message == "Lendo" for update in updates)


def test_running_job_can_be_cancelled():
    manager = JobManager()
    started = threading.Event()
    continue_task = threading.Event()

    def task(context):
        started.set()
        continue_task.wait(2)
        context.check_cancelled()

    job = manager.submit("Cancelavel", task)
    assert started.wait(1)
    assert manager.cancel(job.id)
    continue_task.set()
    result = manager.wait(job.id, timeout=2)

    assert result.state == JobState.CANCELLED
    assert not manager.cancel(job.id)


def test_job_failure_is_captured():
    manager = JobManager()

    def task(_context):
        raise RuntimeError("falha esperada")

    job = manager.submit("Falha", task)
    result = manager.wait(job.id, timeout=2)

    assert result.state == JobState.FAILED
    assert result.error == "falha esperada"
    assert "RuntimeError" in result.traceback
