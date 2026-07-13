"""
Project State Manager for Benedito Digital
Manages project state including current frame position and settings
"""

import json
import os
from datetime import datetime
from typing import Dict, Optional, Any

# Add path for logger
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..', '..', 'lib', 'utils'))

try:
    from logger import get_logger
except ImportError:
    # Fallback if logger not available
    class MockLogger:
        def info(self, msg): print(f"INFO: {msg}")
        def error(self, msg): print(f"ERROR: {msg}")
        def warning(self, msg): print(f"WARNING: {msg}")
        def debug(self, msg): pass
        def log_project_action(self, *args): pass
        def log_gpu_info(self, *args): pass

    def get_logger():
        return MockLogger()

logger = get_logger()

class ProjectStateManager:
    """Manages project state persistence and recovery"""

    def __init__(self, project_path: str):
        self.project_path = project_path
        self.logger = logger
        self.state_file = os.path.join(project_path, "metadata", "project_state.json")
        self.state = self.load_state()

    def load_state(self) -> Dict:
        """Load project state from file"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)
                self.logger.info(f"Loaded project state from {self.state_file}")
                return state
            else:
                # Create default state
                default_state = {
                    'current_frame': 0,
                    'total_frames': 0,
                    'video_path': None,
                    'last_position': 0.0,
                    'playback_speed': 1.0,
                    'zoom_level': 1.0,
                    'pan_offset': {'x': 0, 'y': 0},
                    'selected_frames': [],
                    'deleted_frames': [],
                    'processing_settings': {
                        'diff_thresh': 25,
                        'use_alignment': True,
                        'inpaint_if_needed': True,
                        'thin_line_boost': True,
                        'protect_edges': True
                    },
                    'ffmpeg_config': {
                        'qscale_v': 1,
                        'scale_filter': 'lanczos',
                        'width': 3840,
                        'height': 2160,
                        'fps': 60,
                        'output_pattern': 'frames/frame_%04d.png'
                    },
                    'ui_state': {
                        'selected_tab': 'video',
                        'timeline_zoom': 1.0,
                        'panel_sizes': {}
                    },
                    'last_saved': datetime.now().isoformat(),
                    'version': '2.0.0'
                }
                self.save_state(default_state)
                return default_state
        except Exception as e:
            self.logger.error(f"Error loading project state: {e}")
            return self.get_default_state()

    def get_default_state(self) -> Dict:
        """Get default project state"""
        return {
            'current_frame': 0,
            'total_frames': 0,
            'video_path': None,
            'last_position': 0.0,
            'playback_speed': 1.0,
            'zoom_level': 1.0,
            'pan_offset': {'x': 0, 'y': 0},
            'selected_frames': [],
            'deleted_frames': [],
            'processing_settings': {
                'diff_thresh': 25,
                'use_alignment': True,
                'inpaint_if_needed': True,
                'thin_line_boost': True,
                'protect_edges': True
            },
            'ffmpeg_config': {
                'qscale_v': 1,
                'scale_filter': 'lanczos',
                'width': 3840,
                'height': 2160,
                'fps': 60,
                'output_pattern': 'frames/frame_%04d.png'
            },
            'ui_state': {
                'selected_tab': 'video',
                'timeline_zoom': 1.0,
                'panel_sizes': {}
            },
            'last_saved': datetime.now().isoformat(),
            'version': '2.0.0'
        }

    def save_state(self, state: Optional[Dict] = None) -> bool:
        """Save project state to file"""
        try:
            if state is None:
                state = self.state

            # Update timestamp
            state['last_saved'] = datetime.now().isoformat()

            # Ensure directory exists
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)

            # Save to file
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)

            self.logger.info(f"Saved project state to {self.state_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error saving project state: {e}")
            return False

    def update_current_frame(self, frame_number: int, total_frames: int = None):
        """Update current frame position"""
        self.state['current_frame'] = frame_number
        if total_frames is not None:
            self.state['total_frames'] = total_frames
        self.save_state()
        self.logger.debug(f"Updated current frame to {frame_number}")

    def update_video_info(self, video_path: str, total_frames: int, fps: float = None):
        """Update video information"""
        self.state['video_path'] = video_path
        self.state['total_frames'] = total_frames
        if fps is not None:
            self.state['fps'] = fps
        self.save_state()
        self.logger.info(f"Updated video info: {video_path}, {total_frames} frames")

    def update_playback_position(self, position: float):
        """Update current playback position in seconds"""
        self.state['last_position'] = position
        self.save_state()

    def update_playback_speed(self, speed: float):
        """Update playback speed"""
        self.state['playback_speed'] = speed
        self.save_state()

    def update_zoom_level(self, zoom: float):
        """Update zoom level"""
        self.state['zoom_level'] = zoom
        self.save_state()

    def update_pan_offset(self, x: float, y: float):
        """Update pan offset"""
        self.state['pan_offset'] = {'x': x, 'y': y}
        self.save_state()

    def add_selected_frame(self, frame_number: int):
        """Add frame to selection"""
        if frame_number not in self.state['selected_frames']:
            self.state['selected_frames'].append(frame_number)
            self.save_state()

    def remove_selected_frame(self, frame_number: int):
        """Remove frame from selection"""
        if frame_number in self.state['selected_frames']:
            self.state['selected_frames'].remove(frame_number)
            self.save_state()

    def clear_selected_frames(self):
        """Clear frame selection"""
        self.state['selected_frames'] = []
        self.save_state()

    def add_deleted_frame(self, frame_number: int):
        """Add frame to deleted list"""
        if frame_number not in self.state['deleted_frames']:
            self.state['deleted_frames'].append(frame_number)
            self.save_state()

    def remove_deleted_frame(self, frame_number: int):
        """Remove frame from deleted list"""
        if frame_number in self.state['deleted_frames']:
            self.state['deleted_frames'].remove(frame_number)
            self.save_state()

    def update_processing_settings(self, settings: Dict):
        """Update processing settings"""
        self.state['processing_settings'].update(settings)
        self.save_state()

    def update_ffmpeg_config(self, config: Dict):
        """Update FFmpeg configuration"""
        self.state['ffmpeg_config'].update(config)
        self.save_state()

    def update_ui_state(self, ui_updates: Dict):
        """Update UI state"""
        self.state['ui_state'].update(ui_updates)
        self.save_state()

    def get_current_frame(self) -> int:
        """Get current frame number"""
        return self.state.get('current_frame', 0)

    def get_total_frames(self) -> int:
        """Get total frame count"""
        return self.state.get('total_frames', 0)

    def get_video_path(self) -> Optional[str]:
        """Get current video path"""
        return self.state.get('video_path')

    def get_last_position(self) -> float:
        """Get last playback position"""
        return self.state.get('last_position', 0.0)

    def get_playback_speed(self) -> float:
        """Get playback speed"""
        return self.state.get('playback_speed', 1.0)

    def get_zoom_level(self) -> float:
        """Get zoom level"""
        return self.state.get('zoom_level', 1.0)

    def get_pan_offset(self) -> Dict:
        """Get pan offset"""
        return self.state.get('pan_offset', {'x': 0, 'y': 0})

    def get_selected_frames(self) -> list:
        """Get selected frames list"""
        return self.state.get('selected_frames', [])

    def get_deleted_frames(self) -> list:
        """Get deleted frames list"""
        return self.state.get('deleted_frames', [])

    def get_processing_settings(self) -> Dict:
        """Get processing settings"""
        return self.state.get('processing_settings', {})

    def get_ffmpeg_config(self) -> Dict:
        """Get FFmpeg configuration"""
        return self.state.get('ffmpeg_config', {})

    def get_ui_state(self) -> Dict:
        """Get UI state"""
        return self.state.get('ui_state', {})

    def restore_to_frame(self, frame_number: int) -> bool:
        """Restore project to specific frame position"""
        try:
            if 0 <= frame_number <= self.get_total_frames():
                self.update_current_frame(frame_number)
                self.logger.info(f"Restored project to frame {frame_number}")
                return True
            else:
                self.logger.warning(f"Frame {frame_number} out of range")
                return False
        except Exception as e:
            self.logger.error(f"Error restoring to frame {frame_number}: {e}")
            return False

    def create_checkpoint(self, name: str) -> bool:
        """Create a checkpoint of current state"""
        try:
            checkpoint_dir = os.path.join(self.project_path, "checkpoints")
            os.makedirs(checkpoint_dir, exist_ok=True)

            checkpoint_file = os.path.join(checkpoint_dir, f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")

            with open(checkpoint_file, 'w') as f:
                json.dump(self.state, f, indent=2)

            self.logger.info(f"Created checkpoint: {checkpoint_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error creating checkpoint: {e}")
            return False

    def list_checkpoints(self) -> list:
        """List available checkpoints"""
        try:
            checkpoint_dir = os.path.join(self.project_path, "checkpoints")
            if not os.path.exists(checkpoint_dir):
                return []

            checkpoints = []
            for file in os.listdir(checkpoint_dir):
                if file.endswith('.json'):
                    checkpoints.append({
                        'name': file.replace('.json', ''),
                        'file': os.path.join(checkpoint_dir, file),
                        'modified': datetime.fromtimestamp(os.path.getmtime(os.path.join(checkpoint_dir, file))).isoformat()
                    })

            return sorted(checkpoints, key=lambda x: x['modified'], reverse=True)

        except Exception as e:
            self.logger.error(f"Error listing checkpoints: {e}")
            return []

    def restore_checkpoint(self, checkpoint_file: str) -> bool:
        """Restore state from checkpoint"""
        try:
            with open(checkpoint_file, 'r') as f:
                checkpoint_state = json.load(f)

            self.state = checkpoint_state
            self.save_state()

            self.logger.info(f"Restored from checkpoint: {checkpoint_file}")
            return True

        except Exception as e:
            self.logger.error(f"Error restoring checkpoint: {e}")
            return False

    def export_state(self, export_path: str) -> bool:
        """Export current state to file"""
        try:
            with open(export_path, 'w') as f:
                json.dump(self.state, f, indent=2)

            self.logger.info(f"Exported state to {export_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error exporting state: {e}")
            return False

    def import_state(self, import_path: str) -> bool:
        """Import state from file"""
        try:
            with open(import_path, 'r') as f:
                imported_state = json.load(f)

            # Validate state structure
            required_keys = ['current_frame', 'total_frames', 'version']
            if not all(key in imported_state for key in required_keys):
                self.logger.error("Invalid state file structure")
                return False

            self.state = imported_state
            self.save_state()

            self.logger.info(f"Imported state from {import_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error importing state: {e}")
            return False
