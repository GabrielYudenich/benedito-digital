"""
Video Renderer for Benedito Digital
Advanced video rendering with frame processing and preview capabilities
"""

from __future__ import annotations

import cv2
import json
import numpy as np
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, List, Optional, Dict, Sequence, Tuple

from core.paths import executable_path
from lib.utils.logger import get_logger


EXPORT_PROFILES = {
    "delivery": {
        "label": "Entrega MP4 (H.264)",
        "extension": ".mp4",
        "video": ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-pix_fmt", "yuv420p"],
        "audio": ["-c:a", "aac", "-b:a", "192k"],
        "container": ["-movflags", "+faststart"],
    },
    "mezzanine": {
        "label": "Intermediário MOV (ProRes 422 HQ)",
        "extension": ".mov",
        "video": ["-c:v", "prores_ks", "-profile:v", "3", "-pix_fmt", "yuv422p10le"],
        "audio": ["-c:a", "pcm_s24le"],
        "container": [],
    },
    "archive": {
        "label": "Arquivo MKV sem perda (FFV1)",
        "extension": ".mkv",
        "video": ["-c:v", "ffv1", "-level", "3", "-coder", "1", "-context", "1", "-pix_fmt", "rgb24"],
        "audio": ["-c:a", "flac"],
        "container": [],
    },
}

logger = get_logger()

