#!/usr/bin/env python3
"""
Benedito Digital - GUI Launcher (Dark Theme Default)
Execute este arquivo para iniciar a interface grafica do Benedito Digital.
"""

import sys
import os
import traceback
from datetime import datetime, timezone
from pathlib import Path


def console_message(message=""):
    """Write diagnostics only when a console stream exists."""
    if sys.stdout is not None:
        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()


def report_startup_error(error):
    """Persist startup failures when the windowed executable has no console."""
    local_data = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or os.getcwd()
    log_directory = Path(local_data) / "Benedito Digital" / "logs"
    try:
        log_directory.mkdir(parents=True, exist_ok=True)
        log_path = log_directory / "startup.log"
        with log_path.open("a", encoding="utf-8") as log_file:
            timestamp = datetime.now(timezone.utc).isoformat()
            log_file.write(f"[{timestamp}] {type(error).__name__}: {error}\n")
            log_file.write(traceback.format_exc())
            log_file.write("\n")
    except OSError:
        pass

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

try:
    import tkinter as tk
    from gui.screens.welcome_screen import WelcomeScreen

    if __name__ == "__main__":
        console_message("Iniciando Benedito Digital GUI (Dark Theme)...")
        console_message("Seu Benedito da um jeito!")
        console_message("=" * 60)

        # Check GPU availability
        try:
            import cv2
            if cv2.cuda.getCudaEnabledDeviceCount() > 0:
                console_message(f"CUDA GPU detectada: {cv2.cuda.getCudaEnabledDeviceCount()} dispositivos")
            elif cv2.ocl.haveOpenCL():
                console_message("OpenCL detectado e habilitado")
            else:
                console_message("Nenhuma aceleracao GPU detectada, usando CPU")
        except Exception:
            console_message("Nao foi possivel verificar a disponibilidade de GPU")

        console_message("=" * 60)
        console_message("Interface Dark Theme carregada")
        console_message("=" * 60)

        root = tk.Tk()
        root.title("Benedito Digital")
        root.geometry("1200x800")
        root.configure(bg="#1a1a1a")
        app = WelcomeScreen(root)
        root.mainloop()

except ImportError as e:
    report_startup_error(e)
    console_message(f"Erro de importacao: {e}")
    console_message("Certifique-se de que todas as dependencias estao instaladas:")
    console_message("pip install -r requirements.txt")
    console_message("\nDependencias adicionais para GPU:")
    console_message("- NVIDIA: CUDA Toolkit e cuDNN")
    console_message("- AMD: AMD ROCm")
    console_message("- Intel: Intel OpenCL SDK")
    sys.exit(1)
except Exception as e:
    report_startup_error(e)
    console_message(f"Erro ao iniciar a aplicacao: {e}")
    sys.exit(1)
