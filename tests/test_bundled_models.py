import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
RESTORATION_DIR = SRC_DIR / "lib" / "modules" / "frame" / "restoration"
for path in (SRC_DIR, RESTORATION_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core.model_registry import ModelRegistry
from model_pipeline import ModelPipeline


def test_bundled_unet_weights_match_manifest_and_load():
    weight_root = ROOT / "models" / "weights" / "unet_dust"
    manifest = json.loads((weight_root / "manifest.json").read_text(encoding="utf-8"))

    for record in manifest["weights"]:
        path = weight_root / record["name"]
        assert path.stat().st_size == record["size"]
        assert ModelRegistry.verify_weight(path, record["sha256"])

    pipeline = ModelPipeline([str(ROOT / "models")])
    assert pipeline._unet is not None
    assert Path(pipeline.get_weights_info()["unet"]).parent == weight_root
