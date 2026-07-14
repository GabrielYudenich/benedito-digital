import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.shortcuts import ShortcutPreferences, shortcut_to_tk


def test_shortcut_notation_converts_to_tk_sequences():
    assert shortcut_to_tk("Ctrl+Alt+P") == "<Control-Alt-p>"
    assert shortcut_to_tk("Shift+S") == "<Shift-s>"
    assert shortcut_to_tk("F8") == "<F8>"
    assert shortcut_to_tk("Left") == "<Left>"


def test_shortcuts_are_saved_per_user_and_reject_conflicts(tmp_path):
    path = tmp_path / "shortcuts.json"
    preferences = ShortcutPreferences(path)
    values = dict(preferences.values)
    values["clean_plate"] = "Ctrl+Alt+B"
    preferences.replace(values)

    assert ShortcutPreferences(path).get("clean_plate") == "Ctrl+Alt+B"
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1

    values["preview"] = "Ctrl+Alt+B"
    with pytest.raises(ValueError):
        preferences.replace(values)
