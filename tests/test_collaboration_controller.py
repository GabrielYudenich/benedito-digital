import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.controllers.collaboration_controller import CollaborationController


def test_remote_path_is_remembered_in_recreatable_cache(tmp_path):
    editor = SimpleNamespace(workspace=SimpleNamespace(cache_dir=tmp_path))
    controller = CollaborationController(editor)

    controller.save_remote_path(tmp_path / "team")

    assert controller.load_remote_path() == str(tmp_path / "team")
    assert json.loads((tmp_path / "collaboration.json").read_text(encoding="utf-8"))["remote_path"]
