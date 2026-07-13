import logging
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.diagnostics import (
    development_diagnostics_enabled,
    start_development_diagnostics,
)


def test_source_diagnostics_capture_context_and_tk_traceback(monkeypatch, tmp_path):
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setenv("BENEDITO_DEBUG_LOG", "1")
    session = start_development_diagnostics(tmp_path / "logs")
    assert session is not None
    fake_root = SimpleNamespace(report_callback_exception=None)
    session.install_tk_exception_handler(fake_root)

    logging.getLogger("benedito.test").debug("marcador de diagnóstico")
    try:
        raise RuntimeError("falha simulada no callback")
    except RuntimeError as error:
        fake_root.report_callback_exception(type(error), error, error.__traceback__)
    log_path = session.log_path
    session.close()

    content = log_path.read_text(encoding="utf-8")
    assert "marcador de diagnóstico" in content
    assert "Exceção não tratada em callback do Tkinter" in content
    assert "RuntimeError: falha simulada no callback" in content
    assert "thread=MainThread" in content
    assert "test_source_diagnostics_capture_context_and_tk_traceback" in content


def test_frozen_executable_never_starts_diagnostic_file(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("BENEDITO_DEBUG_LOG", "1")
    destination = tmp_path / "production-logs"

    assert not development_diagnostics_enabled()
    assert start_development_diagnostics(destination) is None
    assert not destination.exists()
