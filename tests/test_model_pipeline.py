import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RESTORE_DIR = os.path.join(ROOT, "src", "lib", "modules", "frame", "restoration")
if RESTORE_DIR not in sys.path:
    sys.path.insert(0, RESTORE_DIR)

from model_pipeline import ModelPipeline


def _touch(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(b"")


def test_swinir_detection_by_folder(tmp_path):
    root = tmp_path / "models"
    weight_path = root / "SwinIR-main" / "weights" / "realSR_x4.pth"
    _touch(str(weight_path))

    mp = ModelPipeline([str(root)])
    assert "realSR_x4.pth" in mp.list_swinir_weights()


def test_restormer_detection_by_folder(tmp_path):
    root = tmp_path / "models"
    weight_path = root / "Restormer-main" / "weights" / "gaussian_denoise.pth"
    _touch(str(weight_path))

    mp = ModelPipeline([str(root)])
    assert "gaussian_denoise.pth" in mp.list_restormer_weights()


def test_swinir_task_inference_modes():
    task, scale, _noise = ModelPipeline._infer_swinir_task("001_classicalSR_swinir_x2.pth")
    assert task == "classical_sr"
    assert scale == 2

    task, scale, _noise = ModelPipeline._infer_swinir_task("002_lightweight_swinir_x4.pth")
    assert task == "lightweight_sr"
    assert scale == 4

    task, scale, _noise = ModelPipeline._infer_swinir_task("003_realSR_swinir_x4.pth")
    assert task == "real_sr"
    assert scale == 4


def test_swinir_sr_weight_filtering(tmp_path):
    root = tmp_path / "models"
    sr_weight = root / "SwinIR-main" / "weights" / "001_classicalSR_swinir_x2.pth"
    dn_weight = root / "SwinIR-main" / "weights" / "002_denoise_noise25_swinir.pth"
    _touch(str(sr_weight))
    _touch(str(dn_weight))

    mp = ModelPipeline([str(root)])
    sr_list = mp.list_swinir_sr_weights(scale=2)
    assert "001_classicalSR_swinir_x2.pth" in sr_list
    assert "002_denoise_noise25_swinir.pth" not in sr_list


def test_infer_scale_patterns():
    assert ModelPipeline._infer_scale_from_name("swinir_x2.pth") == 2
    assert ModelPipeline._infer_scale_from_name("SwinIR_scale4.pth") == 4
    assert ModelPipeline._infer_scale_from_name("SwinIR_4x.pth") == 4
