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


def test_focus_borders_are_limited_to_interactive_widgets(monkeypatch):
    options = []

    class FakeRoot:
        def configure(self, **_values):
            return None

        def option_add(self, pattern, value):
            options.append((pattern, value))

    class FakeStyle:
        configured = []
        mapped = []

        def __init__(self, _root):
            return None

        def configure(self, name, **values):
            self.configured.append((name, values))

        def map(self, name, **values):
            self.mapped.append((name, values))

    monkeypatch.setattr("gui.themes.dark_theme.ttk.Style", FakeStyle)

    DarkTheme.apply_accessibility(
        FakeRoot(), AccessibilityPreferences(large_focus=True)
    )

    patterns = {pattern for pattern, _value in options}
    assert "*highlightThickness" not in patterns
    assert "*takeFocus" not in patterns
    assert "*Button.highlightThickness" in patterns
    assert "*Radiobutton.takeFocus" in patterns
    assert not any("Label.highlightThickness" in pattern for pattern in patterns)
    popup_options = dict(options)
    assert popup_options["*TCombobox*Listbox.background"] == DarkTheme.COLORS["bg_tertiary"]
    assert popup_options["*TCombobox*Listbox.foreground"] == DarkTheme.COLORS["text_primary"]
    combo_config = next(
        values for name, values in FakeStyle.configured if name == "TCombobox"
    )
    assert combo_config["fieldbackground"] == DarkTheme.COLORS["bg_primary"]
    assert combo_config["foreground"] == DarkTheme.COLORS["text_primary"]
