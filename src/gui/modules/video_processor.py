"""Video processing through FFmpeg with structured progress and cancellation."""

from __future__ import annotations

import json
import os
import subprocess
from functools import lru_cache
from fractions import Fraction
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import cv2

from core.paths import executable_path


ProgressCallback = Callable[[float], None]
CancellationCallback = Callable[[], bool]


@lru_cache(maxsize=16)
def _hardware_encoder_is_usable(ffmpeg_path: str, encoder: str) -> bool:
    try:
        result = subprocess.run(
            [
                ffmpeg_path,
                "-hide_banner",
                "-loglevel",
                "error",
                "-f",
                "lavfi",
                "-i",
                "color=size=64x64:rate=1:duration=0.1",
                "-frames:v",
                "1",
                "-pix_fmt",
                "yuv420p",
                "-c:v",
                encoder,
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            timeout=8,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
            if os.name == "nt"
            else 0,
        )
        return result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


class ProcessingCancelled(Exception):
    """Raised when an FFmpeg or frame-processing task is cancelled."""


class VideoProcessor:
    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self.gpu_encoders = self._detect_encoders()
        self.preferred_encoder = self._select_encoder()
        self.gpu_available = self.preferred_encoder not in {"libx264", "libopenh264"}

    def _detect_encoders(self) -> List[str]:
        try:
            result = subprocess.run(
                [executable_path("ffmpeg"), "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            available = []
            for encoder in (
                "h264_nvenc",
                "h264_amf",
                "h264_qsv",
                "libx264",
                "libopenh264",
            ):
                if encoder in result.stdout:
                    available.append(encoder)
            return available or ["libx264"]
        except (OSError, subprocess.SubprocessError):
            return ["libx264"]

    def _select_encoder(self) -> str:
        software_encoder = next(
            (name for name in ("libx264", "libopenh264") if name in self.gpu_encoders),
            "libx264",
        )
        if not self.use_gpu:
            return software_encoder
        for encoder in ("h264_nvenc", "h264_amf", "h264_qsv"):
            if encoder in self.gpu_encoders and _hardware_encoder_is_usable(
                executable_path("ffmpeg"), encoder
            ):
                return encoder
        return software_encoder

    def cut_video(
        self,
        input_path: str,
        output_path: str,
        start_time: float,
        end_time: float,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancellationCallback] = None,
    ) -> bool:
        """Re-encode a selected range with machine-readable progress."""
        if start_time < 0 or end_time <= start_time:
            raise ValueError("Invalid cut range")
        duration = end_time - start_time
        command = self._build_cut_command(input_path, output_path, start_time, end_time)
        return self._run_ffmpeg(command, duration, progress_callback, cancel_callback)

    def _build_cut_command(
        self, input_path: str, output_path: str, start_time: float, end_time: float
    ) -> List[str]:
        duration = end_time - start_time
        command = self._ffmpeg_prefix()
        command.extend(["-ss", str(start_time), "-i", input_path, "-t", str(duration)])

        if self.preferred_encoder == "h264_nvenc":
            command.extend(["-c:v", "h264_nvenc", "-preset", "fast", "-rc", "vbr", "-cq", "23", "-b:v", "0M"])
        elif self.preferred_encoder == "h264_amf":
            command.extend(["-c:v", "h264_amf", "-quality", "speed", "-rc", "cqp", "-qp_i", "23", "-qp_p", "23"])
        elif self.preferred_encoder == "h264_qsv":
            command.extend(["-c:v", "h264_qsv", "-preset", "fast", "-global_quality", "23"])
        elif self.preferred_encoder == "libopenh264":
            command.extend(["-c:v", "libopenh264", "-b:v", "8M", "-maxrate", "12M", "-bufsize", "24M"])
        else:
            command.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "23"])

        command.extend(["-c:a", "aac", "-b:a", "128k", "-y", output_path])
        return command

    def extract_frames(
        self,
        input_path: str,
        output_dir: str,
        frame_rate: Optional[float] = None,
        quality: int = 2,
        resolution: Optional[Tuple[int, int]] = None,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancellationCallback] = None,
        lossless: bool = True,
    ) -> bool:
        """Extract an image sequence without loading the video into memory."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        duration = self._get_video_duration(input_path)
        command = self._build_extraction_command(
            input_path, output_dir, frame_rate, quality, resolution, lossless
        )
        return self._run_ffmpeg(command, duration, progress_callback, cancel_callback)

    def create_proxy(
        self,
        input_path: str,
        output_path: str,
        max_width: int = 1280,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancellationCallback] = None,
    ) -> bool:
        """Create a lightweight H.264 editing proxy while preserving duration."""
        if max_width < 320 or max_width > 3840:
            raise ValueError("Proxy width must be between 320 and 3840")
        info = self._probe_video(input_path)
        source_width = int(info.get("width", 0) or 0)
        target_width = min(source_width, max_width) if source_width else max_width
        if target_width % 2:
            target_width -= 1
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        command = self._ffmpeg_prefix()
        command.extend(
            [
                "-i",
                input_path,
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-vf",
                f"scale={target_width}:-2:flags=lanczos",
                "-c:v",
                *self._h264_video_options("proxy"),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "128k",
                "-movflags",
                "+faststart",
                "-y",
                output_path,
            ]
        )
        return self._run_ffmpeg(
            command,
            float(info.get("duration", 0.0)),
            progress_callback,
            cancel_callback,
        )

    def restore_vhs(
        self,
        input_path: str,
        output_path: str,
        deinterlace: bool = True,
        denoise: str = "medium",
        stabilize: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancellationCallback] = None,
    ) -> bool:
        """Apply a conservative local VHS restoration chain with FFmpeg."""
        filters = self._build_vhs_filters(deinterlace, denoise, stabilize)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        command = self._ffmpeg_prefix()
        command.extend(["-i", input_path])
        if filters:
            command.extend(["-vf", ",".join(filters)])
        command.extend(
            [
                "-c:v",
                *self._h264_video_options("restoration"),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
                "-movflags",
                "+faststart",
                "-y",
                output_path,
            ]
        )
        return self._run_ffmpeg(
            command,
            self._get_video_duration(input_path),
            progress_callback,
            cancel_callback,
        )

    @staticmethod
    def _build_vhs_filters(
        deinterlace: bool, denoise: str, stabilize: bool
    ) -> List[str]:
        filters = []
        if deinterlace:
            filters.append("bwdif=mode=send_frame:parity=auto:deint=all")
        denoise_values = {
            "off": None,
            "light": "hqdn3d=1.5:1.5:3:3",
            "medium": "hqdn3d=2.5:2.0:5:4",
            "strong": "hqdn3d=4:3:7:6",
        }
        if denoise not in denoise_values:
            raise ValueError("Unknown VHS denoise strength")
        if denoise_values[denoise]:
            filters.append(denoise_values[denoise])
        if stabilize:
            filters.append("deshake=rx=16:ry=16:edge=mirror")
        filters.append("eq=contrast=1.02:saturation=1.03")
        return filters

    def _build_extraction_command(
        self,
        input_path: str,
        output_dir: str,
        frame_rate: Optional[float],
        quality: int,
        resolution: Optional[Tuple[int, int]],
        lossless: bool = True,
    ) -> List[str]:
        command = self._ffmpeg_prefix()
        command.extend(["-i", input_path])
        filters = []
        if frame_rate:
            filters.append(f"fps={frame_rate}")
        if resolution:
            width, height = resolution
            filters.append(f"scale={width}:{height}:flags=lanczos")
        if filters:
            command.extend(["-vf", ",".join(filters)])

        extension = "png" if lossless else "jpg"
        if lossless:
            command.extend(["-compression_level", "3"])
        else:
            command.extend(["-q:v", str(quality)])
        output_pattern = str(Path(output_dir) / f"frame_%06d.{extension}")
        command.extend(["-vsync", "0", "-y", output_pattern])
        return command

    def _run_ffmpeg(
        self,
        command: Sequence[str],
        duration: float,
        progress_callback: Optional[ProgressCallback],
        cancel_callback: Optional[CancellationCallback],
    ) -> bool:
        process = subprocess.Popen(
            list(command),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=self._creation_flags(),
        )
        output_lines = []
        try:
            if process.stdout is None:
                raise RuntimeError("FFmpeg progress stream is unavailable")
            for raw_line in process.stdout:
                if cancel_callback and cancel_callback():
                    self._stop_process(process)
                    raise ProcessingCancelled("Video processing cancelled")
                line = raw_line.strip()
                output_lines.append(line)
                key, separator, value = line.partition("=")
                if not separator:
                    continue
                elapsed = self._parse_progress_time(key, value)
                if elapsed is not None and duration > 0 and progress_callback:
                    progress_callback(min(99.9, elapsed * 100.0 / duration))
                if key == "progress" and value == "end" and progress_callback:
                    progress_callback(100.0)
            return_code = process.wait()
            if return_code != 0:
                error = "\n".join(output_lines[-20:])
                raise RuntimeError(error or f"FFmpeg exited with code {return_code}")
            if progress_callback:
                progress_callback(100.0)
            return True
        except BaseException:
            if process.poll() is None:
                self._stop_process(process)
            raise
        finally:
            if process.stdout:
                process.stdout.close()

    def _h264_video_options(self, purpose: str) -> List[str]:
        if self.preferred_encoder == "h264_nvenc":
            return ["h264_nvenc", "-preset", "p4", "-cq", "24" if purpose == "proxy" else "17"]
        if self.preferred_encoder == "h264_amf":
            quality = "24" if purpose == "proxy" else "17"
            return ["h264_amf", "-quality", "balanced", "-rc", "cqp", "-qp_i", quality, "-qp_p", quality]
        if self.preferred_encoder == "h264_qsv":
            return ["h264_qsv", "-preset", "medium", "-global_quality", "24" if purpose == "proxy" else "17"]
        if self.preferred_encoder == "libopenh264":
            bitrate = "4M" if purpose == "proxy" else "12M"
            maximum = "6M" if purpose == "proxy" else "18M"
            buffer_size = "12M" if purpose == "proxy" else "36M"
            return [
                "libopenh264",
                "-b:v",
                bitrate,
                "-maxrate",
                maximum,
                "-bufsize",
                buffer_size,
            ]
        preset = "veryfast" if purpose == "proxy" else "medium"
        quality = "24" if purpose == "proxy" else "17"
        return ["libx264", "-preset", preset, "-crf", quality]

    @staticmethod
    def _ffmpeg_prefix() -> List[str]:
        return [
            executable_path("ffmpeg"),
            "-hide_banner",
            "-loglevel",
            "error",
            "-progress",
            "pipe:1",
            "-nostats",
        ]

    @staticmethod
    def _parse_progress_time(key: str, value: str) -> Optional[float]:
        try:
            if key in {"out_time_us", "out_time_ms"}:
                return int(value) / 1_000_000.0
            if key == "out_time":
                hours, minutes, seconds = value.split(":")
                return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except (TypeError, ValueError):
            return None
        return None

    @staticmethod
    def _stop_process(process: subprocess.Popen) -> None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)

    @staticmethod
    def _creation_flags() -> int:
        return getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

    def _get_video_duration(self, video_path: str) -> float:
        return float(self._probe_video(video_path).get("duration", 0.0))

    def _get_video_frame_count(self, video_path: str) -> int:
        return int(self._probe_video(video_path).get("total_frames", 0))

    def _probe_video(self, video_path: str) -> Dict:
        try:
            result = subprocess.run(
                [
                    executable_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate,codec_name,bit_rate,nb_frames,duration:format=duration",
                    "-of", "json", video_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=self._creation_flags(),
            )
            if result.returncode != 0:
                return {}
            probe = json.loads(result.stdout)
            stream = (probe.get("streams") or [{}])[0]
            format_data = probe.get("format") or {}
            try:
                fps = float(Fraction(stream.get("r_frame_rate", "0/1")))
            except (ValueError, ZeroDivisionError):
                fps = 0.0
            duration = float(stream.get("duration") or format_data.get("duration") or 0)
            total_frames = int(stream.get("nb_frames") or 0)
            if total_frames == 0 and duration > 0 and fps > 0:
                total_frames = round(duration * fps)
            return {
                "duration": duration,
                "width": int(stream.get("width") or 0),
                "height": int(stream.get("height") or 0),
                "fps": fps,
                "codec": stream.get("codec_name", "unknown"),
                "bit_rate": int(stream.get("bit_rate") or 0),
                "total_frames": total_frames,
            }
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            return {}

    def process_frames_batch(
        self,
        input_frames: List[str],
        output_dir: str,
        operation: str = "enhance",
        progress_callback: Optional[ProgressCallback] = None,
        cancel_callback: Optional[CancellationCallback] = None,
    ) -> bool:
        """Process frames one at a time with bounded memory usage."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        total_frames = len(input_frames)
        for index, frame_path in enumerate(input_frames):
            if cancel_callback and cancel_callback():
                raise ProcessingCancelled("Frame processing cancelled")
            frame = cv2.imread(frame_path)
            if frame is None:
                continue
            if operation == "enhance":
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            elif operation == "denoise":
                frame = cv2.fastNlMeansDenoisingColored(frame, None, 10, 10, 7, 21)
            output_path = os.path.join(output_dir, os.path.basename(frame_path))
            if not cv2.imwrite(output_path, frame):
                raise RuntimeError(f"Could not write frame: {output_path}")
            if progress_callback:
                progress_callback((index + 1) * 100.0 / max(1, total_frames))
        return True

    def get_video_info(self, video_path: str) -> Dict:
        """Return normalized FFprobe metadata."""
        info = self._probe_video(video_path)
        info["gpu_accelerated"] = self.use_gpu and self.gpu_available
        return info
