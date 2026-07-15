import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESTORE_DIR = ROOT / "src" / "lib" / "modules" / "frame" / "restoration"
if str(RESTORE_DIR) not in sys.path:
    sys.path.insert(0, str(RESTORE_DIR))

from architecture_loader import ArchitectureLoader


def test_compact_architecture_is_preferred_over_legacy_repository(tmp_path):
    compact = tmp_path / "architectures" / "swinir" / "network_swinir.py"
    legacy = tmp_path / "SwinIR-main" / "SwinIR-main" / "models" / "network_swinir.py"
    compact.parent.mkdir(parents=True)
    legacy.parent.mkdir(parents=True)
    compact.write_text("class SwinIR: pass", encoding="utf-8")
    legacy.write_text("class SwinIR: pass", encoding="utf-8")

    assert ArchitectureLoader([str(tmp_path)]).find("swinir") == compact


def test_missing_architecture_is_reported_without_importing_repository(tmp_path):
    loader = ArchitectureLoader([str(tmp_path)])

    assert loader.find("restormer") is None
    try:
        loader.build_restormer()
    except FileNotFoundError as error:
        assert "restormer" in str(error)
    else:
        raise AssertionError("Expected a missing architecture error")


def test_legacy_repository_layout_is_not_loaded(tmp_path):
    legacy = tmp_path / "Restormer-main" / "Restormer-main" / "basicsr" / "models" / "archs"
    legacy.mkdir(parents=True)
    (legacy / "restormer_arch.py").write_text("class Restormer: pass", encoding="utf-8")

    assert ArchitectureLoader([str(tmp_path)]).find("restormer") is None
