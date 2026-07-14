import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens.editor_screen import EditorScreen


class FakeCanvas:
    def __init__(self):
        self.configurations = []

    def configure(self, **values):
        self.configurations.append(values)


def test_right_drag_pans_instead_of_painting_or_erasing():
    screen = object.__new__(EditorScreen)
    screen.frame_pan = (10.0, 5.0)
    screen.frame_canvas = FakeCanvas()
    screen.selected_tool = "brush"
    redraws = []
    screen._schedule_frame_redraw = redraws.append

    screen._on_secondary_start(SimpleNamespace(x=100, y=100))
    screen._on_secondary_move(SimpleNamespace(x=125, y=90))
    screen._on_secondary_end(SimpleNamespace(x=125, y=90))

    assert screen.frame_pan == (35.0, -5.0)
    assert redraws == [16]
    assert screen._secondary_pan_start is None


def test_clone_right_click_still_sets_source_without_dragging():
    screen = object.__new__(EditorScreen)
    screen.frame_pan = (0.0, 0.0)
    screen.frame_canvas = FakeCanvas()
    screen.selected_tool = "clone"
    sources = []
    screen._set_retouch_source = sources.append
    event = SimpleNamespace(x=50, y=60)

    screen._on_secondary_start(event)
    screen._on_secondary_end(event)

    assert sources == [event]
