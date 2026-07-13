import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.edit_timeline import EditTimeline
from core.keyframes import KeyframeCurve


def test_keyframe_curve_supports_step_linear_and_smooth():
    linear = KeyframeCurve()
    linear.set(0, 0)
    linear.set(10, 100)
    assert linear.evaluate(5) == 50

    step = KeyframeCurve()
    step.set(0, 10, "step")
    step.set(2, 20)
    assert step.evaluate(1) == 10

    smooth = KeyframeCurve()
    smooth.set(0, 0, "smooth")
    smooth.set(10, 100)
    assert smooth.evaluate(5) == 50
    assert smooth.evaluate(2.5) < 25


def test_timeline_add_move_trim_split_transition_and_persist(tmp_path):
    timeline = EditTimeline(fps=25, width=720, height=576)
    first = timeline.add_clip("video-1", "roll.mov", 2, 8, 0, "Plano 1")
    second = timeline.add_clip("video-1", "roll.mov", 8, 14, 6, "Plano 2")
    timeline.move_clip(second.id, 5.5)
    timeline.trim_clip(first.id, 2.5, 8)
    timeline.add_transition(first.id, second.id, duration=0.5)
    timeline.set_keyframe(first.id, "opacity", 0, 0)
    timeline.set_keyframe(first.id, "opacity", 1, 1)
    left, right = timeline.split_clip(second.id, 8.5)
    path = tmp_path / "timeline.json"

    timeline.save(path)
    loaded = EditTimeline.load(path)

    assert loaded.fps == 25
    assert len(loaded.clips) == 3
    assert len(loaded.transitions) == 1
    assert loaded.clips[first.id].value_at("opacity", 0.5, 1) == 0.5
    assert left.timeline_end == right.timeline_start


def test_active_clips_respect_tracks_and_timing():
    timeline = EditTimeline()
    timeline.add_clip("video-1", "a.mov", 0, 5, 2)
    timeline.add_clip("audio-1", "a.wav", 0, 8, 0)

    assert len(timeline.active_clips(3, "video")) == 1
    assert len(timeline.active_clips(3, "audio")) == 1
    assert not timeline.active_clips(1, "video")


def test_rejects_invalid_timing_and_transition():
    timeline = EditTimeline()
    with pytest.raises(ValueError):
        timeline.add_clip("video-1", "a.mov", 2, 1, 0)
    first = timeline.add_clip("video-1", "a.mov", 0, 1, 0)
    second = timeline.add_clip("audio-1", "a.wav", 0, 1, 0)
    with pytest.raises(ValueError):
        timeline.add_transition(first.id, second.id)
