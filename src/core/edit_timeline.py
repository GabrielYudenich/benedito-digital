"""Open non-linear edit timeline model for Benedito projects."""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from .keyframes import KeyframeCurve


@dataclass
class TimelineTrack:
    id: str
    name: str
    kind: str = "video"
    locked: bool = False
    muted: bool = False


@dataclass
class TimelineClip:
    id: str
    track_id: str
    source: str
    name: str
    source_in: float
    source_out: float
    timeline_start: float
    enabled: bool = True
    opacity: float = 1.0
    keyframes: Dict[str, KeyframeCurve] = field(default_factory=dict)

    @property
    def duration(self):
        return self.source_out - self.source_in

    @property
    def timeline_end(self):
        return self.timeline_start + self.duration

    def value_at(self, parameter: str, timeline_time: float, default: float):
        curve = self.keyframes.get(parameter)
        if curve is None:
            return default
        return curve.evaluate(max(0.0, timeline_time - self.timeline_start), default)


@dataclass
class TimelineTransition:
    id: str
    from_clip: str
    to_clip: str
    kind: str = "crossfade"
    duration: float = 0.5


class EditTimeline:
    SCHEMA_VERSION = 1

    def __init__(self, fps=24.0, width=1920, height=1080):
        if fps <= 0 or width <= 0 or height <= 0:
            raise ValueError("Timeline format must be positive")
        self.fps = float(fps)
        self.width = int(width)
        self.height = int(height)
        self.tracks: Dict[str, TimelineTrack] = {}
        self.clips: Dict[str, TimelineClip] = {}
        self.transitions: Dict[str, TimelineTransition] = {}
        self.add_track("Vídeo 1", "video", track_id="video-1")
        self.add_track("Áudio 1", "audio", track_id="audio-1")

    @property
    def duration(self):
        return max((clip.timeline_end for clip in self.clips.values() if clip.enabled), default=0.0)

    def add_track(self, name, kind="video", track_id=None):
        if kind not in {"video", "audio"}:
            raise ValueError("Track kind must be video or audio")
        identifier = track_id or uuid.uuid4().hex
        if identifier in self.tracks:
            raise ValueError("Track already exists")
        track = TimelineTrack(identifier, str(name).strip() or kind.title(), kind)
        self.tracks[identifier] = track
        return track

    def add_clip(
        self,
        track_id,
        source,
        source_in,
        source_out,
        timeline_start,
        name=None,
        clip_id=None,
    ):
        track = self._track(track_id)
        if track.locked:
            raise ValueError("Track is locked")
        source_in = float(source_in)
        source_out = float(source_out)
        timeline_start = float(timeline_start)
        if source_in < 0 or source_out <= source_in or timeline_start < 0:
            raise ValueError("Invalid clip timing")
        identifier = clip_id or uuid.uuid4().hex
        if identifier in self.clips:
            raise ValueError("Clip already exists")
        source_value = str(Path(source).expanduser())
        clip = TimelineClip(
            id=identifier,
            track_id=track.id,
            source=source_value,
            name=str(name or Path(source_value).name),
            source_in=source_in,
            source_out=source_out,
            timeline_start=timeline_start,
        )
        self.clips[identifier] = clip
        return clip

    def move_clip(self, clip_id, timeline_start, track_id=None):
        clip = self._clip(clip_id)
        destination = self._track(track_id or clip.track_id)
        if destination.locked:
            raise ValueError("Track is locked")
        value = float(timeline_start)
        if value < 0:
            raise ValueError("Timeline start cannot be negative")
        clip.timeline_start = value
        clip.track_id = destination.id
        return clip

    def trim_clip(self, clip_id, source_in, source_out):
        clip = self._clip(clip_id)
        source_in = float(source_in)
        source_out = float(source_out)
        if source_in < 0 or source_out <= source_in:
            raise ValueError("Invalid trim range")
        clip.source_in = source_in
        clip.source_out = source_out
        return clip

    def split_clip(self, clip_id, timeline_time):
        clip = self._clip(clip_id)
        split = float(timeline_time)
        if not clip.timeline_start < split < clip.timeline_end:
            raise ValueError("Split point must be inside the clip")
        source_split = clip.source_in + split - clip.timeline_start
        original_out = clip.source_out
        clip.source_out = source_split
        right = self.add_clip(
            clip.track_id,
            clip.source,
            source_split,
            original_out,
            split,
            name=f"{clip.name} (parte 2)",
        )
        right.opacity = clip.opacity
        right.keyframes = {
            name: KeyframeCurve.from_list(curve.to_list())
            for name, curve in clip.keyframes.items()
        }
        return clip, right

    def remove_clip(self, clip_id):
        self._clip(clip_id)
        del self.clips[clip_id]
        self.transitions = {
            identifier: transition
            for identifier, transition in self.transitions.items()
            if transition.from_clip != clip_id and transition.to_clip != clip_id
        }

    def add_transition(self, from_clip, to_clip, kind="crossfade", duration=0.5):
        left = self._clip(from_clip)
        right = self._clip(to_clip)
        if left.track_id != right.track_id:
            raise ValueError("Transition clips must share a track")
        if kind not in {"crossfade", "fade", "dip_to_black"}:
            raise ValueError("Unsupported transition")
        duration = float(duration)
        if duration <= 0 or duration > min(left.duration, right.duration):
            raise ValueError("Invalid transition duration")
        transition = TimelineTransition(uuid.uuid4().hex, left.id, right.id, kind, duration)
        self.transitions[transition.id] = transition
        return transition

    def set_keyframe(self, clip_id, parameter, time, value, interpolation="linear"):
        clip = self._clip(clip_id)
        if parameter not in {"x", "y", "scale", "rotation", "opacity", "volume"}:
            raise ValueError("Unsupported keyframe parameter")
        curve = clip.keyframes.setdefault(parameter, KeyframeCurve())
        return curve.set(time, value, interpolation)

    def active_clips(self, timeline_time, kind=None):
        time_value = float(timeline_time)
        tracks = self.tracks
        return sorted(
            [
                clip
                for clip in self.clips.values()
                if clip.enabled
                and clip.timeline_start <= time_value < clip.timeline_end
                and (kind is None or tracks[clip.track_id].kind == kind)
            ],
            key=lambda clip: list(tracks).index(clip.track_id),
        )

    def save(self, path):
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(temporary, destination)

    def to_dict(self):
        return {
            "schema_version": self.SCHEMA_VERSION,
            "format": {"fps": self.fps, "width": self.width, "height": self.height},
            "tracks": [vars(track) for track in self.tracks.values()],
            "clips": [
                {
                    **{key: value for key, value in vars(clip).items() if key != "keyframes"},
                    "keyframes": {name: curve.to_list() for name, curve in clip.keyframes.items()},
                }
                for clip in self.clips.values()
            ],
            "transitions": [vars(transition) for transition in self.transitions.values()],
        }

    @classmethod
    def load(cls, path):
        source = Path(path)
        if not source.exists():
            return cls()
        data = json.loads(source.read_text(encoding="utf-8"))
        if data.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError("Unsupported timeline schema")
        format_data = data.get("format", {})
        timeline = cls(format_data.get("fps", 24), format_data.get("width", 1920), format_data.get("height", 1080))
        timeline.tracks = {}
        for value in data.get("tracks", []):
            timeline.tracks[value["id"]] = TimelineTrack(**value)
        for value in data.get("clips", []):
            keyframes = {
                name: KeyframeCurve.from_list(points)
                for name, points in value.pop("keyframes", {}).items()
            }
            clip = TimelineClip(**value, keyframes=keyframes)
            timeline.clips[clip.id] = clip
        for value in data.get("transitions", []):
            transition = TimelineTransition(**value)
            timeline.transitions[transition.id] = transition
        timeline._validate()
        return timeline

    def _validate(self):
        if not self.tracks:
            raise ValueError("Timeline must contain tracks")
        for clip in self.clips.values():
            self._track(clip.track_id)
            if clip.duration <= 0 or clip.timeline_start < 0:
                raise ValueError("Invalid clip in timeline")
        for transition in self.transitions.values():
            self._clip(transition.from_clip)
            self._clip(transition.to_clip)

    def _track(self, track_id):
        try:
            return self.tracks[track_id]
        except KeyError as error:
            raise ValueError("Track does not exist") from error

    def _clip(self, clip_id):
        try:
            return self.clips[clip_id]
        except KeyError as error:
            raise ValueError("Clip does not exist") from error