class VideoRenderer:
    """Advanced video renderer with frame processing capabilities"""

    def __init__(self, use_gpu: bool = True):
        self.use_gpu = use_gpu
        self.logger = logger
        self.temp_dir = None
        self.setup_temp_directory()

    def setup_temp_directory(self):
        """Setup temporary directory for rendering"""
        try:
            self.temp_dir = tempfile.mkdtemp(prefix="benedito_render_")
            self.logger.info(f"Created temporary directory: {self.temp_dir}")
        except Exception as e:
            self.logger.error(f"Error creating temp directory: {e}")
            self.temp_dir = tempfile.gettempdir()

    def cleanup_temp_directory(self, log_messages: bool = True):
        """Clean up temporary files"""
        try:
            if self.temp_dir and os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir)
                if log_messages:
                    self.logger.info(f"Cleaned up temporary directory: {self.temp_dir}")
            self.temp_dir = None
        except Exception as e:
            if log_messages:
                self.logger.error(f"Error cleaning temp directory: {e}")

    def get_video_info(self, video_path: str) -> Optional[Dict]:
        """Get video information using OpenCV"""
        try:
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                return None

            info = {
                'width': int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'duration': int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) / cap.get(cv2.CAP_PROP_FPS)
            }

            cap.release()
            return info

        except Exception as e:
            self.logger.error(f"Error getting video info: {e}")
            return None

    def extract_frames_segment(self, video_path: str, start_time: float, end_time: float,
                              output_dir: str, fps: Optional[float] = None) -> bool:
        """Extract frames from a specific time segment"""
        try:
            video_info = self.get_video_info(video_path)
            if not video_info:
                return False

            # Use original FPS if not specified
            if fps is None:
                fps = video_info['fps']

            # FFmpeg command for segment extraction
            output_pattern = os.path.join(output_dir, "frame_%04d.png")

            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-ss', str(start_time),
                '-t', str(end_time - start_time),
                '-vf', f'fps={fps}',
                '-qscale:v', '2',
                '-y',
                output_pattern
            ]

            self.logger.log_ffmpeg_command(' '.join(cmd), 'segment extraction')

            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                self.logger.info(f"Extracted frames from {start_time}s to {end_time}s")
                return True
            else:
                self.logger.error(f"FFmpeg error: {result.stderr}")
                return False

        except Exception as e:
            self.logger.error(f"Error extracting frames segment: {e}")
            return False

    def render_frames_to_video(
        self,
        frames_dir: str,
        output_path: str,
        fps: float = 30,
        codec: str = "h264",
        quality: str = "high",
        profile: Optional[str] = None,
        audio_source: Optional[str] = None,
        audio_start: float = 0.0,
        preserve_audio: bool = True,
        progress_callback: Optional[Callable[[float], None]] = None,
        cancel_callback: Optional[Callable[[], bool]] = None,
    ) -> bool:
        """Render an ordered image sequence with optional synchronized source audio."""
        try:
            frame_files = sorted(
                Path(frames_dir) / name
                for name in os.listdir(frames_dir)
                if name.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
            )
            if not frame_files:
                self.logger.error("No frames found for rendering")
                return False
            if fps <= 0:
                raise ValueError("FPS must be greater than zero")

            selected_profile = profile or {
                "prores": "mezzanine",
                "uncompressed": "archive",
            }.get(codec, "delivery")
            if selected_profile not in EXPORT_PROFILES:
                raise ValueError(f"Unknown export profile: {selected_profile}")

            output = Path(output_path)
            output.parent.mkdir(parents=True, exist_ok=True)
            duration = len(frame_files) / float(fps)
            manifest_path = Path(self.temp_dir) / f"frames_{os.getpid()}_{id(frame_files)}.ffconcat"
            self._write_frame_manifest(manifest_path, frame_files, fps)
            try:
                source_metadata = self._probe_source_metadata(audio_source) if audio_source else {}
                command = self._build_render_command(
                    manifest_path=manifest_path,
                    output_path=output,
                    duration=duration,
                    fps=fps,
                    profile=selected_profile,
                    audio_source=Path(audio_source) if audio_source and preserve_audio else None,
                    audio_start=audio_start,
                    source_metadata=source_metadata,
                    h264_encoder=self._select_h264_encoder(),
                )
                self.logger.log_ffmpeg_command(" ".join(map(str, command)), "frame rendering")
                self._run_ffmpeg(command, duration, progress_callback, cancel_callback)
            finally:
                manifest_path.unlink(missing_ok=True)
            self.logger.info(f"Rendered video to {output_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error rendering frames to video: {e}")
            return False

    @staticmethod
    def _write_frame_manifest(path: Path, frame_files: Sequence[Path], fps: float) -> None:
        frame_duration = 1.0 / float(fps)
        lines = ["ffconcat version 1.0"]
        for frame_path in frame_files:
            escaped = frame_path.resolve().as_posix().replace("'", "'\\''")
            lines.extend([f"file '{escaped}'", f"duration {frame_duration:.12f}"])
        escaped_last = frame_files[-1].resolve().as_posix().replace("'", "'\\''")
        lines.append(f"file '{escaped_last}'")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def _build_render_command(
        manifest_path: Path,
        output_path: Path,
        duration: float,
        profile: str,
        fps: float = 30.0,
        audio_source: Optional[Path] = None,
        audio_start: float = 0.0,
        source_metadata: Optional[Dict] = None,
        h264_encoder: str = "libx264",
    ) -> List[str]:
        settings = EXPORT_PROFILES[profile]
        command = [
            executable_path("ffmpeg"), "-hide_banner", "-loglevel", "error", "-progress", "pipe:1", "-nostats",
            "-f", "concat", "-safe", "0", "-i", str(manifest_path),
        ]
        if audio_source:
            command.extend(["-ss", f"{max(0.0, audio_start):.9f}", "-i", str(audio_source)])
        command.extend(["-map", "0:v:0"])
        if audio_source:
            command.extend(["-map", "1:a?", "-map_metadata", "1", *settings["audio"]])
        if profile == "delivery" and h264_encoder == "libopenh264":
            command.extend(
                [
                    "-c:v",
                    "libopenh264",
                    "-b:v",
                    "12M",
                    "-maxrate",
                    "18M",
                    "-bufsize",
                    "36M",
                    "-pix_fmt",
                    "yuv420p",
                ]
            )
        else:
            command.extend(settings["video"])

        metadata = source_metadata or {}
        sample_aspect_ratio = metadata.get("sample_aspect_ratio")
        if sample_aspect_ratio and sample_aspect_ratio not in {"0:1", "N/A"}:
            command.extend(["-vf", f"setsar={sample_aspect_ratio.replace(':', '/')}"])
        for key, option in (
            ("color_range", "-color_range"),
            ("color_space", "-colorspace"),
            ("color_transfer", "-color_trc"),
            ("color_primaries", "-color_primaries"),
        ):
            value = metadata.get(key)
            if value and value not in {"unknown", "reserved", "N/A"}:
                command.extend([option, str(value)])
        if profile == "delivery":
            bitstream_metadata = VideoRenderer._h264_bitstream_metadata(metadata)
            if bitstream_metadata:
                command.extend(["-bsf:v", bitstream_metadata])
        command.extend(
            [
                "-fps_mode",
                "cfr",
                "-r",
                f"{fps:.12g}",
                "-t",
                f"{duration:.9f}",
                *settings["container"],
                "-y",
                str(output_path),
            ]
        )
        return command

    @staticmethod
    def _h264_bitstream_metadata(metadata: Dict) -> str:
        primaries = {
            "bt709": 1, "bt470m": 4, "bt470bg": 5, "smpte170m": 6,
            "smpte240m": 7, "film": 8, "bt2020": 9, "smpte428": 10,
            "smpte431": 11, "smpte432": 12, "jedec-p22": 22,
        }
        transfers = {
            "bt709": 1, "gamma22": 4, "gamma28": 5, "smpte170m": 6,
            "smpte240m": 7, "linear": 8, "log": 9, "log_sqrt": 10,
            "iec61966-2-4": 11, "bt1361e": 12, "iec61966-2-1": 13,
            "bt2020-10": 14, "bt2020-12": 15, "smpte2084": 16,
            "smpte428": 17, "arib-std-b67": 18,
        }
        matrices = {
            "gbr": 0, "rgb": 0, "bt709": 1, "fcc": 4, "bt470bg": 5,
            "smpte170m": 6, "smpte240m": 7, "ycgco": 8, "bt2020nc": 9,
            "bt2020c": 10, "smpte2085": 11, "chroma-derived-nc": 12,
            "chroma-derived-c": 13, "ictcp": 14,
        }
        fields = []
        for key, option, values in (
            ("color_primaries", "colour_primaries", primaries),
            ("color_transfer", "transfer_characteristics", transfers),
            ("color_space", "matrix_coefficients", matrices),
        ):
            value = str(metadata.get(key, "")).lower()
            if value in values:
                fields.append(f"{option}={values[value]}")
        return "h264_metadata=" + ":".join(fields) if fields else ""

    @staticmethod
    def _probe_source_metadata(video_path: str) -> Dict:
        try:
            result = subprocess.run(
                [
                    executable_path("ffprobe"), "-v", "error", "-select_streams", "v:0",
                    "-show_entries",
                    "stream=sample_aspect_ratio,color_range,color_space,color_transfer,color_primaries",
                    "-of", "json", video_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
                creationflags=VideoRenderer._creation_flags(),
            )
            if result.returncode != 0:
                return {}
            return (json.loads(result.stdout).get("streams") or [{}])[0]
        except (OSError, ValueError, json.JSONDecodeError, subprocess.SubprocessError):
            return {}

    @staticmethod
    def _select_h264_encoder() -> str:
        try:
            result = subprocess.run(
                [executable_path("ffmpeg"), "-hide_banner", "-encoders"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
                creationflags=VideoRenderer._creation_flags(),
            )
            for encoder in ("libx264", "libopenh264"):
                if encoder in result.stdout:
                    return encoder
        except (OSError, subprocess.SubprocessError):
            pass
        return "libx264"

    @staticmethod
    def _run_ffmpeg(
        command: Sequence[str],
        duration: float,
        progress_callback: Optional[Callable[[float], None]],
        cancel_callback: Optional[Callable[[], bool]],
    ) -> None:
        process = subprocess.Popen(
            list(command),
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
            for raw_line in process.stdout:
                if cancel_callback and cancel_callback():
                    VideoRenderer._stop_process(process)
                    raise RuntimeError("Render cancelled")
                line = raw_line.strip()
                output_lines.append(line)
                key, separator, value = line.partition("=")
                if not separator:
                    continue
                elapsed = VideoRenderer._parse_progress_time(key, value)
                if elapsed is not None and duration > 0 and progress_callback:
                    progress_callback(min(99.9, elapsed * 100.0 / duration))
                if key == "progress" and value == "end" and progress_callback:
                    progress_callback(100.0)
            return_code = process.wait()
            if return_code != 0:
                raise RuntimeError("\n".join(output_lines[-20:]) or f"FFmpeg exited with {return_code}")
            if progress_callback:
                progress_callback(100.0)
        finally:
            if process.poll() is None:
                VideoRenderer._stop_process(process)
            if process.stdout:
                process.stdout.close()

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

    def stabilize_frames_ecc(self, frames_dir: str, output_dir: str,
                             progress_callback: Optional[callable] = None,
                             use_bidirectional: bool = True,
                             window_radius: int = 1,
                             cancel_callback: Optional[Callable[[], bool]] = None) -> bool:
        """Stabilize frames using ECC alignment to neighboring frames."""
        try:
            os.makedirs(output_dir, exist_ok=True)
            frame_files = sorted([f for f in os.listdir(frames_dir)
                                 if f.endswith(('.jpg', '.jpeg', '.png'))])
            if not frame_files:
                return False

            total = len(frame_files)
            for i, fname in enumerate(frame_files):
                if cancel_callback and cancel_callback():
                    return False
                path = os.path.join(frames_dir, fname)
                img = cv2.imread(path)
                if img is None:
                    continue

                # ECC alignment (translation)
                try:
                    motion = cv2.MOTION_TRANSLATION
                    cur_g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    dx_list = []
                    dy_list = []

                    criteria = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 20, 1e-5)
                    radius = max(1, int(window_radius or 1))
                    offsets = [-1] if not use_bidirectional else list(range(-radius, radius + 1))
                    for off in offsets:
                        if cancel_callback and cancel_callback():
                            return False
                        if off == 0:
                            continue
                        j = i + off
                        if j < 0 or j >= total:
                            continue
                        neighbor = cv2.imread(os.path.join(frames_dir, frame_files[j]))
                        if neighbor is None:
                            continue
                        neighbor_g = cv2.cvtColor(neighbor, cv2.COLOR_BGR2GRAY)
                        warp = np.eye(2, 3, dtype=np.float32)
                        cv2.findTransformECC(neighbor_g, cur_g, warp, motion, criteria, None, 1)
                        dx_list.append(warp[0, 2])
                        dy_list.append(warp[1, 2])

                    dx = float(np.mean(dx_list)) if dx_list else 0.0
                    dy = float(np.mean(dy_list)) if dy_list else 0.0
                    warp = np.array([[1, 0, dx], [0, 1, dy]], dtype=np.float32)
                    h, w = img.shape[:2]
                    stabilized = cv2.warpAffine(
                        img, warp, (w, h),
                        flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
                        borderMode=cv2.BORDER_REFLECT
                    )
                except Exception:
                    stabilized = img

                if cancel_callback and cancel_callback():
                    return False
                cv2.imwrite(os.path.join(output_dir, fname), stabilized)
                if progress_callback:
                    progress_callback(((i + 1) / total) * 100.0)

            return True
        except Exception as e:
            self.logger.error(f"Error stabilizing frames: {e}")
            return False

    def render_segment_preview(self, video_path: str, start_time: float, duration: float,
                              output_path: str, apply_processing: bool = False,
                              processing_config: Optional[Dict] = None) -> bool:
        """Render a preview segment with optional processing"""
        try:
            # Create temp directory for processed frames
            temp_frames_dir = os.path.join(self.temp_dir, "preview_frames")
            os.makedirs(temp_frames_dir, exist_ok=True)

            # Extract frames from segment
            if not self.extract_frames_segment(video_path, start_time, start_time + duration, temp_frames_dir):
                return False

            # Apply processing if requested
            if apply_processing and processing_config:
                if not self.apply_processing_to_frames(temp_frames_dir, processing_config):
                    return False

            # Render to video
            video_info = self.get_video_info(video_path)
            fps = video_info['fps'] if video_info else 30

            success = self.render_frames_to_video(temp_frames_dir, output_path, fps)

            # Cleanup temp frames
            try:
                import shutil
                shutil.rmtree(temp_frames_dir)
            except:
                pass

            return success

        except Exception as e:
            self.logger.error(f"Error rendering segment preview: {e}")
            return False

    def apply_processing_to_frames(self, frames_dir: str, config: Dict) -> bool:
        """Apply processing to all frames in directory"""
        try:
            from ...frame.mask.mask_generator import MaskGenerator

            mask_generator = MaskGenerator()
            frame_files = sorted([f for f in os.listdir(frames_dir)
                                if f.endswith(('.jpg', '.jpeg', '.png'))])

            self.logger.info(f"Applying processing to {len(frame_files)} frames")

            for i, frame_file in enumerate(frame_files):
                frame_path = os.path.join(frames_dir, frame_file)

                # Get neighboring frames for temporal processing
                prev_frame = frame_files[max(0, i-1)]
                next_frame = frame_files[min(len(frame_files)-1, i+1)]

                prev_path = os.path.join(frames_dir, prev_frame)
                next_path = os.path.join(frames_dir, next_frame)

                # Load frames
                curr = cv2.imread(frame_path)
                prev_img = cv2.imread(prev_path)
                next_img = cv2.imread(next_path)

                if curr is None:
                    continue

                # Use current frame for missing neighbors
                if prev_img is None:
                    prev_img = curr.copy()
                if next_img is None:
                    next_img = curr.copy()

                # Apply temporal repair
                repaired, mask = mask_generator.temporal_repair(
                    prev_img, curr, next_img,
                    diff_thresh=config.get('diff_thresh', 25),
                    use_alignment=config.get('use_alignment', True),
                    inpaint_if_needed=config.get('inpaint_if_needed', True)
                )

                # Save processed frame
                cv2.imwrite(frame_path, repaired)

            self.logger.info("Frame processing completed")
            return True

        except Exception as e:
            self.logger.error(f"Error applying processing to frames: {e}")
            return False

    def render_full_project(self, project_path: str, output_path: str,
                           include_processing: bool = False,
                           processing_config: Optional[Dict] = None,
                           frames_dir: Optional[str] = None,
                           profile: str = "delivery",
                           audio_source: Optional[str] = None,
                           preserve_audio: bool = True,
                           progress_callback: Optional[Callable[[float], None]] = None,
                           cancel_callback: Optional[Callable[[], bool]] = None) -> bool:
        """Render entire project to video"""
        try:
            if frames_dir is None:
                restored = os.path.join(project_path, "worktrees", "principal", "restored")
                originals = os.path.join(project_path, "frames", "originals")
                legacy = os.path.join(project_path, "frames")
                frames_dir = restored if os.path.isdir(restored) else originals
                if not os.path.isdir(frames_dir):
                    frames_dir = legacy

            if not os.path.exists(frames_dir):
                self.logger.error("No frames directory found in project")
                return False

            # Apply processing if requested
            if include_processing and processing_config:
                import shutil
                processing_dir = os.path.join(self.temp_dir, "render_processing")
                if os.path.exists(processing_dir):
                    shutil.rmtree(processing_dir)
                shutil.copytree(frames_dir, processing_dir)
                if not self.apply_processing_to_frames(processing_dir, processing_config):
                    return False
                frames_dir = processing_dir

            if not audio_source:
                originals_dir = Path(project_path) / "media" / "originals"
                if originals_dir.is_dir():
                    originals = sorted(path for path in originals_dir.iterdir() if path.is_file())
                    if originals:
                        audio_source = str(originals[0])

            fps = 30.0
            if audio_source:
                video_info = self.get_video_info(audio_source)
                if video_info and video_info.get("fps"):
                    fps = float(video_info["fps"])

            # Render video
            success = self.render_frames_to_video(
                frames_dir,
                output_path,
                fps,
                profile=profile,
                audio_source=audio_source,
                preserve_audio=preserve_audio,
                progress_callback=progress_callback,
                cancel_callback=cancel_callback,
            )

            if success:
                self.logger.info(f"Full project rendered to {output_path}")

            return success

        except Exception as e:
            self.logger.error(f"Error rendering full project: {e}")
            return False

    def create_preview_with_masks(self, frames_dir: str, masks_dir: str, output_path: str,
                                 overlay_color: Tuple[int, int, int] = (255, 0, 0),
                                 alpha: float = 0.3, fps: float = 30) -> bool:
        """Create preview video with mask overlays"""
        try:
            # Create temp directory for overlay frames
            temp_overlay_dir = os.path.join(self.temp_dir, "overlay_frames")
            os.makedirs(temp_overlay_dir, exist_ok=True)

            # Get frame files
            frame_files = sorted([f for f in os.listdir(frames_dir)
                                if f.endswith(('.jpg', '.jpeg', '.png'))])

            from ...frame.mask.mask_generator import MaskGenerator
            mask_generator = MaskGenerator()

            # Apply mask overlays to frames
            for frame_file in frame_files:
                frame_path = os.path.join(frames_dir, frame_file)
                mask_file = os.path.join(masks_dir, f"mask_{frame_file}")

                if not os.path.exists(mask_file):
                    # Create empty mask if none exists
                    mask_file = None

                output_frame = os.path.join(temp_overlay_dir, frame_file)

                if mask_file and os.path.exists(mask_file):
                    mask_generator.apply_mask_to_frame(
                        frame_path, mask_file, output_frame,
                        overlay_color, alpha
                    )
                else:
                    # Just copy original frame
                    import shutil
                    shutil.copy2(frame_path, output_frame)

            # Render to video
            success = self.render_frames_to_video(temp_overlay_dir, output_path, fps)

            # Cleanup
            try:
                import shutil
                shutil.rmtree(temp_overlay_dir)
            except:
                pass

            return success

        except Exception as e:
            self.logger.error(f"Error creating preview with masks: {e}")
            return False

    def __del__(self):
        """Cleanup when object is destroyed"""
        try:
            self.cleanup_temp_directory(log_messages=False)
        except Exception:
            pass
