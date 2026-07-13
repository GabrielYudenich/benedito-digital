"""
GUI Modules Package
Contains modular components for Benedito Digital GUI
"""

__version__ = "1.0.0"
__author__ = "Benedito Digital Team"

from .video_player import VideoPlayer
from .video_processor import VideoProcessor
from .frame_manager import FrameManager
from .project_manager_gui import ProjectManagerGUI

__all__ = [
    'VideoPlayer',
    'VideoProcessor',
    'FrameManager',
    'ProjectManagerGUI'
]
