import logging
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from lib.utils.logger import BeneditoLogger


def test_reconfiguring_logger_closes_previous_file_handler(tmp_path):
    name = "BeneditoDigitalLoggerTest"
    first = BeneditoLogger(name=name, log_dir=str(tmp_path / "first"))
    previous = next(
        handler for handler in first.logger.handlers if isinstance(handler, logging.FileHandler)
    )

    BeneditoLogger(name=name, log_dir=str(tmp_path / "second"))

    assert previous.stream is None
