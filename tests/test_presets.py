import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
UTILS_DIR = os.path.join(ROOT, "src", "lib", "utils")
if UTILS_DIR not in sys.path:
    sys.path.insert(0, UTILS_DIR)

from presets import get_global_preset_settings


def test_preset_cinema_defaults():
    cfg = get_global_preset_settings("Cinema")
    assert cfg["profile_label"] == "Qualidade"
    assert cfg["use_upscale"] is False
    assert cfg["upscale_scale"] == "Auto"


def test_preset_conservador_defaults():
    cfg = get_global_preset_settings("Conservador")
    assert cfg["profile_label"] == "Rapido"
    assert cfg["use_upscale"] is False
    assert cfg["upscale_scale"] == "Auto"


def test_preset_nitro_forces_x4():
    cfg = get_global_preset_settings("Nitro")
    assert cfg["profile_label"] == "Maximo"
    assert cfg["use_upscale"] is True
    assert cfg["upscale_scale"] == "x4"


def test_preset_unknown_falls_back_to_cinema():
    cfg = get_global_preset_settings("Qualquer")
    assert cfg["profile_label"] == "Qualidade"
