from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.tracking.context import RunLogContext, set_current_context
from cmhh.tracking.llm_call_logger import LLMCallLogger
from src.util.llm_client.api_model_client import APIModelClient


def test_llm_client_retries_preserve_call_id() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)
        set_current_context(RunLogContext(run_id="test_run", task_id="tsp20", worker_id="worker-0", llm_call_logger=logger))

        config = {
            "model": "gpt-5-mini",
            "url": "https://api.openai.com/v1/chat/completions",
            "api_key": "test_key",
            "timeout": 10,
            "sleep_time": 0.0001,
        }
        client = APIModelClient(config)

        # Attempt 1: 429
        # Attempt 2: 429
        # Attempt 3: 200 OK
        resp_429 = MagicMock()
        resp_429.ok = False
        resp_429.status_code = 429
        resp_429.reason = "Too Many Requests"
        resp_429.text = "{}"

        resp_200 = MagicMock()
        resp_200.ok = True
        resp_200.status_code = 200
        resp_200.reason = "OK"
        resp_200.text = json.dumps({"choices": [{"message": {"content": "finally succeeded"}}]})

        client.messages.append({"role": "user", "content": "retry test"})
        with patch("requests.request", side_effect=[resp_429, resp_429, resp_200]):
            with patch("time.sleep", return_value=None):
                reply = client.chat()

        assert reply == "finally succeeded"
        records = logger.load_all()
        assert len(records) == 3

        # All 3 records should share the same call_id and model
        call_ids = {r["call_id"] for r in records}
        assert len(call_ids) == 1
        assert "call-" in list(call_ids)[0]

        # Attempts should be 1, 2, 3
        attempts = [r["attempt"] for r in records]
        assert attempts == [1, 2, 3]

        # Statuses should be 429, 429, 200
        statuses = [r["status_code"] for r in records]
        assert statuses == [429, 429, 200]
