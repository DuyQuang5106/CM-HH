from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.tracking.context import RunLogContext, set_current_context
from cmhh.tracking.llm_call_logger import LLMCallLogger
from src.util.llm_client.api_model_client import APIModelClient


def test_api_client_missing_tokens_preserved_as_none() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)
        set_current_context(RunLogContext(run_id="test_run", task_id="tsp20", worker_id="worker-0", llm_call_logger=logger))

        config = {
            "model": "gpt-custom",
            "url": "https://api.openai.com/v1/chat/completions",
            "api_key": "test_key",
            "timeout": 10,
        }
        client = APIModelClient(config)
        client.messages = [{"role": "user", "content": "hello"}]

        # Response without "usage" field
        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.text = json.dumps({
            "choices": [{"message": {"content": "no usage field content"}}],
        })

        with patch("requests.request", return_value=mock_resp):
            reply = client.chat_once()

        assert reply == "no usage field content"
        records = logger.load_all()
        assert len(records) == 1
        rec = records[0]
        # Verify tokens are None/null and NOT 0
        assert rec["prompt_tokens"] is None
        assert rec["completion_tokens"] is None
        assert rec["total_tokens"] is None
