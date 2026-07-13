#!/usr/bin/env python3
"""Benedito Digital GUI launcher with source-only diagnostics."""

import logging
import os
import sys


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(ROOT_DIR, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def console_message(message=""):
    """Write diagnostics only when a console stream exists."""
    if sys.stdout is not None:
        sys.stdout.write(f"{message}\n")
        sys.stdout.flush()


def report_startup_error(error):
    """Record startup failures only in a source diagnostic session."""
    if getattr(sys, "frozen", False):
        return
    logging.getLogger("benedito.startup").critical(
        "Falha durante a inicialização da interface",
        exc_info=(type(error), error, error.__traceback__),
    )


def main():
    from core.diagnostics import diagnostic_span, start_development_diagnostics

    diagnostic_session = start_development_diagnostics()
    logger = logging.getLogger("benedito.startup")
    if diagnostic_session and diagnostic_session.log_path:
        console_message(f"Log detalhado: {diagnostic_session.log_path}")

    try:
        with diagnostic_span("importar interface principal"):
            import tkinter as tk

            from core.app_info import get_app_info
            from gui.screens.welcome_screen import WelcomeScreen

        app_info = get_app_info()
        logger.info(
            "Aplicação: nome=%r versão=%s licença=%s",
            app_info.name,
            app_info.version,
            app_info.license,
        )

        console_message("Iniciando Benedito Digital GUI (Dark Theme)...")
        console_message("Seu Benedito da um jeito!")
        console_message("=" * 60)
        logger.info("Inicialização da GUI solicitada")

        with diagnostic_span("detectar aceleração gráfica"):
            try:
                import cv2

                cuda_devices = cv2.cuda.getCudaEnabledDeviceCount()
                opencl_available = bool(cv2.ocl.haveOpenCL())
                logger.info(
                    "Aceleração detectada: cuda_devices=%d opencl=%s",
                    cuda_devices,
                    opencl_available,
                )
                if cuda_devices > 0:
                    console_message(f"CUDA GPU detectada: {cuda_devices} dispositivos")
                elif opencl_available:
                    console_message("OpenCL detectado e habilitado")
                else:
                    console_message("Nenhuma aceleracao GPU detectada, usando CPU")
            except Exception:
                logger.exception("Falha ao verificar aceleração gráfica")
                console_message("Nao foi possivel verificar a disponibilidade de GPU")

        console_message("=" * 60)
        console_message("Interface Dark Theme carregada")
        console_message("=" * 60)

        with diagnostic_span("criar janela raiz Tkinter"):
            root = tk.Tk()
            root.title("Benedito Digital")
            root.geometry("1200x800")
            root.configure(bg="#1a1a1a")
            if diagnostic_session:
                diagnostic_session.install_tk_exception_handler(root)

        with diagnostic_span("construir tela inicial"):
            WelcomeScreen(root)

        logger.info("Entrando no loop principal do Tkinter")
        root.mainloop()
        logger.info("Loop principal do Tkinter encerrado normalmente")
        return 0
    except ImportError as error:
        report_startup_error(error)
        console_message(f"Erro de importacao: {error}")
        console_message("Certifique-se de que todas as dependencias estao instaladas:")
        console_message("pip install -r requirements.txt")
        return 1
    except Exception as error:
        report_startup_error(error)
        console_message(f"Erro ao iniciar a aplicacao: {error}")
        return 1
    finally:
        if diagnostic_session:
            diagnostic_session.close()


if __name__ == "__main__":
    raise SystemExit(main())
