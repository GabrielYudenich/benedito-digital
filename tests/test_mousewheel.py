import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.mousewheel import scroll_canvas_if_within


class Widget:
    def __init__(self, master=None):
        self.master = master


class Canvas(Widget):
    def __init__(self, master=None):
        super().__init__(master)
        self.scrolls = []

    def yview_scroll(self, units, kind):
        self.scrolls.append((units, kind))


def test_properties_scroll_ignores_events_from_modal_window():
    canvas = Canvas()
    properties = Widget(canvas)
    modal_widget = Widget(Widget())
    event = SimpleNamespace(widget=modal_widget, delta=-120, num=0)

    assert scroll_canvas_if_within(event, canvas, properties) is None
    assert canvas.scrolls == []


def test_properties_scroll_only_moves_its_own_descendants():
    canvas = Canvas()
    properties = Widget(canvas)
    property_control = Widget(properties)
    event = SimpleNamespace(widget=property_control, delta=-120, num=0)

    assert scroll_canvas_if_within(event, canvas, properties) == "break"
    assert canvas.scrolls == [(1, "units")]
