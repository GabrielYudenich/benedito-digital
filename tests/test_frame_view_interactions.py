import sys
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from gui.screens.editor_screen import EditorScreen


class FakeCanvas:
    def __init__(self):
        self.configurations = []
        self.items = []

    def configure(self, **values):
        self.configurations.append(values)

    def create_line(self, *coordinates, **values):
        self.items.append(("line", coordinates, values))

    def create_oval(self, *coordinates, **values):
        self.items.append(("oval", coordinates, values))

    def delete(self, tag):
        self.items.append(("delete", tag, {}))


class FakeVariable:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


class FakeLabel:
    def __init__(self):
        self.text = None

    def config(self, **values):
        self.text = values.get("text", self.text)


class FakeTree:
    def __init__(self):
        self.items = {}

    def item(self, item, **values):
        self.items[item] = values


class FakeRoot:
    def __init__(self):
        self.scheduled = []
        self.cancelled = []

    def after(self, delay, callback):
        job = len(self.scheduled) + 1
        self.scheduled.append((job, delay, callback))
        return job

    def after_cancel(self, job):
        self.cancelled.append(job)


class FakeFrameManager:
    def __init__(self, total, current=0):
        self.frames = [f"frame_{index:04d}.png" for index in range(total)]
        self.current_frame_index = current

    def go_to_frame(self, index):
        if 0 <= index < len(self.frames):
            self.current_frame_index = index
            return True
        return False


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


def test_brush_draws_continuous_stroke_at_selected_size():
    screen = object.__new__(EditorScreen)
    screen.frame_manager = SimpleNamespace(
        get_current_frame_info=lambda: {
            "path": "frame.png",
            "width": 200,
            "height": 100,
        }
    )
    screen.frame_canvas = FakeCanvas()
    screen.brush_size = 9
    screen._view_scale = 1.0
    screen._view_offset = (0, 0)
    screen._current_mask = Image.new("L", (200, 100), 0)
    screen._current_mask_path = "frame.png"
    screen._active_stroke = {
        "tool": "brush",
        "radius": 9,
        "value": 255,
        "points": [],
    }
    screen._brush_preview_canvas_point = None

    screen._apply_brush(20, 50, 255)
    screen._apply_brush(170, 50, 255)

    pixels = np.asarray(screen._current_mask)
    assert pixels[50, 20] == 255
    assert pixels[50, 95] == 255
    assert pixels[50, 170] == 255
    assert pixels[42, 95] == 255
    assert any(item[0] == "line" for item in screen.frame_canvas.items)


def test_primary_drag_routes_erase_events_to_eraser():
    screen = object.__new__(EditorScreen)
    screen.selected_tool = "erase"
    calls = []
    screen._on_erase_start = lambda event: calls.append(("start", event.x))
    screen._on_erase_move = lambda event: calls.append(("move", event.x))
    screen._on_erase_end = lambda event: calls.append(("end", event.x))
    event = SimpleNamespace(x=42, y=15)

    screen._on_primary_start(event)
    screen._on_primary_move(event)
    screen._on_primary_end(event)

    assert calls == [("start", 42), ("move", 42), ("end", 42)]


def test_thumbnail_zoom_uses_discrete_buttons_and_clear_percentage():
    screen = object.__new__(EditorScreen)
    screen.filmstrip_zoom_var = FakeVariable(1.2)
    screen.filmstrip_zoom_label = FakeLabel()
    updates = []
    screen._schedule_filmstrip_update = updates.append

    screen._change_filmstrip_zoom(0.2)
    screen._change_filmstrip_zoom(-0.2)

    assert screen.filmstrip_zoom_var.get() == 1.2
    assert screen.filmstrip_zoom_label.text == "120%"
    assert updates == [20, 20]


def test_work_range_is_active_without_refreshing_hidden_filmstrip():
    screen = object.__new__(EditorScreen)
    screen.frame_manager = FakeFrameManager(1000, current=60)
    screen.range_start_var = FakeVariable("61")
    screen.range_end_var = FakeVariable("817")
    screen.range_summary_var = FakeVariable("")
    screen.status_var = FakeVariable("")
    screen._draw_range_overview = lambda: None
    assert screen._commit_work_range() is True
    assert screen._current_work_range() == (60, 816)
    assert "61–817" in screen.range_summary_var.get()
    assert "automaticamente" in screen.status_var.get()


