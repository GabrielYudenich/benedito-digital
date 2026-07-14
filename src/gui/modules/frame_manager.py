"""
Frame Manager Module
Handles frame viewing, navigation, deletion, and renumbering
"""

import os
import cv2
import numpy as np
from typing import List, Optional, Tuple
from PIL import Image, ImageTk
import shutil
import re

class FrameManager:
    def __init__(self, project_path: str):
        # Accept either a project root or the frames directory itself
        if os.path.basename(project_path).lower() == 'frames':
            self.project_path = os.path.dirname(project_path)
            self.frames_dir = project_path
        else:
            self.project_path = project_path
            workspace_file = os.path.join(project_path, 'metadata', 'workspace.json')
            versioned_frames = os.path.join(project_path, 'frames', 'originals')
            self.frames_dir = versioned_frames if os.path.exists(workspace_file) else os.path.join(project_path, 'frames')
        self.frames_list: List[str] = []
        self.current_index = 0
        self.loaded_frame: Optional[np.ndarray] = None
        self.loaded_photo: Optional[ImageTk.PhotoImage] = None

        # Ensure frames directory exists
        os.makedirs(self.frames_dir, exist_ok=True)

        # Load existing frames
        self.refresh_frames_list()

    def refresh_frames_list(self):
        """Refresh the list of available frames"""
        try:
            if os.path.exists(self.frames_dir):
                # Get all jpg files and sort them numerically
                files = [f for f in os.listdir(self.frames_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                # Sort by frame number (extract numeric part)
                self.frames_list = sorted(files, key=self._extract_frame_number)
            else:
                self.frames_list = []

            # Reset current index if needed
            if self.current_index >= len(self.frames_list) and self.frames_list:
                self.current_index = len(self.frames_list) - 1
            elif not self.frames_list:
                self.current_index = 0

        except Exception as e:
            print(f"Error refreshing frames list: {e}")
            self.frames_list = []

    def set_frames_dir(self, frames_dir: str):
        """Switch the active source without mixing frame sequences."""
        target = os.path.abspath(frames_dir)
        if os.path.abspath(self.frames_dir) == target:
            self.refresh_frames_list()
            return
        self.frames_dir = target
        os.makedirs(self.frames_dir, exist_ok=True)
        self.current_index = 0
        self.loaded_frame = None
        self.loaded_photo = None
        self.refresh_frames_list()

    # Backwards-compatible aliases used by editor_screen
    def refresh_frame_list(self):
        self.refresh_frames_list()

    @property
    def frames(self) -> List[str]:
        return self.frames_list

    @property
    def current_frame_index(self) -> int:
        return self.current_index

    @current_frame_index.setter
    def current_frame_index(self, value: int):
        self.current_index = max(0, min(value, max(0, len(self.frames_list) - 1)))
        self.loaded_frame = None

    def display_current_frame(self) -> Optional[np.ndarray]:
        """Compatibility shim for older UI code"""
        return self.get_current_frame()

    def _extract_frame_number(self, filename: str) -> int:
        """Extract frame number from filename"""
        try:
            # Look for patterns like frame_0001.jpg, frame0001.jpg, 0001.jpg
            match = re.search(r'(\d+)', filename)
            if match:
                return int(match.group(1))
            return 0
        except:
            return 0

    def get_frame_count(self) -> int:
        """Get total number of frames"""
        return len(self.frames_list)

    def get_current_frame_info(self) -> dict:
        """Get information about current frame"""
        if not self.frames_list or self.current_index >= len(self.frames_list):
            return {}

        frame_path = os.path.join(self.frames_dir, self.frames_list[self.current_index])

        try:
            # Get image info
            with Image.open(frame_path) as img:
                return {
                    'filename': self.frames_list[self.current_index],
                    'path': frame_path,
                    'index': self.current_index,
                    'total': len(self.frames_list),
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'size': os.path.getsize(frame_path)
                }
        except Exception as e:
            print(f"Error getting frame info: {e}")
            return {}

    def load_frame(self, index: int) -> Optional[np.ndarray]:
        """Load frame at specific index"""
        if not self.frames_list or index < 0 or index >= len(self.frames_list):
            return None

        try:
            frame_path = os.path.join(self.frames_dir, self.frames_list[index])
            frame = cv2.imread(frame_path)

            if frame is not None:
                self.loaded_frame = frame
                self.current_index = index
                return frame

        except Exception as e:
            print(f"Error loading frame {index}: {e}")

        return None

    def get_current_frame(self) -> Optional[np.ndarray]:
        """Get current loaded frame"""
        if self.loaded_frame is None:
            self.load_frame(self.current_index)
        return self.loaded_frame

    def get_frame_as_photo(self, width: int, height: int) -> Optional[ImageTk.PhotoImage]:
        """Get current frame as PhotoImage for tkinter"""
        frame = self.get_current_frame()
        if frame is None:
            return None

        try:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Convert to PIL Image
            image = Image.fromarray(frame_rgb)

            # Calculate aspect ratio
            img_width, img_height = image.size
            aspect_ratio = img_width / img_height

            # Calculate new dimensions maintaining aspect ratio
            if width / height > aspect_ratio:
                new_height = height
                new_width = int(height * aspect_ratio)
            else:
                new_width = width
                new_height = int(width / aspect_ratio)

            # Resize image
            image_resized = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

            # Convert to PhotoImage
            photo = ImageTk.PhotoImage(image=image_resized)
            self.loaded_photo = photo

            return photo

        except Exception as e:
            print(f"Error converting frame to PhotoImage: {e}")
            return None

    def next_frame(self) -> bool:
        """Move to next frame"""
        if self.current_index < len(self.frames_list) - 1:
            self.current_index += 1
            self.loaded_frame = None  # Force reload
            return True
        return False

    def previous_frame(self) -> bool:
        """Move to previous frame"""
        if self.current_index > 0:
            self.current_index -= 1
            self.loaded_frame = None  # Force reload
            return True
        return False

    def go_to_frame(self, index: int) -> bool:
        """Go to specific frame index"""
        if 0 <= index < len(self.frames_list):
            self.current_index = index
            self.loaded_frame = None  # Force reload
            return True
        return False

    def delete_current_frame(self) -> bool:
        """Delete current frame"""
        if not self.frames_list or self.current_index >= len(self.frames_list):
            return False

        try:
            frame_path = os.path.join(self.frames_dir, self.frames_list[self.current_index])
            os.remove(frame_path)

            # Remove from list
            self.frames_list.pop(self.current_index)

            # Adjust current index if needed
            if self.current_index >= len(self.frames_list) and self.current_index > 0:
                self.current_index -= 1

            # Clear loaded frame
            self.loaded_frame = None
            self.loaded_photo = None

            return True

        except Exception as e:
            print(f"Error deleting frame: {e}")
            return False

    def delete_frames_range(self, start_index: int, end_index: int) -> bool:
        """Delete frames in range [start_index, end_index]"""
        if not self.frames_list:
            return False

        # Validate indices
        start_index = max(0, start_index)
        end_index = min(len(self.frames_list) - 1, end_index)

        if start_index > end_index:
            return False

        try:
            # Delete files
            for i in range(start_index, end_index + 1):
                if i < len(self.frames_list):
                    frame_path = os.path.join(self.frames_dir, self.frames_list[i])
                    if os.path.exists(frame_path):
                        os.remove(frame_path)

            # Remove from list
            del self.frames_list[start_index:end_index + 1]

            # Adjust current index
            if self.current_index >= len(self.frames_list) and self.current_index > 0:
                self.current_index = len(self.frames_list) - 1

            # Clear loaded frame
            self.loaded_frame = None
            self.loaded_photo = None

            return True

        except Exception as e:
            print(f"Error deleting frames range: {e}")
            return False

    def renumber_frames(self, prefix: str = 'frame', start_number: int = 1) -> bool:
        """Renumber all frames with sequential numbering"""
        if not self.frames_list:
            return True

        try:
            # Create temporary directory for renamed files
            temp_dir = os.path.join(self.frames_dir, 'temp_renumber')
            os.makedirs(temp_dir, exist_ok=True)

            # Rename all files to temporary names first
            temp_files = []
            for i, old_filename in enumerate(self.frames_list):
                old_path = os.path.join(self.frames_dir, old_filename)
                temp_name = f"temp_{i:06d}.jpg"
                temp_path = os.path.join(temp_dir, temp_name)

                if os.path.exists(old_path):
                    shutil.move(old_path, temp_path)
                    temp_files.append((temp_name, old_filename))

            # Now rename to final names
            self.frames_list.clear()
            for i, (temp_name, _) in enumerate(temp_files):
                temp_path = os.path.join(temp_dir, temp_name)
                new_name = f"{prefix}_{i + start_number:04d}.jpg"
                new_path = os.path.join(self.frames_dir, new_name)

                shutil.move(temp_path, new_path)
                self.frames_list.append(new_name)

            # Clean up temp directory
            os.rmdir(temp_dir)

            # Reset current index
            self.current_index = 0
            self.loaded_frame = None
            self.loaded_photo = None

            return True

        except Exception as e:
            print(f"Error renumbering frames: {e}")
            return False

    def duplicate_frame(self, index: Optional[int] = None) -> bool:
        """Duplicate frame at index (or current frame if None)"""
        if index is None:
            index = self.current_index

        if not self.frames_list or index < 0 or index >= len(self.frames_list):
            return False

        try:
            original_path = os.path.join(self.frames_dir, self.frames_list[index])

            # Generate new filename
            base_name = os.path.splitext(self.frames_list[index])[0]
            new_filename = f"{base_name}_copy.jpg"
            new_path = os.path.join(self.frames_dir, new_filename)

            # Copy file
            shutil.copy2(original_path, new_path)

            # Insert into list
            self.frames_list.insert(index + 1, new_filename)

            return True

        except Exception as e:
            print(f"Error duplicating frame: {e}")
            return False

    def get_frame_histogram(self, index: Optional[int] = None) -> Optional[np.ndarray]:
        """Get histogram for frame at index"""
        if index is None:
            index = self.current_index

        if not self.frames_list or index < 0 or index >= len(self.frames_list):
            return None

        try:
            frame_path = os.path.join(self.frames_dir, self.frames_list[index])
            frame = cv2.imread(frame_path)

            if frame is not None:
                # Calculate histogram for each channel
                hist_b = cv2.calcHist([frame], [0], None, [256], [0, 256])
                hist_g = cv2.calcHist([frame], [1], None, [256], [0, 256])
                hist_r = cv2.calcHist([frame], [2], None, [256], [0, 256])

                return np.stack([hist_b, hist_g, hist_r], axis=1)

        except Exception as e:
            print(f"Error calculating histogram: {e}")

        return None

    def get_frames_summary(self) -> dict:
        """Get summary of all frames"""
        if not self.frames_list:
            return {
                'total_frames': 0,
                'total_size_mb': 0,
                'average_size_mb': 0,
                'resolution': None
            }

        try:
            total_size = 0
            resolutions = []

            for filename in self.frames_list:
                frame_path = os.path.join(self.frames_dir, filename)
                if os.path.exists(frame_path):
                    total_size += os.path.getsize(frame_path)

                    # Get resolution from first frame
                    if not resolutions:
                        with Image.open(frame_path) as img:
                            resolutions.append((img.width, img.height))

            return {
                'total_frames': len(self.frames_list),
                'total_size_mb': total_size / (1024 * 1024),
                'average_size_mb': (total_size / len(self.frames_list)) / (1024 * 1024) if self.frames_list else 0,
                'resolution': resolutions[0] if resolutions else None
            }

        except Exception as e:
            print(f"Error getting frames summary: {e}")
            return {
                'total_frames': len(self.frames_list),
                'total_size_mb': 0,
                'average_size_mb': 0,
                'resolution': None
            }

    def cleanup_empty_directory(self):
        """Clean up if frames directory is empty"""
        try:
            if os.path.exists(self.frames_dir) and not os.listdir(self.frames_dir):
                os.rmdir(self.frames_dir)
        except:
            pass
