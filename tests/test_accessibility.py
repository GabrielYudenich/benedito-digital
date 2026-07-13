import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from core.accessibility import AccessibilityPreferences, audit_palette, contrast_ratio
from gui.themes.dark_theme import DarkTheme


def test_preferences_are_normalized_and_round_trip():
    preferences = AccessibilityPreferences.from_dict({"scale": 3, "high_contrast": True})
    assert preferences.scale == 1.5
    assert AccessibilityPreferences.from_dict(preferences.to_dict()) == preferences


def test_primary_theme_text_meets_wcag_contrast():
    ratio = contrast_ratio(DarkTheme.COLORS["text_primary"], DarkTheme.COLORS["bg_primary"])
    assert ratio >= 7.0
    audit = audit_palette([
        ("primary", DarkTheme.COLORS["text_primary"], DarkTheme.COLORS["bg_primary"]),
        ("secondary", DarkTheme.COLORS["text_secondary"], DarkTheme.COLORS["bg_secondary"]),
    ])
    assert all(item["passes"] for item in audit)
