"""
Logging System for Benedito Digital
Centralized logging with file output and console display
"""

import logging
import os
from datetime import datetime
from typing import Optional

class BeneditoLogger:
    """Centralized logging system"""

    def __init__(self, name: str = "BeneditoDigital", log_dir: str = "logs"):
        self.name = name
        self.log_dir = log_dir
        self.logger = None
        self.setup_logger()

    def setup_logger(self):
        """Setup logger with file and console handlers"""
        # Create logs directory if it doesn't exist
        os.makedirs(self.log_dir, exist_ok=True)

        # Create logger
        self.logger = logging.getLogger(self.name)
        self.logger.setLevel(logging.DEBUG)

        # Replace existing handlers without leaking their open file descriptors.
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            handler.close()

        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )

        # File handler (detailed logs)
        log_filename = f"{self.name}_{datetime.now().strftime('%Y%m%d')}.log"
        file_handler = logging.FileHandler(
            os.path.join(self.log_dir, log_filename),
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)

        # Console handler (important messages only)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)

        # Add handlers to logger
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

    def debug(self, message: str):
        """Log debug message"""
        self.logger.debug(message)

    def info(self, message: str):
        """Log info message"""
        self.logger.info(message)

    def warning(self, message: str):
        """Log warning message"""
        self.logger.warning(message)

    def error(self, message: str):
        """Log error message"""
        self.logger.error(message)

    def critical(self, message: str):
        """Log critical message"""
        self.logger.critical(message)

    def log_gpu_info(self, gpu_info: dict):
        """Log GPU information"""
        self.info("=== GPU Information ===")
        for key, value in gpu_info.items():
            self.info(f"{key}: {value}")
        self.info("=====================")

    def log_project_action(self, action: str, project_name: str, details: Optional[str] = None):
        """Log project-related actions"""
        message = f"Project: {project_name} - Action: {action}"
        if details:
            message += f" - Details: {details}"
        self.info(message)

    def log_video_processing(self, video_path: str, operation: str, details: Optional[str] = None):
        """Log video processing operations"""
        message = f"Video: {os.path.basename(video_path)} - Operation: {operation}"
        if details:
            message += f" - Details: {details}"
        self.info(message)

    def log_frame_operation(self, frame_number: int, operation: str, details: Optional[str] = None):
        """Log frame-specific operations"""
        message = f"Frame: {frame_number:04d} - Operation: {operation}"
        if details:
            message += f" - Details: {details}"
        self.debug(message)

    def log_ffmpeg_command(self, command: str, operation: str):
        """Log FFmpeg commands"""
        self.info(f"FFmpeg {operation}: {command}")

    def log_error_with_traceback(self, error: Exception, context: str):
        """Log error with full traceback"""
        self.error(f"Error in {context}: {str(error)}")
        self.debug(f"Traceback: {error.__traceback__}")

# Global logger instance
logger = BeneditoLogger()

def get_logger() -> BeneditoLogger:
    """Get the global logger instance"""
    return logger
