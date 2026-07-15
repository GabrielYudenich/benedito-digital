import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIALOGS_DIR = os.path.join(ROOT, "src", "gui", "dialogs")
if DIALOGS_DIR not in sys.path:
    sys.path.insert(0, DIALOGS_DIR)

from proxy_dialog import ProxyDialog


def test_proxy_recommendation_prefers_smaller_width_for_hd_sources():
    assert ProxyDialog.recommended_option(1280) == "Leve — 960 px"
    assert ProxyDialog.recommended_option(3840) == "Equilibrado — 1280 px"
