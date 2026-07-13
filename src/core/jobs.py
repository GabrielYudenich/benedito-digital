"""Cancelable background jobs with observable progress."""

from __future__ import annotations

import logging
import threading
import time
import traceback
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


LOGGER = logging.getLogger(__name__)


class JobState(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCancelled(Exception):
    """Raised cooperatively when a job cancellation is requested."""


@dataclass(frozen=True)
class JobSnapshot:
    id: str
    name: str
    state: JobState
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: Optional[str] = None
    traceback: Optional[str] = None
    created_at: str = ""
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobContext:
    """Progress and cancellation interface passed to a running task."""

    def __init__(self, cancel_event: threading.Event, report: Callable[[float, str], None]):
        self._cancel_event = cancel_event
        self._report = report

    @property
    def cancellation_requested(self) -> bool:
        return self._cancel_event.is_set()

    def check_cancelled(self) -> None:
        if self.cancellation_requested:
            raise JobCancelled("Task cancelled")

    def report(self, progress: float, message: str = "") -> None:
        self.check_cancelled()
        self._report(progress, message)


class _Job:
    def __init__(self, snapshot: JobSnapshot):
        self.snapshot = snapshot
        self.lock = threading.RLock()
        self.cancel_event = threading.Event()
        self.finished_event = threading.Event()
        self.listeners: List[Callable[[JobSnapshot], None]] = []


class JobManager:
    """Runs bounded-memory tasks on daemon threads."""

    def __init__(self):
        self._jobs: Dict[str, _Job] = {}
        self._lock = threading.RLock()

    def submit(
        self,
        name: str,
        task: Callable[[JobContext], Any],
        on_update: Optional[Callable[[JobSnapshot], None]] = None,
    ) -> JobSnapshot:
        if not name.strip():
            raise ValueError("Job name cannot be empty")

        job_id = uuid.uuid4().hex
        snapshot = JobSnapshot(
            id=job_id,
            name=name.strip(),
            state=JobState.QUEUED,
            created_at=self._now(),
        )
        job = _Job(snapshot)
        if on_update:
            job.listeners.append(on_update)
        with self._lock:
            self._jobs[job_id] = job
        LOGGER.info(
            "Job enfileirado: id=%s nome=%r tarefa=%s.%s",
            job_id,
            snapshot.name,
            getattr(task, "__module__", "desconhecido"),
            getattr(task, "__qualname__", repr(task)),
        )
        self._notify(job)

        thread = threading.Thread(
            target=self._run,
            args=(job, task),
            name=f"benedito-job-{job_id[:8]}",
            daemon=True,
        )
        thread.start()
        return snapshot

    def cancel(self, job_id: str) -> bool:
        job = self._get_job(job_id)
        with job.lock:
            if job.snapshot.state not in {JobState.QUEUED, JobState.RUNNING}:
                return False
            job.cancel_event.set()
            LOGGER.warning(
                "Cancelamento solicitado: id=%s nome=%r progresso=%.2f",
                job.snapshot.id,
                job.snapshot.name,
                job.snapshot.progress,
            )
            return True

    def get(self, job_id: str) -> JobSnapshot:
        job = self._get_job(job_id)
        with job.lock:
            return job.snapshot

    def list(self) -> List[JobSnapshot]:
        with self._lock:
            job_ids = list(self._jobs)
        return [self.get(job_id) for job_id in job_ids]

    def wait(self, job_id: str, timeout: Optional[float] = None) -> JobSnapshot:
        job = self._get_job(job_id)
        job.finished_event.wait(timeout)
        return self.get(job_id)

    def _run(self, job: _Job, task: Callable[[JobContext], Any]) -> None:
        started = time.perf_counter()
        try:
            if job.cancel_event.is_set():
                raise JobCancelled("Task cancelled")
            self._update(job, state=JobState.RUNNING, started_at=self._now())
            LOGGER.info("Job iniciado: id=%s nome=%r", job.snapshot.id, job.snapshot.name)
            context = JobContext(job.cancel_event, lambda value, message: self._progress(job, value, message))
            result = task(context)
            context.check_cancelled()
            self._update(
                job,
                state=JobState.COMPLETED,
                progress=100.0,
                result=result,
                finished_at=self._now(),
            )
            LOGGER.info(
                "Job concluído: id=%s nome=%r duração=%.3fs resultado=%s",
                job.snapshot.id,
                job.snapshot.name,
                time.perf_counter() - started,
                type(result).__name__,
            )
        except JobCancelled:
            self._update(job, state=JobState.CANCELLED, finished_at=self._now())
            LOGGER.warning(
                "Job cancelado: id=%s nome=%r duração=%.3fs",
                job.snapshot.id,
                job.snapshot.name,
                time.perf_counter() - started,
            )
        except Exception as error:
            LOGGER.exception(
                "Job falhou: id=%s nome=%r duração=%.3fs",
                job.snapshot.id,
                job.snapshot.name,
                time.perf_counter() - started,
            )
            self._update(
                job,
                state=JobState.FAILED,
                error=str(error),
                traceback=traceback.format_exc(),
                finished_at=self._now(),
            )
        finally:
            job.finished_event.set()

    def _progress(self, job: _Job, progress: float, message: str) -> None:
        normalized = max(0.0, min(100.0, float(progress)))
        LOGGER.debug(
            "Progresso do job: id=%s nome=%r progresso=%.2f mensagem=%r",
            job.snapshot.id,
            job.snapshot.name,
            normalized,
            message,
        )
        self._update(job, progress=normalized, message=message)

    def _update(self, job: _Job, **changes: Any) -> None:
        with job.lock:
            job.snapshot = replace(job.snapshot, **changes)
        self._notify(job)

    @staticmethod
    def _notify(job: _Job) -> None:
        with job.lock:
            snapshot = job.snapshot
            listeners = list(job.listeners)
        for listener in listeners:
            try:
                listener(snapshot)
            except Exception:
                LOGGER.exception(
                    "Listener de job falhou: id=%s nome=%r listener=%r",
                    snapshot.id,
                    snapshot.name,
                    listener,
                )

    def _get_job(self, job_id: str) -> _Job:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job: {job_id}")
        return job

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
