"""FFmpeg renderer for the open Benedito edit timeline."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable, Optional

from core.edit_timeline import EditTimeline
from core.paths import executable_path
from lib.modules.video.renderer.video_renderer import VideoRenderer


class TimelineRenderCancelled(Exception):
    pass


class TimelineRenderer:
    def build_command(self, timeline: EditTimeline, output_path) -> list[str]:
        if timeline.duration <= 0:
            raise ValueError("Timeline is empty")
        clips = sorted(timeline.clips.values(), key=lambda item: (item.timeline_start, item.id))
        missing = [clip.source for clip in clips if not Path(clip.source).is_file()]
        if missing:
            raise FileNotFoundError(f"Timeline source does not exist: {missing[0]}")
        command = [executable_path("ffmpeg"), "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats"]
        for clip in clips:
            command.extend(["-i", clip.source])

        filters = [
            f"color=c=black:s={timeline.width}x{timeline.height}:r={timeline.fps:.12g}:d={timeline.duration:.9f}[base0]"
        ]
        video_chain = "base0"
        video_number = 0
        audio_labels = []
        transition_by_to = {item.to_clip: item for item in timeline.transitions.values()}
        transition_by_from = {item.from_clip: item for item in timeline.transitions.values()}
        for input_index, clip in enumerate(clips):
            track = timeline.tracks[clip.track_id]
            if not clip.enabled or track.muted:
                continue
            if track.kind == "video":
                scale = max(0.01, clip.value_at("scale", clip.timeline_start, 1.0))
                rotation = clip.value_at("rotation", clip.timeline_start, 0.0)
                opacity = min(1.0, max(0.0, clip.value_at("opacity", clip.timeline_start, clip.opacity)))
                x = clip.value_at("x", clip.timeline_start, 0.0)
                y = clip.value_at("y", clip.timeline_start, 0.0)
                scale_expression = self._curve_expression(clip.keyframes.get("scale"), "t", scale)
                rotation_expression = self._curve_expression(clip.keyframes.get("rotation"), "t", rotation)
                x_expression = self._curve_expression(clip.keyframes.get("x"), f"t-{clip.timeline_start:.9f}", x)
                y_expression = self._curve_expression(clip.keyframes.get("y"), f"t-{clip.timeline_start:.9f}", y)
                label = f"clipv{video_number}"
                parts = [
                    f"[{input_index}:v]trim=start={clip.source_in:.9f}:end={clip.source_out:.9f}",
                    "setpts=PTS-STARTPTS",
                    f"scale={timeline.width}:{timeline.height}:force_original_aspect_ratio=decrease",
                ]
                if clip.keyframes.get("scale") or scale != 1.0:
                    parts.append(f"scale='iw*({scale_expression})':'ih*({scale_expression})':eval=frame")
                if clip.keyframes.get("rotation") or rotation:
                    parts.append(f"rotate='({rotation_expression})*PI/180':c=none:ow=rotw(iw):oh=roth(ih)")
                parts.extend(["format=rgba", f"colorchannelmixer=aa={opacity:.9f}"])
                incoming = transition_by_to.get(clip.id)
                outgoing = transition_by_from.get(clip.id)
                if incoming:
                    parts.append(f"fade=t=in:st=0:d={incoming.duration:.9f}:alpha=1")
                if outgoing:
                    start = max(0.0, clip.duration - outgoing.duration)
                    parts.append(f"fade=t=out:st={start:.9f}:d={outgoing.duration:.9f}:alpha=1")
                parts.append(f"setpts=PTS+{clip.timeline_start:.9f}/TB[{label}]")
                filters.append(",".join(parts))
                next_chain = f"base{video_number + 1}"
                filters.append(
                    f"[{video_chain}][{label}]overlay=x='(W-w)/2+({x_expression})':y='(H-h)/2+({y_expression})':"
                    f"enable='between(t,{clip.timeline_start:.9f},{clip.timeline_end:.9f})'[{next_chain}]"
                )
                video_chain = next_chain
                video_number += 1
            elif track.kind == "audio":
                label = f"clipa{len(audio_labels)}"
                delay = max(0, int(round(clip.timeline_start * 1000)))
                volume = max(0.0, clip.value_at("volume", clip.timeline_start, 1.0))
                volume_expression = self._curve_expression(clip.keyframes.get("volume"), "t", volume)
                filters.append(
                    f"[{input_index}:a]atrim=start={clip.source_in:.9f}:end={clip.source_out:.9f},"
                    f"asetpts=PTS-STARTPTS,volume='{volume_expression}':eval=frame,adelay={delay}:all=1[{label}]"
                )
                audio_labels.append(label)

        filters.append(f"[{video_chain}]format=yuv420p[vout]")
        if audio_labels:
            joined = "".join(f"[{label}]" for label in audio_labels)
            filters.append(f"{joined}amix=inputs={len(audio_labels)}:duration=longest:normalize=0[aout]")
        command.extend(["-filter_complex", ";".join(filters), "-map", "[vout]"])
        if audio_labels:
            command.extend(["-map", "[aout]", "-c:a", "aac", "-b:a", "192k"])
        encoder = VideoRenderer._select_h264_encoder()
        if encoder == "libopenh264":
            command.extend(["-c:v", encoder, "-b:v", "12M", "-maxrate", "18M", "-bufsize", "36M"])
        else:
            command.extend(["-c:v", encoder, "-preset", "slow", "-crf", "17"])
        command.extend([
            "-r", f"{timeline.fps:.12g}",
            "-t", f"{timeline.duration:.9f}",
            "-movflags", "+faststart",
            "-y", str(output_path),
        ])
        return command

    @staticmethod
    def _curve_expression(curve, variable, default):
        if curve is None or not curve.keyframes:
            return f"{float(default):.9f}"
        points = curve.keyframes
        expression = f"{points[-1].value:.9f}"
        for left, right in reversed(list(zip(points, points[1:]))):
            if left.interpolation == "step":
                segment = f"{left.value:.9f}"
            else:
                position = f"(({variable})-{left.time:.9f})/{max(1e-9, right.time - left.time):.9f}"
                if left.interpolation == "smooth":
                    position = f"({position})*({position})*(3-2*({position}))"
                segment = f"{left.value:.9f}+({right.value - left.value:.9f})*({position})"
            expression = f"if(lte(({variable}),{right.time:.9f}),{segment},{expression})"
        return f"if(lte(({variable}),{points[0].time:.9f}),{points[0].value:.9f},{expression})"

    def render(
        self,
        timeline: EditTimeline,
        output_path,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> Path:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        command = self.build_command(timeline, destination)
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=VideoRenderer._creation_flags(),
        )
        output_lines = []
        try:
            if process.stdout is None:
                raise RuntimeError("FFmpeg progress stream is unavailable")
            for line in process.stdout:
                output_lines.append(line.rstrip())
                if cancel_callback and cancel_callback():
                    process.terminate()
                    raise TimelineRenderCancelled("Timeline render cancelled")
                key, separator, value = line.strip().partition("=")
                if separator:
                    seconds = VideoRenderer._parse_progress_time(key, value)
                    if seconds is not None and progress_callback:
                        progress_callback(min(99.0, seconds * 100.0 / timeline.duration))
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError("FFmpeg timeline render failed: " + "\n".join(output_lines[-20:]))
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
        if progress_callback:
            progress_callback(100.0)
        return destination
