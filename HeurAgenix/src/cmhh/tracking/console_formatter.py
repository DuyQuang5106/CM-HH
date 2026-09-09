from __future__ import annotations

import logging
import sys
import time
from datetime import datetime, timezone


class ConsoleFormatter(logging.Formatter):
    """Clean human-readable console formatter with Windows ASCII fallback."""

    def __init__(self, force_ascii: bool = False) -> None:
        super().__init__(datefmt="%H:%M:%S")
        self.force_ascii = force_ascii or not self._supports_unicode()

    @staticmethod
    def _supports_unicode() -> bool:
        encoding = getattr(sys.stderr, "encoding", None) or getattr(sys.stdout, "encoding", None)
        if not encoding:
            return False
        try:
            "═".encode(encoding)
            return True
        except Exception:
            return False

    def format(self, record: logging.LogRecord) -> str:
        # Generate HH:MM:SS timestamp
        record_time = time.strftime(self.datefmt or "%H:%M:%S", time.localtime(record.created))
        message = record.getMessage()

        # If force_ascii or console doesn't support unicode box characters, replace them
        if self.force_ascii:
            message = message.replace("═", "=").replace("─", "-")

        # Format with timestamp if not already formatted with timestamp
        if not message.startswith(f"{record_time} "):
            return f"{record_time} {message}"
        return message
