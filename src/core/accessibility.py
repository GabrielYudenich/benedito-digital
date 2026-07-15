"""Accessibility preferences and deterministic contrast diagnostics."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class AccessibilityPreferences:
    scale: float = 1.0
    high_contrast: bool = False
    reduced_motion: bool = False
    large_focus: bool = True

    def normalized(self):
        return AccessibilityPreferences(
            scale=max(0.9, min(1.5, float(self.scale))),
            high_contrast=bool(self.high_contrast),
            reduced_motion=bool(self.reduced_motion),
            large_focus=bool(self.large_focus),
        )

    def to_dict(self):
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, value):
        data = value if isinstance(value, dict) else {}
        return cls(
            scale=data.get("scale", data.get("interface_scale", 1.0)),
            high_contrast=data.get("high_contrast", False),
            reduced_motion=data.get("reduced_motion", False),
            large_focus=data.get("large_focus", True),
        ).normalized()


def contrast_ratio(first, second):
    bright = relative_luminance(first)
    dark = relative_luminance(second)
    lighter, darker = max(bright, dark), min(bright, dark)
    return (lighter + 0.05) / (darker + 0.05)


def relative_luminance(color):
    value = str(color).lstrip("#")
    if len(value) != 6:
        raise ValueError("Color must use #RRGGBB")
    channels = [int(value[index : index + 2], 16) / 255.0 for index in (0, 2, 4)]
    converted = [channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4 for channel in channels]
    return converted[0] * 0.2126 + converted[1] * 0.7152 + converted[2] * 0.0722


def audit_palette(pairs, minimum=4.5):
    return [
        {"name": name, "ratio": round(contrast_ratio(foreground, background), 3), "passes": contrast_ratio(foreground, background) >= minimum}
        for name, foreground, background in pairs
    ]
