"""Print installation diagnostics without modifying the computer."""

import json
import platform
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.paths import executable_path


def main():
    checks = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "ffmpeg": executable_path("ffmpeg"),
        "ffprobe": executable_path("ffprobe"),
        "tkinter": _available("tkinter"),
        "opencv": _available("cv2"),
        "torch": _available("torch"),
        "cuda": _cuda_status(),
    }
    print(json.dumps(checks, indent=2, ensure_ascii=False))
    required = checks["ffmpeg"] and checks["ffprobe"] and checks["tkinter"] and checks["opencv"]
    return 0 if required else 1


def _available(module_name):
    try:
        __import__(module_name)
        return True
    except Exception:
        return False


def _cuda_status():
    try:
        import torch

        return {
            "available": torch.cuda.is_available(),
            "devices": torch.cuda.device_count(),
        }
    except Exception:
        return {"available": False, "devices": 0}


if __name__ == "__main__":
    raise SystemExit(main())
