from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from cmhh.logging import EventRecord, EventWriter
from cmhh.tracking.llm_call_logger import LLMCallLogger, LLMCallRecord


def test_event_writer_schema_version_and_timestamp() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        events_path = Path(tmpdir) / "events.jsonl"
        writer = EventWriter(events_path)

        rec = EventRecord(event="run_started", task_id="tsp_20", payload={"seed": 1})
        writer.write_event(rec)

        lines = events_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["schema_version"] == 1
        assert data["event"] == "run_started"
        assert data["task_id"] == "tsp_20"
        # Validate UTC ISO-8601 timestamp
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts is not None


def test_llm_call_logger_schema_version_and_timestamp() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
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
        logger.log_attempt(rec)

        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 1

        data = json.loads(lines[0])
        assert data["schema_version"] == 1
        assert data["call_id"] == "call-1"
        ts = datetime.fromisoformat(data["timestamp"])
        assert ts is not None
