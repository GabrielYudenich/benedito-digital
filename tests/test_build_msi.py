import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("build_msi", ROOT / "scripts" / "build_msi.py")
build_msi = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build_msi)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1", "1.0.0"), ("1.2", "1.2.0"), ("1.2.3", "1.2.3"), ("0.0.1", "0.0.1")],
)
def test_normalize_msi_version(value, expected):
    assert build_msi.normalize_msi_version(value) == expected


@pytest.mark.parametrize("value", ["", "1.2.3.4", "v1.0", "256.0.0", "1.256.0", "1.0.65536"])
def test_invalid_msi_versions_are_rejected(value):
    with pytest.raises(ValueError):
        build_msi.normalize_msi_version(value)


def test_component_guids_are_stable_and_distinct():
    first = build_msi.deterministic_guid("component", "bin")
    second = build_msi.deterministic_guid("component", "bin")
    other = build_msi.deterministic_guid("component", "models")

    assert first == second
    assert first != other
    assert first.startswith("{") and first.endswith("}")


@pytest.mark.skipif(build_msi.os.name != "nt", reason="Windows Installer is Windows-only")
def test_builds_minimal_msi(tmp_path):
    source = tmp_path / "app"
    (source / "empty").mkdir(parents=True)
    (source / "assets").mkdir()
    (source / "Benedito Digital.exe").write_bytes(b"fixture")
    (source / "assets" / "sample.txt").write_text("sample", encoding="utf-8")

    output = build_msi.build_msi(source, tmp_path / "benedito.msi", "1.0")

    assert output.is_file()
    assert output.stat().st_size > 0
