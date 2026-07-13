# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path
from PyInstaller.building.datastruct import TOC


ROOT = Path(SPEC).resolve().parent.parent
SRC = ROOT / "src"
VENDOR_FFMPEG = ROOT / "vendor" / "ffmpeg"

pathex = [
    str(ROOT),
    str(SRC),
    str(SRC / "gui" / "screens"),
    str(SRC / "gui" / "modules"),
    str(SRC / "gui" / "dialogs"),
    str(SRC / "gui" / "themes"),
    str(SRC / "lib" / "utils"),
    str(SRC / "lib" / "modules" / "project"),
    str(SRC / "lib" / "modules" / "project" / "state"),
    str(SRC / "lib" / "modules" / "frame" / "mask"),
    str(SRC / "lib" / "modules" / "frame" / "restoration"),
    str(SRC / "lib" / "modules" / "video" / "renderer"),
]

datas = [
    (str(ROOT / "config.json"), "."),
    (str(ROOT / "LICENSE"), "."),
    (str(ROOT / "README.md"), "."),
    (str(ROOT / "README_TUTORIAL.md"), "."),
    (str(ROOT / "models" / "registry.json"), "models"),
    (str(ROOT / "models" / "THIRD_PARTY_NOTICES.md"), "models"),
    (str(ROOT / "models" / "MODELS_INDEX.md"), "models"),
    (str(ROOT / "models" / "architectures"), "models/architectures"),
    (str(ROOT / "models" / "weights" / "unet_dust"), "models/weights/unet_dust"),
    (str(ROOT / "packaging" / "ffmpeg-lock.json"), "licenses"),
]

binaries = []
vendor_bin = VENDOR_FFMPEG / "bin"
for path in sorted(vendor_bin.glob("*")):
    if path.name.lower() not in {"ffmpeg.exe", "ffprobe.exe"} and path.suffix.lower() != ".dll":
        continue
    if path.is_file():
        binaries.append((str(path), "ffmpeg/bin"))

for path in sorted((VENDOR_FFMPEG / "legal").glob("*")):
    if path.is_file():
        datas.append((str(path), "licenses/ffmpeg"))
provenance = VENDOR_FFMPEG / "provenance.json"
if provenance.is_file():
    datas.append((str(provenance), "licenses/ffmpeg"))

hiddenimports = [
    "gui.screens.editor_screen",
    "gui.screens.welcome_screen",
    "PIL._tkinter_finder",
    "cv2",
    "torch",
    "torchvision",
    "timm",
    "einops",
    "model_pipeline",
    "architecture_loader",
    "rrdbnet",
    "video_renderer",
]

analysis = Analysis(
    [str(ROOT / "run_gui.py"), str(ROOT / "benedito_cli.py")],
    pathex=pathex,
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(analysis.pure)
runtime_scripts = [entry for entry in analysis.scripts if entry[0].startswith("pyi_rth_")]
gui_entrypoints = [entry for entry in analysis.scripts if entry[0] == "run_gui"]
cli_entrypoints = [entry for entry in analysis.scripts if entry[0] == "benedito_cli"]
if len(gui_entrypoints) != 1 or len(cli_entrypoints) != 1:
    raise RuntimeError("PyInstaller entrypoints were not discovered uniquely")
gui_scripts = TOC(runtime_scripts + gui_entrypoints)
cli_scripts = TOC(runtime_scripts + cli_entrypoints)

exe = EXE(
    pyz,
    gui_scripts,
    [],
    exclude_binaries=True,
    name="Benedito Digital",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

cli_exe = EXE(
    pyz,
    cli_scripts,
    [],
    exclude_binaries=True,
    name="benedito",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collection = COLLECT(
    exe,
    cli_exe,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="BeneditoDigital",
)
