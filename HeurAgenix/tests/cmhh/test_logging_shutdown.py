from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from cmhh.tracking.logging_config import configure_logging, shutdown_logging


def test_shutdown_logging_flushes_and_releases_locks() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        log_dir = Path(tmpdir)
        handlers = configure_logging(log_dir=log_dir, level="INFO")
        logger = logging.getLogger("cmhh.test")
        logger.info("Message before shutdown")

        shutdown_logging()

        # Root logger should no longer have cmhh managed handlers
        root_logger = logging.getLogger()
        cmhh_handlers = [h for h in root_logger.handlers if getattr(h, "_cmhh_managed", False)]
        assert len(cmhh_handlers) == 0

        log_file = log_dir / "run.log"
        assert log_file.exists()
        assert "Message before shutdown" in log_file.read_text(encoding="utf-8")
