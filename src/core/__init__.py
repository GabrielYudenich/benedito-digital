"""Core services for Benedito Digital."""

from .chunks import CheckpointMismatch, ChunkedFrameRunner
from .collaboration import CollaborationError, FolderCollaborationRemote, SyncResult
from .color_scopes import ColorScopeGenerator, ScopeStatistics
from .accessibility import AccessibilityPreferences, audit_palette, contrast_ratio
from .damage_analysis import DamageResult, FrameDamageAnalyzer
from .jobs import JobCancelled, JobContext, JobManager, JobSnapshot, JobState
from .film_analysis import (
    FilmPerforation,
    FilmPerforationDetector,
    FilmRegistration,
    PerforationDetection,
)
from .edit_timeline import EditTimeline, TimelineClip, TimelineTrack, TimelineTransition
from .keyframes import Keyframe, KeyframeCurve
from .updates import UpdateChecker, UpdateCheckError, UpdateInfo
from .model_registry import ModelRegistry, OptionalModelPackage, WeightRecord
from .paths import default_models_dir, default_projects_dir, resource_path, resource_root
from .selections import polygon_mask, rectangle_mask, selection_bounds

__all__ = [
    "CheckpointMismatch",
    "ChunkedFrameRunner",
    "CollaborationError",
    "FolderCollaborationRemote",
    "SyncResult",
    "ColorScopeGenerator",
    "ScopeStatistics",
    "AccessibilityPreferences",
    "audit_palette",
    "contrast_ratio",
    "DamageResult",
    "FrameDamageAnalyzer",
    "FilmPerforation",
    "FilmPerforationDetector",
    "FilmRegistration",
    "PerforationDetection",
    "EditTimeline",
    "TimelineClip",
    "TimelineTrack",
    "TimelineTransition",
    "Keyframe",
    "KeyframeCurve",
    "UpdateChecker",
    "UpdateCheckError",
    "UpdateInfo",
    "JobCancelled",
    "JobContext",
    "JobManager",
    "JobSnapshot",
    "JobState",
    "ModelRegistry",
    "OptionalModelPackage",
    "WeightRecord",
    "default_models_dir",
    "default_projects_dir",
    "resource_path",
    "resource_root",
    "polygon_mask",
    "rectangle_mask",
    "selection_bounds",
]
