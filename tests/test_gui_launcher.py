import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import run_gui


def test_console_message_is_safe_without_console(monkeypatch):
    monkeypatch.setattr(run_gui.sys, "stdout", None)
    run_gui.console_message("hidden")
