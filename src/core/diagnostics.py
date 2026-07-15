"""Development-only diagnostics for source GUI executions."""

from __future__ import annotations

import atexit
import faulthandler
import importlib.metadata
import logging
import os
import platform
import shutil
import sys
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional


LOGGER_NAME = "benedito.diagnostics"
_ACTIVE_SESSION: Optional["DiagnosticSession"] = None


def development_diagnostics_enabled() -> bool:
    """Enable detailed files for source runs, never for frozen executables."""
    if getattr(sys, "frozen", False):
        return False
    configured = os.environ.get("BENEDITO_DEBUG_LOG", "1").strip().lower()
    return configured not in {"0", "false", "no", "off"}


def default_diagnostic_log_dir() -> Path:
    configured = os.environ.get("BENEDITO_DEBUG_LOG_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / ".benedito" / "logs"


class DiagnosticSession:
    """Own the file handler and exception hooks for one GUI execution."""

    def __init__(self, log_directory: Path):
        self.log_directory = Path(log_directory)
        self.log_path: Optional[Path] = None
        self.handler: Optional[logging.FileHandler] = None
        self._root_level = logging.getLogger().level
        self._sys_excepthook = sys.excepthook
        self._thread_excepthook = getattr(threading, "excepthook", None)
        self._faulthandler_enabled_here = False
        self._closed = False

    def start(self) -> "DiagnosticSession":
        self.log_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        self.log_path = self.log_directory / (
            f"benedito-debug-{timestamp}-pid{os.getpid()}.log"
        )
        self.handler = logging.FileHandler(self.log_path, encoding="utf-8")
        self.handler.setLevel(logging.DEBUG)
        self.handler.setFormatter(
            logging.Formatter(
                "%(asctime)s.%(msecs)03d | %(levelname)-8s | pid=%(process)d | "
                "thread=%(threadName)s | %(name)s | %(pathname)s:%(lineno)d | "
                "%(funcName)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(self.handler)
        logging.captureWarnings(True)
        self._install_exception_hooks()
        self._enable_fault_handler()
        self._log_environment()
        self._prune_old_sessions()
        atexit.register(self.close)
        return self

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(LOGGER_NAME)

    def install_tk_exception_handler(self, root) -> None:
        def report_callback_exception(exception_type, value, traceback_object):
            self.logger.critical(
                "Exceção não tratada em callback do Tkinter",
                exc_info=(exception_type, value, traceback_object),
            )

        root.report_callback_exception = report_callback_exception
        self.logger.debug("Handler de exceções do Tkinter instalado")

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.logger.info("Sessão de diagnóstico encerrada")
        if self._faulthandler_enabled_here and faulthandler.is_enabled():
            faulthandler.disable()
        sys.excepthook = self._sys_excepthook
        if self._thread_excepthook is not None:
            threading.excepthook = self._thread_excepthook
        logging.captureWarnings(False)
        if self.handler is not None:
            root_logger = logging.getLogger()
            root_logger.removeHandler(self.handler)
            root_logger.setLevel(self._root_level)
            self.handler.flush()
            self.handler.close()

    def _install_exception_hooks(self) -> None:
        def system_exception_hook(exception_type, value, traceback_object):
            self.logger.critical(
                "Exceção não tratada na thread principal",
                exc_info=(exception_type, value, traceback_object),
            )
            self._sys_excepthook(exception_type, value, traceback_object)

        def thread_exception_hook(arguments):
            self.logger.critical(
                "Exceção não tratada em thread: %s",
                arguments.thread.name if arguments.thread else "desconhecida",
                exc_info=(
                    arguments.exc_type,
                    arguments.exc_value,
                    arguments.exc_traceback,
                ),
            )

        sys.excepthook = system_exception_hook
        if self._thread_excepthook is not None:
            threading.excepthook = thread_exception_hook

    def _enable_fault_handler(self) -> None:
        if self.handler is None or self.handler.stream is None or faulthandler.is_enabled():
            return
        try:
            faulthandler.enable(file=self.handler.stream, all_threads=True)
            self._faulthandler_enabled_here = True
        except (OSError, RuntimeError):
            self.logger.exception("Não foi possível habilitar faulthandler")

    def _log_environment(self) -> None:
        self.logger.info("=" * 88)
        self.logger.info("Sessão de diagnóstico de desenvolvimento iniciada")
        self.logger.info("Arquivo: %s", self.log_path)
        self.logger.info("Python: %s", sys.version.replace("\n", " "))
        self.logger.info("Executável Python: %s", sys.executable)
        self.logger.info("Plataforma: %s", platform.platform())
        self.logger.info("Máquina: %s | processador: %s", platform.machine(), platform.processor())
        self.logger.info("Diretório atual: %s", Path.cwd())
        self.logger.info("Argumentos: %r", sys.argv)
        self.logger.info("Modo congelado: %s", bool(getattr(sys, "frozen", False)))
        try:
            usage = shutil.disk_usage(self.log_directory)
            self.logger.info(
                "Disco dos logs: total=%d livre=%d usado=%d",
                usage.total,
                usage.free,
                usage.used,
            )
        except OSError:
            self.logger.exception("Não foi possível consultar o disco dos logs")
        for package in (
            "opencv-python",
            "opencv-contrib-python",
            "numpy",
            "Pillow",
            "torch",
            "torchvision",
            "timm",
            "einops",
        ):
            try:
                version = importlib.metadata.version(package)
            except importlib.metadata.PackageNotFoundError:
                version = "não instalado"
            self.logger.info("Dependência %s=%s", package, version)
        self.logger.info("=" * 88)

    def _prune_old_sessions(self, keep: int = 20) -> None:
        paths = sorted(
            self.log_directory.glob("benedito-debug-*.log"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for path in paths[keep:]:
            try:
                path.unlink()
            except OSError:
                self.logger.warning("Não foi possível remover log antigo: %s", path)


def start_development_diagnostics(log_directory=None) -> Optional[DiagnosticSession]:
    global _ACTIVE_SESSION
    if not development_diagnostics_enabled():
        return None
    if _ACTIVE_SESSION is not None and not _ACTIVE_SESSION._closed:
        return _ACTIVE_SESSION
    directory = Path(log_directory) if log_directory else default_diagnostic_log_dir()
    _ACTIVE_SESSION = DiagnosticSession(directory).start()
    return _ACTIVE_SESSION


def active_diagnostic_session() -> Optional[DiagnosticSession]:
    return _ACTIVE_SESSION


@contextmanager
def diagnostic_span(name: str, **details) -> Iterator[None]:
    """Log start, elapsed time and full errors for a high-level operation."""
    logger = logging.getLogger(LOGGER_NAME)
    started = time.perf_counter()
    logger.debug("INÍCIO %s | detalhes=%r", name, details)
    try:
        yield
    except BaseException:
        logger.exception("FALHA %s | duração=%.3fs", name, time.perf_counter() - started)
        raise
    else:
        logger.debug("FIM %s | duração=%.3fs", name, time.perf_counter() - started)
