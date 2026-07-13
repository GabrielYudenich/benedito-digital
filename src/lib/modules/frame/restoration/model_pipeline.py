"""
Optional ML model integration for frame restoration.
Uses external models if available, otherwise falls back gracefully.
"""

from dataclasses import dataclass
from typing import Optional, Dict, List, Sequence, Union
import os
import cv2
import numpy as np
import re

from lib.modules.frame.restoration.architecture_loader import ArchitectureLoader


@dataclass
class ModelInfo:
    name: str
    available: bool
    reason: str = ""


class ModelPipeline:
    def __init__(self, models_root: Union[Sequence[str], str]):
        if isinstance(models_root, (list, tuple)):
            roots = [os.path.abspath(p) for p in models_root if p]
        else:
            roots = [os.path.abspath(models_root)]
        self.models_roots = [p for p in roots if os.path.isdir(p)] or roots
        self.models_root = self.models_roots[0] if self.models_roots else os.path.abspath(".")
        self._architectures = ArchitectureLoader(self.models_roots)
        self._torch = None
        self._torchvision = None
        self._unet = None
        self._unet_weights = None
        self._dncnn = None
        self._dncnn_weights = None
        self._dncnn_candidates = []
        self._device = None
        self._unet_code_root = None
        self._sr_model = None
        self._sr_weights = None
        self._sr_scale = 1
        self._sr_name = ""
        self._sr_candidates = []
        self._swinir_model = None
        self._swinir_weights = None
        self._swinir_candidates = []
        self._swinir_task = None
        self._swinir_scale = 1
        self._swinir_noise = 15
        self._swinir_mode = None
        self._restormer_model = None
        self._restormer_weights = None
        self._restormer_candidates = []
        self._init_torch()
        self._discover_unet_dust()
        self._discover_dncnn_weights()
        self._discover_sr_weights()
        self._discover_swinir_weights()
        self._discover_restormer_weights()

    def get_weights_info(self) -> Dict[str, Optional[str]]:
        return {
            "unet": self._unet_weights,
            "dncnn": self._dncnn_weights,
            "sr": self._sr_weights,
            "swinir": self._swinir_weights,
            "restormer": self._restormer_weights,
        }

    def refresh(self):
        self._unet = None
        self._dncnn = None
        self._unet_weights = None
        self._dncnn_weights = None
        self._dncnn_candidates = []
        self._unet_code_root = None
        self._sr_model = None
        self._sr_weights = None
        self._sr_scale = 1
        self._sr_name = ""
        self._sr_candidates = []
        self._swinir_model = None
        self._swinir_weights = None
        self._swinir_candidates = []
        self._swinir_task = None
        self._swinir_scale = 1
        self._swinir_noise = 15
        self._swinir_mode = None
        self._restormer_model = None
        self._restormer_weights = None
        self._restormer_candidates = []
        self._init_torch()
        self._discover_unet_dust()
        self._discover_dncnn_weights()
        self._discover_sr_weights()
        self._discover_swinir_weights()
        self._discover_restormer_weights()

    def refresh_sr(self):
        self._sr_model = None
        self._sr_weights = None
        self._sr_scale = 1
        self._sr_name = ""
        self._sr_candidates = []
        self._discover_sr_weights()

    def refresh_dncnn(self):
        self._dncnn = None
        self._dncnn_weights = None
        self._dncnn_candidates = []
        self._discover_dncnn_weights()

    def refresh_swinir(self):
        self._swinir_model = None
        self._swinir_weights = None
        self._swinir_candidates = []
        self._swinir_task = None
        self._swinir_scale = 1
        self._swinir_noise = 15
        self._swinir_mode = None
        self._discover_swinir_weights()

    def refresh_restormer(self):
        self._restormer_model = None
        self._restormer_weights = None
        self._restormer_candidates = []
        self._discover_restormer_weights()

    def _init_torch(self):
        try:
            import torch
            import torchvision
            self._torch = torch
            self._torchvision = torchvision
            self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        except Exception:
            self._torch = None
            self._torchvision = None
            self._device = None

    def _iter_roots(self) -> List[str]:
        return [p for p in self.models_roots if p]

    def _iter_weight_files(self, root: str, max_depth: int = 4):
        if not root or not os.path.isdir(root):
            return
        base_depth = root.rstrip(os.sep).count(os.sep)
        for dirpath, dirnames, filenames in os.walk(root):
            depth = dirpath.rstrip(os.sep).count(os.sep) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            for filename in filenames:
                lower = filename.lower()
                if lower.endswith((".pth", ".pt")):
                    yield os.path.join(dirpath, filename)

    def _find_subdir(self, rel_path: str) -> Optional[str]:
        for root in self._iter_roots():
            candidate = os.path.join(root, rel_path)
            if os.path.isdir(candidate):
                return candidate
        return None

    def _find_repo_dir(self, name: str) -> Optional[str]:
        for root in self._iter_roots():
            candidate = os.path.join(root, name)
            if os.path.isdir(candidate):
                nested = os.path.join(candidate, name)
                if os.path.isdir(nested):
                    return nested
                return candidate
        return None

    def _discover_unet_dust(self):
        candidates = []
        for root in self._iter_roots():
            for path in self._iter_weight_files(root):
                lower = path.lower()
                if "dust" in lower or "unet" in lower:
                    candidates.append(path)
        if candidates:
            self._unet_weights = sorted(candidates)[-1]
        if self._unet_weights and self._torch is not None:
            try:
                self._unet = self._architectures.build_unet_dust(self._torch)
                state = self._torch.load(self._unet_weights, map_location=self._device)
                self._unet.load_state_dict(state, strict=True)
                self._unet.to(self._device)
                self._unet.eval()
            except Exception:
                self._unet = None

    def set_unet_weights(self, weights_path: str) -> bool:
        if not weights_path or not os.path.exists(weights_path):
            return False
        self._unet_weights = weights_path
        if self._torch is None:
            return False
        try:
            self._unet = self._architectures.build_unet_dust(self._torch)
            state = self._torch.load(weights_path, map_location=self._device)
            self._unet.load_state_dict(state, strict=True)
            self._unet.to(self._device)
            self._unet.eval()
            return True
        except Exception:
            self._unet = None
            return False

    def set_dncnn_weights(self, weights_path: str) -> bool:
        if not weights_path or not os.path.exists(weights_path):
            return False
        if weights_path.lower().endswith(".mat"):
            # Not supported directly (Matlab format)
            return False
        if self._torch is None:
            return False
        self._dncnn_weights = weights_path
        try:
            # Build DnCNN model (DnCNN-S, 17 layers)
            self._dncnn = self._build_dncnn(in_channels=3, num_layers=17, features=64)
            state = self._torch.load(weights_path, map_location=self._device)
            # Some checkpoints wrap state dict
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            self._dncnn.load_state_dict(state, strict=False)
            self._dncnn.to(self._device)
            self._dncnn.eval()
            return True
        except Exception:
            self._dncnn = None
            return False

    def available_models(self) -> List[ModelInfo]:
        models = [
            ModelInfo("None", True),
            ModelInfo("DnCNN (OpenCV)", True),
        ]
        if self._dncnn is not None:
            models.append(ModelInfo("DnCNN (PyTorch)", True))
        else:
            models.append(ModelInfo("DnCNN (PyTorch)", False, "Pesos .pth nao encontrados"))
        if self._unet is not None and self._torch is not None:
            models.append(ModelInfo("UNet Dust", True))
        else:
            reason = "Torch/weights nao encontrados"
            models.append(ModelInfo("UNet Dust", False, reason))
        if self._swinir_candidates and self._torch is not None and self._check_swinir_deps():
            models.append(ModelInfo("SwinIR (Denoise)", True))
        else:
            models.append(ModelInfo("SwinIR (Denoise)", False, "Pesos/deps SwinIR nao encontrados"))
        if self._restormer_candidates and self._torch is not None and self._check_restormer_deps():
            models.append(ModelInfo("Restormer (Denoise)", True))
        else:
            models.append(ModelInfo("Restormer (Denoise)", False, "Pesos/deps Restormer nao encontrados"))
        return models

    def list_dncnn_weights(self) -> List[str]:
        names = [os.path.basename(p) for p in self._dncnn_candidates]
        return sorted(list(dict.fromkeys(names)))

    def get_dncnn_weight_path(self, name: str) -> Optional[str]:
        for path in self._dncnn_candidates:
            if os.path.basename(path) == name:
                return path
        return None

    def list_sr_weights(self) -> List[str]:
        names = [os.path.basename(p) for p in self._sr_candidates]
        return sorted(list(dict.fromkeys(names)))

    def list_sr_weights_by_scale(self, scale: int) -> List[str]:
        names = []
        for path in self._sr_candidates:
            if self._infer_scale_from_name(os.path.basename(path)) == int(scale):
                names.append(os.path.basename(path))
        return sorted(list(dict.fromkeys(names)))

    def list_swinir_weights(self) -> List[str]:
        names = [os.path.basename(p) for p in self._swinir_candidates]
        return sorted(list(dict.fromkeys(names)))

    def list_swinir_sr_weights(self, scale: Optional[int] = None) -> List[str]:
        names = []
        for path in self._swinir_candidates:
            name = os.path.basename(path)
            task, sc, _noise = self._infer_swinir_task(name)
            if task in ("real_sr", "classical_sr", "lightweight_sr") and sc > 1:
                if scale is None or sc == int(scale):
                    names.append(name)
        return sorted(list(dict.fromkeys(names)))

    def list_swinir_denoise_weights(self) -> List[str]:
        names = []
        for path in self._swinir_candidates:
            name = os.path.basename(path)
            task, _sc, _noise = self._infer_swinir_task(name)
            if task in ("gray_dn", "color_dn", "jpeg_car"):
                names.append(name)
        return sorted(list(dict.fromkeys(names)))

    def get_swinir_weight_path(self, name: str) -> Optional[str]:
        for path in self._swinir_candidates:
            if os.path.basename(path) == name:
                return path
        return None

    def list_restormer_weights(self) -> List[str]:
        names = [os.path.basename(p) for p in self._restormer_candidates]
        return sorted(list(dict.fromkeys(names)))

    def get_restormer_weight_path(self, name: str) -> Optional[str]:
        for path in self._restormer_candidates:
            if os.path.basename(path) == name:
                return path
        return None

    def get_sr_weight_path(self, name: str) -> Optional[str]:
        for path in self._sr_candidates:
            if os.path.basename(path) == name:
                return path
        return None

    def get_sr_info(self) -> Dict[str, Optional[str]]:
        return {
            "name": self._sr_name,
            "scale": self._sr_scale,
            "path": self._sr_weights,
        }

    def get_swinir_info(self) -> Dict[str, Optional[str]]:
        name = ""
        if self._swinir_weights:
            name = os.path.basename(self._swinir_weights)
        return {
            "name": name,
            "scale": self._swinir_scale,
            "task": self._swinir_task,
            "mode": self._swinir_mode,
            "path": self._swinir_weights,
        }

    def ensure_swinir(self) -> bool:
        if self._swinir_model is not None:
            return True
        if not self._swinir_candidates:
            return False
        return self.set_swinir_weights(self._swinir_candidates[0])

    def ensure_swinir_sr(self, scale: Optional[int] = None) -> bool:
        if self._swinir_model is not None and self._swinir_mode == "sr":
            if scale is None or int(scale) == int(self._swinir_scale):
                return True
        candidates = self.list_swinir_sr_weights(scale=scale)
        if not candidates:
            return False
        path = self.get_swinir_weight_path(candidates[0])
        if path:
            return self.set_swinir_weights(path)
        return False

    def ensure_restormer(self) -> bool:
        if self._restormer_model is not None:
            return True
        if not self._restormer_candidates:
            return False
        return self.set_restormer_weights(self._restormer_candidates[0])

    def auto_select_sr(self, scale: Optional[int] = None) -> bool:
        if not self._sr_candidates:
            return False
        best = None
        best_score = -1
        for path in self._sr_candidates:
            score = 0
            name = os.path.basename(path).lower()
            if scale is not None and self._infer_scale_from_name(name) == int(scale):
                score += 10
            if "bsrgan" in name:
                score += 6
            if "esrgan" in name:
                score += 4
            if "rrdb" in name:
                score += 2
            if score > best_score:
                best_score = score
                best = path
        if best:
            return self.set_sr_weights(best)
        return False

    def auto_select_swinir_sr(self, scale: Optional[int] = None) -> bool:
        candidates = self.list_swinir_sr_weights(scale=scale)
        if not candidates:
            return False
        # prefer real_sr then classical then lightweight
        best = None
        best_score = -1
        for name in candidates:
            score = 0
            lower = name.lower()
            if "real" in lower or "bsrgan" in lower:
                score += 4
            if "classical" in lower:
                score += 3
            if "lightweight" in lower:
                score += 2
            if score > best_score:
                best_score = score
                best = name
        if best:
            path = self.get_swinir_weight_path(best)
            if path:
                return self.set_swinir_weights(path)
        return False

    def _check_swinir_deps(self) -> bool:
        try:
            import timm  # noqa: F401
            return True
        except Exception:
            return False

    def _check_restormer_deps(self) -> bool:
        try:
            from einops import rearrange  # noqa: F401
            return True
        except Exception:
            return False

    def denoise_opencv(self, bgr: np.ndarray) -> np.ndarray:
        try:
            return cv2.fastNlMeansDenoisingColored(bgr, None, 10, 10, 7, 21)
        except Exception:
            return bgr

    def denoise_dncnn(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        if self._dncnn is None or self._torch is None:
            return None
        try:
            img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
            tensor = self._torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self._device)
            with self._torch.no_grad():
                residual = self._dncnn(tensor)
                denoised = tensor - residual
            out = denoised.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
            out = (out * 255.0).astype(np.uint8)
            out = cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
            return out
        except Exception:
            return None

    def _build_dncnn(self, in_channels=3, num_layers=17, features=64):
        # DnCNN-S architecture: Conv+ReLU, (Conv+BN+ReLU)x(n-2), Conv
        import torch.nn as nn
        layers = []
        layers.append(nn.Conv2d(in_channels, features, kernel_size=3, padding=1, bias=True))
        layers.append(nn.ReLU(inplace=True))
        for _ in range(num_layers - 2):
            layers.append(nn.Conv2d(features, features, kernel_size=3, padding=1, bias=False))
            layers.append(nn.BatchNorm2d(features))
            layers.append(nn.ReLU(inplace=True))
        layers.append(nn.Conv2d(features, in_channels, kernel_size=3, padding=1, bias=False))
        return nn.Sequential(*layers)

    def predict_dust_mask_unet(self, bgr: np.ndarray, threshold: float = 0.5) -> Optional[np.ndarray]:
        if self._unet is None or self._torch is None or self._torchvision is None:
            return None

        try:
            # Convert to tensor
            img = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            tensor = self._torchvision.transforms.ToTensor()(img).unsqueeze(0).to(self._device)
            with self._torch.no_grad():
                pred = self._unet(tensor).detach().cpu().numpy()[0, 0]
            mask = (pred > threshold).astype(np.uint8) * 255
            return mask
        except Exception:
            return None

    def set_sr_weights(self, weights_path: str) -> bool:
        if not weights_path or not os.path.exists(weights_path):
            return False
        if self._torch is None:
            return False
        try:
            module_dir = os.path.dirname(__file__)
            if module_dir not in os.sys.path:
                os.sys.path.insert(0, module_dir)
            from rrdbnet import RRDBNet
        except Exception:
            return False
        try:
            state = self._torch.load(weights_path, map_location=self._device)
            if isinstance(state, dict) and "params" in state:
                state = state["params"]
            if isinstance(state, dict) and "state_dict" in state:
                state = state["state_dict"]
            if not isinstance(state, dict):
                return False

            state = self._sanitize_state_dict(state)
            nf, nb, gc = self._infer_rrdb_params(state)
            scale = self._infer_scale_from_name(os.path.basename(weights_path))

            model = RRDBNet(in_nc=3, out_nc=3, nf=nf, nb=nb, gc=gc, scale=scale)
            model.load_state_dict(state, strict=False)
            model.to(self._device)
            model.eval()

            self._sr_model = model
            self._sr_weights = weights_path
            self._sr_scale = scale
            self._sr_name = os.path.basename(weights_path)
            return True
        except Exception:
            self._sr_model = None
            self._sr_weights = None
            self._sr_scale = 1
            self._sr_name = ""
            return False

    def set_swinir_weights(self, weights_path: str) -> bool:
        if not weights_path or not os.path.exists(weights_path):
            return False
        if self._torch is None:
            return False
        if not self._check_swinir_deps():
            return False
        try:
            args = self._build_swinir_args(weights_path)
            model = self._architectures.build_swinir(self._torch, weights_path, args)
            model.to(self._device)
            model.eval()
            self._swinir_model = model
            self._swinir_weights = weights_path
            self._swinir_task = args.task
            self._swinir_scale = args.scale
            self._swinir_noise = args.noise
            self._swinir_mode = "sr" if args.task in ("real_sr", "classical_sr", "lightweight_sr") else "denoise"
            return True
        except Exception:
            self._swinir_model = None
            return False

    def set_restormer_weights(self, weights_path: str) -> bool:
        if not weights_path or not os.path.exists(weights_path):
            return False
        if self._torch is None:
            return False
        if not self._check_restormer_deps():
            return False
        try:
            model = self._architectures.build_restormer()
            checkpoint = self._torch.load(weights_path, map_location=self._device)
            if isinstance(checkpoint, dict) and "params" in checkpoint:
                checkpoint = checkpoint["params"]
            model.load_state_dict(checkpoint, strict=False)
            model.to(self._device)
            model.eval()
            self._restormer_model = model
            self._restormer_weights = weights_path
            return True
        except Exception:
            self._restormer_model = None
            return False

    def upscale_rrdb(self, bgr: np.ndarray, tile: int = 0, tile_overlap: int = 20) -> Optional[np.ndarray]:
        if self._sr_model is None or self._torch is None:
            return None
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            scale = int(self._sr_scale or 1)
            if tile <= 0 or (h <= tile and w <= tile):
                out = self._sr_forward(rgb)
                return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

            tile = int(max(64, tile))
            overlap = int(max(0, tile_overlap))
            stride = tile - overlap
            out_h, out_w = h * scale, w * scale
            out = np.zeros((out_h, out_w, 3), dtype=np.float32)
            weight = np.zeros((out_h, out_w, 3), dtype=np.float32)

            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    y1 = min(y + tile, h)
                    x1 = min(x + tile, w)
                    tile_rgb = rgb[y:y1, x:x1, :]
                    out_tile = self._sr_forward(tile_rgb).astype(np.float32)
                    oy, ox = y * scale, x * scale
                    oy1, ox1 = oy + out_tile.shape[0], ox + out_tile.shape[1]
                    out[oy:oy1, ox:ox1, :] += out_tile
                    weight[oy:oy1, ox:ox1, :] += 1.0

            out = out / np.maximum(weight, 1e-6)
            out = np.clip(out, 0, 255).astype(np.uint8)
            return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def _sr_forward(self, rgb: np.ndarray) -> np.ndarray:
        img = rgb.astype(np.float32) / 255.0
        tensor = self._torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self._device)
        with self._torch.no_grad():
            out = self._sr_model(tensor)
        out = out.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
        out = (out * 255.0).astype(np.uint8)
        return out

    def denoise_swinir(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        if self._swinir_model is None and not self.ensure_swinir():
            return None
        if self._swinir_mode == "sr":
            return None
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = rgb.astype(np.float32) / 255.0
            tensor = self._torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self._device)
            window = 8
            _, _, h, w = tensor.shape
            pad_h = (window - h % window) % window
            pad_w = (window - w % window) % window
            if pad_h or pad_w:
                tensor = self._torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
            with self._torch.no_grad():
                out = self._swinir_model(tensor)
            out = out[:, :, :h, :w]
            out = out.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
            out = (out * 255.0).astype(np.uint8)
            return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def upscale_swinir(self, bgr: np.ndarray, tile: int = 0, tile_overlap: int = 20) -> Optional[np.ndarray]:
        if not self.ensure_swinir_sr():
            return None
        if self._swinir_mode != "sr":
            return None
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            h, w = rgb.shape[:2]
            scale = int(self._swinir_scale or 1)
            if tile <= 0 or (h <= tile and w <= tile):
                out = self._swinir_forward(rgb)
                return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)

            tile = int(max(64, tile))
            overlap = int(max(0, tile_overlap))
            stride = tile - overlap
            out_h, out_w = h * scale, w * scale
            out = np.zeros((out_h, out_w, 3), dtype=np.float32)
            weight = np.zeros((out_h, out_w, 3), dtype=np.float32)

            for y in range(0, h, stride):
                for x in range(0, w, stride):
                    y1 = min(y + tile, h)
                    x1 = min(x + tile, w)
                    tile_rgb = rgb[y:y1, x:x1, :]
                    out_tile = self._swinir_forward(tile_rgb).astype(np.float32)
                    oy, ox = y * scale, x * scale
                    oy1, ox1 = oy + out_tile.shape[0], ox + out_tile.shape[1]
                    out[oy:oy1, ox:ox1, :] += out_tile
                    weight[oy:oy1, ox:ox1, :] += 1.0

            out = out / np.maximum(weight, 1e-6)
            out = np.clip(out, 0, 255).astype(np.uint8)
            return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    def _swinir_forward(self, rgb: np.ndarray) -> np.ndarray:
        img = rgb.astype(np.float32) / 255.0
        tensor = self._torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self._device)
        window = 8
        _, _, h, w = tensor.shape
        pad_h = (window - h % window) % window
        pad_w = (window - w % window) % window
        if pad_h or pad_w:
            tensor = self._torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
        with self._torch.no_grad():
            out = self._swinir_model(tensor)
        scale = int(self._swinir_scale or 1)
        out = out[:, :, :h * scale, :w * scale]
        out = out.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
        out = (out * 255.0).astype(np.uint8)
        return out

    def denoise_restormer(self, bgr: np.ndarray) -> Optional[np.ndarray]:
        if self._restormer_model is None and not self.ensure_restormer():
            return None
        try:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = rgb.astype(np.float32) / 255.0
            tensor = self._torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).to(self._device)
            _, _, h, w = tensor.shape
            pad_h = (8 - h % 8) % 8
            pad_w = (8 - w % 8) % 8
            if pad_h or pad_w:
                tensor = self._torch.nn.functional.pad(tensor, (0, pad_w, 0, pad_h), mode="reflect")
            with self._torch.no_grad():
                out = self._restormer_model(tensor)
            out = out[:, :, :h, :w]
            out = out.squeeze(0).permute(1, 2, 0).clamp(0, 1).cpu().numpy()
            out = (out * 255.0).astype(np.uint8)
            return cv2.cvtColor(out, cv2.COLOR_RGB2BGR)
        except Exception:
            return None

    @staticmethod
    def _infer_scale_from_name(name: str) -> int:
        lower = name.lower()
        match = re.search(r"x(\d)", lower)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass
        match = re.search(r"scale(\d)", lower)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass
        match = re.search(r"(\d)x", lower)
        if match:
            try:
                return int(match.group(1))
            except Exception:
                pass
        return 4

    @staticmethod
    def _infer_swinir_task(name: str) -> tuple:
        lower = name.lower()
        def _infer_noise():
            match = re.search(r"(?:noise|n)(15|25|50)", lower)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    return 15
            return 15

        if "jpeg" in lower or "car" in lower:
            return ("jpeg_car", 1, 40)
        if "gray" in lower and ("noise" in lower or "dn" in lower):
            return ("gray_dn", 1, _infer_noise())
        if "noise" in lower or "dn" in lower or "denoise" in lower:
            return ("color_dn", 1, _infer_noise())

        scale = ModelPipeline._infer_scale_from_name(lower)
        task = "real_sr"
        if "classical" in lower or "bicubic" in lower or "bic" in lower:
            task = "classical_sr"
        if "lightweight" in lower or "lw" in lower or "light" in lower:
            task = "lightweight_sr"
        if "real" in lower and "sr" in lower:
            task = "real_sr"
        return (task, scale, 15)

    def _build_swinir_args(self, weights_path: str):
        class Args:
            pass
        args = Args()
        task, scale, noise = self._infer_swinir_task(os.path.basename(weights_path))
        args.task = task
        args.scale = scale
        args.noise = noise
        args.jpeg = 40
        args.training_patch_size = 128
        args.large_model = False
        args.model_path = weights_path
        args.folder_lq = None
        args.folder_gt = None
        return args

    @staticmethod
    def _infer_rrdb_params(state: dict) -> tuple:
        nf = 64
        gc = 32
        nb = 23
        try:
            w = state.get("conv_first.weight")
            if w is not None:
                nf = int(w.shape[0])
            w2 = state.get("body.0.rdb1.conv1.weight")
            if w2 is not None:
                gc = int(w2.shape[0])
            indices = []
            for k in state.keys():
                if k.startswith("body."):
                    parts = k.split(".")
                    if len(parts) > 1 and parts[1].isdigit():
                        indices.append(int(parts[1]))
            if indices:
                nb = max(indices) + 1
        except Exception:
            pass
        return nf, nb, gc

    @staticmethod
    def _sanitize_state_dict(state: dict) -> dict:
        new_state = {}
        for k, v in state.items():
            nk = k
            for prefix in ("module.", "netG.", "model."):
                if nk.startswith(prefix):
                    nk = nk[len(prefix):]
            new_state[nk] = v
        return new_state

    def _discover_sr_weights(self):
        keywords = ("bsrgan", "esrgan", "rrdb", "realesrgan", "real-esrgan")
        candidates = []
        for root in self._iter_roots():
            try:
                for path in self._iter_weight_files(root):
                    lower = os.path.basename(path).lower()
                    if any(k in lower for k in keywords):
                        candidates.append(path)
            except Exception:
                continue
        self._sr_candidates = candidates
        # auto pick candidate if available
        if candidates and self._sr_weights is None:
            self.auto_select_sr()

    def _discover_dncnn_weights(self):
        if self._torch is None:
            return
        candidates = []
        for root in self._iter_roots():
            try:
                for path in self._iter_weight_files(root):
                    lower = os.path.basename(path).lower()
                    if "dncnn" in lower:
                        candidates.append(path)
            except Exception:
                continue
        if not candidates:
            return
        self._dncnn_candidates = candidates[:]
        preferred = ["dncnn_25", "dncnn3", "dncnn_15", "dncnn_50"]
        for pref in preferred:
            for path in candidates:
                if pref in os.path.basename(path).lower():
                    if self.set_dncnn_weights(path):
                        return
        # fallback: most recent
        candidates.sort(key=lambda p: os.path.getmtime(p))
        for path in reversed(candidates):
            if self.set_dncnn_weights(path):
                return

    def _discover_swinir_weights(self):
        candidates = []
        keywords = ("swinir", "swin2sr")
        for root in self._iter_roots():
            try:
                for path in self._iter_weight_files(root):
                    lower = path.lower()
                    if any(k in lower for k in keywords):
                        candidates.append(path)
            except Exception:
                continue
        self._swinir_candidates = candidates

    def _discover_restormer_weights(self):
        candidates = []
        keywords = ("restormer",)
        for root in self._iter_roots():
            try:
                for path in self._iter_weight_files(root):
                    lower = path.lower()
                    if any(k in lower for k in keywords):
                        candidates.append(path)
            except Exception:
                continue
        self._restormer_candidates = candidates
