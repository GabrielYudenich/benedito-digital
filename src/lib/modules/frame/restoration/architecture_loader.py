"""Load only the model architecture files required by imported weights."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Iterable, Optional


class ArchitectureLoader:
    def __init__(self, roots: Iterable[str]):
        self.roots = [Path(root).resolve() for root in roots]

    def find(self, family: str) -> Optional[Path]:
        candidates = {
            "unet_dust": (
                Path("architectures/unet_dust/unet.py"),
            ),
            "swinir": (
                Path("architectures/swinir/network_swinir.py"),
            ),
            "restormer": (
                Path("architectures/restormer/restormer_arch.py"),
            ),
        }
        for root in self.roots:
            for relative_path in candidates.get(family, ()):
                path = root / relative_path
                if path.is_file():
                    return path
        return None

    def build_unet_dust(self, torch_module):
        module = self._load("unet_dust")
        model_class = getattr(module, "UNet", None)
        if model_class is None:
            raise RuntimeError("UNet architecture class is missing")
        return model_class(
            in_channels=3,
            wf=4,
            depth=4,
            n_classes=1,
            padding=True,
            up_mode="upconv",
            batch_norm=True,
        )

    def build_swinir(self, torch_module, weights_path: str, args):
        module = self._load("swinir")
        model_class = getattr(module, "SwinIR", None)
        if model_class is None:
            raise RuntimeError("SwinIR architecture class is missing")
        common = {
            "img_range": 1.0,
            "mlp_ratio": 2,
            "resi_connection": "1conv",
        }
        if args.task == "classical_sr":
            model = model_class(
                upscale=args.scale, in_chans=3, img_size=args.training_patch_size,
                window_size=8, depths=[6] * 6, embed_dim=180, num_heads=[6] * 6,
                upsampler="pixelshuffle", **common,
            )
            parameter_key = "params"
        elif args.task == "lightweight_sr":
            model = model_class(
                upscale=args.scale, in_chans=3, img_size=64, window_size=8,
                depths=[6] * 4, embed_dim=60, num_heads=[6] * 4,
                upsampler="pixelshuffledirect", **common,
            )
            parameter_key = "params"
        elif args.task == "real_sr":
            if args.large_model:
                model = model_class(
                    upscale=args.scale, in_chans=3, img_size=64, window_size=8,
                    depths=[6] * 9, embed_dim=240, num_heads=[8] * 9,
                    upsampler="nearest+conv", img_range=1.0, mlp_ratio=2,
                    resi_connection="3conv",
                )
            else:
                model = model_class(
                    upscale=args.scale, in_chans=3, img_size=64, window_size=8,
                    depths=[6] * 6, embed_dim=180, num_heads=[6] * 6,
                    upsampler="nearest+conv", **common,
                )
            parameter_key = "params_ema"
        elif args.task in {"gray_dn", "color_dn"}:
            model = model_class(
                upscale=1,
                in_chans=1 if args.task == "gray_dn" else 3,
                img_size=128,
                window_size=8,
                depths=[6] * 6,
                embed_dim=180,
                num_heads=[6] * 6,
                upsampler="",
                **common,
            )
            parameter_key = "params"
        elif args.task in {"jpeg_car", "color_jpeg_car"}:
            model = model_class(
                upscale=1,
                in_chans=1 if args.task == "jpeg_car" else 3,
                img_size=126,
                window_size=7,
                img_range=255.0,
                depths=[6] * 6,
                embed_dim=180,
                num_heads=[6] * 6,
                mlp_ratio=2,
                upsampler="",
                resi_connection="1conv",
            )
            parameter_key = "params"
        else:
            raise ValueError(f"Unsupported SwinIR task: {args.task}")
        checkpoint = torch_module.load(weights_path, map_location="cpu")
        state = checkpoint.get(parameter_key, checkpoint) if isinstance(checkpoint, dict) else checkpoint
        model.load_state_dict(state, strict=True)
        return model

    def build_restormer(self):
        module = self._load("restormer")
        model_class = getattr(module, "Restormer", None)
        if model_class is None:
            raise RuntimeError("Restormer architecture class is missing")
        return model_class(
            inp_channels=3,
            out_channels=3,
            dim=48,
            num_blocks=[4, 6, 6, 8],
            num_refinement_blocks=4,
            heads=[1, 2, 4, 8],
            ffn_expansion_factor=2.66,
            bias=False,
            LayerNorm_type="WithBias",
            dual_pixel_task=False,
        )

    def _load(self, family: str):
        path = self.find(family)
        if path is None:
            raise FileNotFoundError(f"Architecture not installed for {family}")
        module_name = f"benedito_arch_{family}_{abs(hash(str(path)))}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Could not load architecture: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
