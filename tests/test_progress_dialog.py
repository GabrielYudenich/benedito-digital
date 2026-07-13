import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIALOGS_DIR = os.path.join(ROOT, "src", "gui", "dialogs")
SRC_DIR = os.path.join(ROOT, "src")
for path in (DIALOGS_DIR, SRC_DIR):
    if path not in sys.path:
        sys.path.insert(0, path)

from progress_dialog import TaskProgressDialog


def test_accessible_duration_formatting():
    assert TaskProgressDialog.format_seconds(4.6) == "5 s"
    assert TaskProgressDialog.format_seconds(65) == "1 min 05 s"
    assert TaskProgressDialog.format_seconds(3720) == "1 h 02 min"
