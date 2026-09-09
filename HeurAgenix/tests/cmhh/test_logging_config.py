from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from cmhh.tracking.logging_config import configure_logging, shutdown_logging


def test_configure_logging_creates_files_and_handlers() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        handlers = configure_logging(log_dir=log_dir, level="DEBUG", quiet=False)
        try:
            assert len(handlers) >= 2  # Console + File handler
            log_file = log_dir / "run.log"
            assert log_file.exists()

            logger = logging.getLogger("cmhh.test")
            logger.info("Test message for logging config")

            # Force flush
            for h in handlers:
                h.flush()

            content = log_file.read_text(encoding="utf-8")
            assert "Test message for logging config" in content
        finally:
            shutdown_logging()


def test_configure_logging_idempotency() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        handlers1 = configure_logging(log_dir=log_dir, level="INFO")
        handlers2 = configure_logging(log_dir=log_dir, level="INFO")
        try:
            # Reconfiguring should not endlessly duplicate root handlers
            root_logger = logging.getLogger()
            cmhh_handlers = [h for h in root_logger.handlers if getattr(h, "_cmhh_managed", False)]
            assert len(cmhh_handlers) == len(handlers2)
        finally:
            shutdown_logging()


def test_configure_logging_quiet_mode(capsys) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        handlers = configure_logging(log_dir=log_dir, level="INFO", quiet=True)
        try:
            # When quiet=True, only FileHandler is attached
            assert len(handlers) == 1
            assert isinstance(handlers[0], logging.FileHandler)

            logger = logging.getLogger("cmhh.test")
            logger.info("Quiet message test")

            for h in handlers:
                h.flush()

            log_file = log_dir / "run.log"
            assert "Quiet message test" in log_file.read_text(encoding="utf-8")
        finally:
            shutdown_logging()
