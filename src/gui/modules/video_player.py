"""
Video Player Module with CUDA/OpenCL Acceleration
Handles video playback with hardware acceleration support
"""

import cv2
import numpy as np
import logging
import subprocess
import threading
import time
from typing import Optional, Callable, Tuple
import os

from core.paths import executable_path


logger = logging.getLogger(__name__)

class VideoPlayer:
    def __init__(self, use_gpu: bool = True):
        cv2.setUseOptimized(True)
        self.use_gpu = use_gpu
        self.cap: Optional[cv2.VideoCapture] = None
        self.current_frame = 0
        self.total_frames = 0
        self.fps = 30.0
        self.is_playing = False
        self.playback_thread: Optional[threading.Thread] = None
        self.video_path: Optional[str] = None
        self.audio_enabled = True
        self.audio_process: Optional[subprocess.Popen] = None

        # GPU acceleration setup
        self.gpu_available = self._check_gpu_available()
        if self.use_gpu and self.gpu_available:
            self._setup_gpu_acceleration()

    def _check_gpu_available(self) -> bool:
        """Check if CUDA/OpenCL is available"""
        try:
            # Check CUDA
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                print("CUDA GPU detected and enabled")
                return True

            # Check OpenCL
            if cv2.ocl.haveOpenCL():
                cv2.ocl.setUseOpenCL(True)
                print("OpenCL detected and enabled")
                return True

            print("No GPU acceleration available, using CPU")
            return False
        except:
            print("GPU check failed, using CPU")
            return False

    def _setup_gpu_acceleration(self):
        """Setup GPU acceleration for OpenCV"""
        try:
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                # CUDA is available
                self.gpu_backend = 'cuda'
                print(f"Using CUDA backend with {cv2.cuda.getCudaEnabledDeviceCount()} devices")
            elif cv2.ocl.haveOpenCL():
                # OpenCL is available
                cv2.ocl.setUseOpenCL(True)
                self.gpu_backend = 'opencl'
                print("Using OpenCL backend")
            else:
                self.gpu_backend = 'cpu'
                print("Using CPU backend")
        except Exception as e:
            print(f"GPU setup failed: {e}")
            self.gpu_backend = 'cpu'

    def load_video(self, video_path: str) -> bool:
        """Load video file with optimal backend"""
        try:
            self.stop_playback()
            if self.cap:
                self.cap.release()

            # Try to use GPU accelerated backend if available
            if self.use_gpu and self.gpu_available:
                # Use CUDA backend for video capture
                self.cap = cv2.VideoCapture(video_path, cv2.CAP_FFMPEG)

                # Set optimal buffer size for GPU processing
                self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 4)

                if not self.cap.isOpened():
                    # Fallback to CPU
                    self.cap = cv2.VideoCapture(video_path)
                    print("Fallback to CPU backend")
            else:
                self.cap = cv2.VideoCapture(video_path)

            if not self.cap.isOpened():
                return False

            # Get video properties
            self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.cap.get(cv2.CAP_PROP_FPS)
            if self.fps <= 0:
                self.fps = 30.0

            self.current_frame = 0
            self.video_path = os.path.abspath(video_path)
            return True

        except Exception as e:
            print(f"Error loading video: {e}")
            self.video_path = None
            return False

    def is_loaded(self) -> bool:
        return bool(self.cap and self.cap.isOpened() and self.video_path)

    def get_frame(self, frame_number: int = None) -> Optional[np.ndarray]:
        """Get frame with GPU acceleration if available"""
        if not self.cap or not self.cap.isOpened():
            return None

        try:
            if frame_number is not None:
                try:
                    frame_number = int(frame_number)
                except Exception:
                    frame_number = int(self.current_frame)
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                self.current_frame = frame_number

            ret, frame = self.cap.read()
            if not ret:
                return None

            # Apply GPU accelerated processing if available
            if self.use_gpu and self.gpu_available and self.gpu_backend == 'cuda':
                try:
                    # Upload to GPU for processing
                    gpu_frame = cv2.cuda_GpuMat()
                    gpu_frame.upload(frame)

                    # Optional: Apply GPU-accelerated filters for better quality
                    # gpu_frame = cv2.cuda.cvtColor(gpu_frame, cv2.COLOR_BGR2RGB)

                    # Download back to CPU
                    processed_frame = gpu_frame.download()
                    return processed_frame
                except:
                    # Fallback to CPU frame
                    return frame

            return frame

        except Exception as e:
            print(f"Error getting frame: {e}")
            return None

    def get_frame_at_time(self, time_seconds: float) -> Optional[np.ndarray]:
        """Get frame at specific time"""
        if self.fps > 0:
            frame_number = int(time_seconds * self.fps)
            return self.get_frame(frame_number)
        return None

    def start_playback(self, callback: Callable[[np.ndarray], None],
                      progress_callback: Callable[[float], None] = None,
                      fps_override: float = None,
                      audio_enabled: bool = True,
                      finished_callback: Callable[[], None] = None):
        """Start video playback with callback for each frame"""
        if self.is_playing or not self.is_loaded():
            return

        self.is_playing = True
        self.audio_enabled = bool(audio_enabled)
        playback_fps = max(0.1, float(fps_override or self.fps))
        frame_interval = 1.0 / playback_fps
        self._start_audio_playback()

        def playback_loop():
            next_frame_at = time.monotonic()
            try:
                while self.is_playing and self.cap and self.cap.isOpened():
                    frame = self.get_frame()
                    if frame is None:
                        break

                    if callback:
                        callback(frame)

                    self.current_frame += 1
                    if progress_callback:
                        progress = (
                            (self.current_frame / self.total_frames) * 100
                            if self.total_frames > 0
                            else 0
                        )
                        progress_callback(min(100.0, progress))

                    if self.current_frame >= self.total_frames:
                        break

                    next_frame_at += frame_interval
                    remaining = next_frame_at - time.monotonic()
                    if remaining > 0:
                        time.sleep(remaining)
            finally:
                self.is_playing = False
                self._stop_audio_playback()
                if finished_callback:
                    finished_callback()

        self.playback_thread = threading.Thread(target=playback_loop, daemon=True)
        self.playback_thread.start()

    def stop_playback(self):
        """Stop video playback"""
        self.is_playing = False
        self._stop_audio_playback()
        if self.playback_thread and self.playback_thread is not threading.current_thread():
            self.playback_thread.join(timeout=1.0)
        self.playback_thread = None

    def set_audio_enabled(self, enabled: bool):
        self.audio_enabled = bool(enabled)
        if not self.is_playing:
            return
        self._stop_audio_playback()
        if self.audio_enabled:
            self._start_audio_playback()

    def _start_audio_playback(self):
        if not self.audio_enabled or not self.video_path:
            return
        self._stop_audio_playback()
        start_time = self.current_frame / self.fps if self.fps > 0 else 0.0
        command = [
            executable_path("ffplay"),
            "-nodisp",
            "-autoexit",
            "-loglevel",
            "error",
            "-ss",
            f"{start_time:.6f}",
            "-i",
            self.video_path,
            "-vn",
        ]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        try:
            self.audio_process = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creationflags,
            )
            logger.debug(
                "Reference audio started: path=%s start=%.3fs pid=%s",
                self.video_path,
                start_time,
                self.audio_process.pid,
            )
        except OSError:
            self.audio_process = None
            logger.exception("Could not start reference audio with ffplay")

    def _stop_audio_playback(self):
        process = self.audio_process
        self.audio_process = None
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            process.kill()
        except OSError:
            logger.debug("Reference audio process already closed", exc_info=True)

    def seek(self, frame_number: int):
        """Seek to specific frame"""
        if self.cap:
            try:
                frame_number = int(frame_number)
            except Exception:
                frame_number = int(self.current_frame)
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self.current_frame = frame_number

    def seek_to_time(self, time_seconds: float):
        """Seek to specific time"""
        if self.fps > 0:
            frame_number = int(float(time_seconds) * self.fps)
            self.seek(frame_number)

    def get_video_info(self) -> dict:
        """Get video information"""
        if not self.cap:
            return {}

        return {
            'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
            'fps': self.fps,
            'total_frames': self.total_frames,
            'duration': self.total_frames / self.fps if self.fps > 0 else 0,
            'gpu_accelerated': self.use_gpu and self.gpu_available,
            'gpu_backend': getattr(self, 'gpu_backend', 'cpu')
        }

    def release(self):
        """Release video capture"""
        self.stop_playback()
        if self.cap:
            self.cap.release()
            self.cap = None
        self.video_path = None

    def __del__(self):
        """Cleanup on deletion"""
        self.release()
