import os
import re
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.app_info import get_app_info


def test_application_metadata_comes_from_bundled_config():
    info = get_app_info()

    assert info.name == "Benedito Digital"
    assert re.fullmatch(r"\d+\.\d+\.\d+", info.version)
    assert info.license == "Apache-2.0"
