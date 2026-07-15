import hashlib
import json
import os
import sys


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SRC_DIR = os.path.join(ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

from core.model_registry import ModelRegistry


def registry_file(tmp_path):
    path = tmp_path / "registry.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "families": {
                    family: {
                        "name": family,
                        "tasks": [],
                        "license": "test",
                        "source": "test",
                        "attribution": "test",
                    }
                    for family in ("swinir", "restormer", "unet_dust", "dncnn_kair", "bsrgan")
                },
            }
        ),
        encoding="utf-8",
    )
    return path


def test_discovers_and_classifies_native_weights(tmp_path):
    weights = tmp_path / "weights"
    weights.mkdir()
    (weights / "SwinIR_x4.pth").write_bytes(b"sr")
    (weights / "dncnn_25.pth").write_bytes(b"dn")
    registry = ModelRegistry(registry_file(tmp_path), [weights])

    records = registry.discover()

    assert [(record.family, record.task, record.scale) for record in records] == [
        ("dncnn_kair", "denoise", None),
        ("swinir", "super_resolution", 4),
    ]


def test_imports_weight_transactionally_with_checksum(tmp_path):
    source = tmp_path / "restormer_denoise.pth"
    source.write_bytes(b"model-weight")
    registry = ModelRegistry(registry_file(tmp_path), [])

    record = registry.import_weight(source, tmp_path / "native", "restormer")

    assert record.sha256 == hashlib.sha256(b"model-weight").hexdigest()
    assert ModelRegistry.verify_weight(record.path, record.sha256)


def test_official_registry_exposes_ltx_as_optional_not_bundled():
    registry = ModelRegistry(ROOT + "/models/registry.json", [])

    package = next(item for item in registry.optional_catalog() if item.id == "ltx-2.3")

    assert package.install_policy == "optional-after-install"
    assert package.status == "experimental-planned"
    assert "47" in package.minimum_download
    assert package.source == "https://github.com/Lightricks/LTX-2"
