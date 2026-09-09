from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

from cmhh.tracking.llm_call_logger import LLMCallLogger, LLMCallRecord


def test_d9_sink_write_failure_does_not_crash_caller() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "invalid_path" / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)

        rec = LLMCallRecord(
            call_id="call-1",
            worker_id="w-0",
            attempt=1,
            model="gpt-5-mini",
            backend="api",
            status_code=200,
            reason="OK",
            latency_s=1.23,
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            error_type=None,
            error_message=None,
        )

        # Mock open or write to raise OSError
        with patch.object(Path, "open", side_effect=OSError("Disk write error")):
            # Must NOT raise exception (D9 failure isolation)
            logger.log_attempt(rec)
