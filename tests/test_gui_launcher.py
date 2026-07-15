import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_gui


def test_console_message_is_safe_without_console(monkeypatch):
    monkeypatch.setattr(run_gui.sys, "stdout", None)
    run_gui.console_message("hidden")


def test_source_launcher_creates_detailed_session_log(monkeypatch, tmp_path):
    import tkinter as tk
    from gui.screens import welcome_screen

    class FakeRoot:
        def title(self, _value):
            return None

        def geometry(self, _value):
            return None

        def configure(self, **_options):
            return None

        def mainloop(self):
            return None

    monkeypatch.delattr(run_gui.sys, "frozen", raising=False)
    monkeypatch.setenv("BENEDITO_DEBUG_LOG", "1")
    monkeypatch.setenv("BENEDITO_DEBUG_LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setattr(tk, "Tk", FakeRoot)
    monkeypatch.setattr(welcome_screen, "WelcomeScreen", lambda _root: object())

    assert run_gui.main() == 0

    logs = list((tmp_path / "logs").glob("benedito-debug-*.log"))
    assert len(logs) == 1
    content = logs[0].read_text(encoding="utf-8")
    assert "Sessão de diagnóstico de desenvolvimento iniciada" in content
    assert "Entrando no loop principal do Tkinter" in content
    assert "Loop principal do Tkinter encerrado normalmente" in content