def test_review_panel_status_updates_catalog_and_timeline():
    stored = {}
    workspace = SimpleNamespace(
        set_frame_status=lambda frame, status, note: stored.update(
            {frame: {"status": status, "note": note}}
        ),
        get_frame_status=lambda frame: stored.get(frame),
    )
    screen = object.__new__(EditorScreen)
    screen.workspace = workspace
    screen.frame_manager = SimpleNamespace(
        get_current_frame_info=lambda: {"index": 12}
    )
    screen.status_var = FakeVariable("")
    screen._frame_review_panel = None
    updates = []
    screen._refresh_frame_catalog = lambda: updates.append("catalog")
    screen._refresh_loaded_media_frame_statuses = lambda: updates.append("tree")
    screen._draw_range_overview = lambda: updates.append("timeline")

    screen._set_current_frame_status("Risco", "Risco vertical")

    assert stored[12] == {"status": "scratch", "note": "Risco vertical"}
    assert updates == ["catalog", "tree", "timeline"]
    assert "Frame 13: Risco" == screen.status_var.get()


def test_loaded_media_tree_updates_flagged_frame_label_and_color():
    screen = object.__new__(EditorScreen)
    screen.media_tree = FakeTree()
    screen._media_tree_items = {
        "frame-2": {
            "kind": "frame",
            "index": 1,
            "filename": "frame_000002.png",
        }
    }
    screen._frame_status_label = lambda _index: ("review", "Revisar", {})

    screen._refresh_loaded_media_frame_statuses()

    assert screen.media_tree.items["frame-2"] == {
        "text": "⚠ frame_000002.png — Revisar",
        "tags": ("review",),
    }


def test_second_screen_counter_time_and_source_offset():
    screen = object.__new__(EditorScreen)
    screen.current_video = "trecho.mov"
    screen.workspace = SimpleNamespace(
        data={
            "originals": {
                "hash": {
                    "path": "media/originals/trecho.mov",
                    "provenance": {"start_time": 510.0},
                }
            }
        }
    )

    assert screen._format_counter_time(641.125) == "00:10:41.125"
    assert screen._source_time_offset() == 510.0


def test_burn_in_counters_change_rendered_frame():
    screen = object.__new__(EditorScreen)
    screen.frame_manager = FakeFrameManager(120)
    screen._source_time_offset = lambda: 510.0
    image = np.zeros((240, 640, 3), dtype=np.uint8)
    useful = SimpleNamespace(start=30)

    result = screen._draw_burn_in_counters(image, 60, 30.0, useful)

    assert result is image
    assert int(result.sum()) > 0


def test_frame_review_plays_selected_range_without_audio_controls():
    screen = object.__new__(EditorScreen)
    screen.root = FakeRoot()
    screen.frame_manager = FakeFrameManager(20, current=0)
    screen.range_start_var = FakeVariable("3")
    screen.range_end_var = FakeVariable("7")
    screen.frame_review_speed_var = FakeVariable("0.5x")
    screen.video_player = SimpleNamespace(fps=20)
    screen.status_var = FakeVariable("")
    screen._frame_review_playing = False
    screen._frame_review_direction = 1
    screen._frame_review_job = None
    screen._frame_review_next_due = None
    displayed = []
    screen.show_current_frame = lambda: displayed.append(
        screen.frame_manager.current_frame_index
    )
    screen.update_frame_counter = lambda: None

    screen.start_frame_review(1)

    assert screen.frame_manager.current_frame_index == 2
    assert "sem áudio" in screen.status_var.get()
    assert screen._frame_review_playing is True
    screen._frame_review_job = None
    screen._frame_review_next_due = time.perf_counter() - 0.01
    screen._frame_review_tick()
    assert screen.frame_manager.current_frame_index == 3
    assert displayed[-1] == 3
