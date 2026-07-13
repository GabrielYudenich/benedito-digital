import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIALOGS_DIR = os.path.join(ROOT, "src", "gui", "dialogs")
if DIALOGS_DIR not in sys.path:
    sys.path.insert(0, DIALOGS_DIR)

from extraction_dialog import ExtractionDialog


def test_estimates_original_and_custom_frame_rates():
    assert ExtractionDialog.estimate_frame_count(10, "Original", 24) == 240
    assert ExtractionDialog.estimate_frame_count(10, "12", 24) == 120
    assert ExtractionDialog.estimate_frame_count(10, "inválido", 24) is None
