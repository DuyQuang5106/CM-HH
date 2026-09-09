from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.tracking.context import RunLogContext, set_current_context
from cmhh.tracking.llm_call_logger import LLMCallLogger
from src.util.llm_client.local_model_client import LocalModelClient


def test_local_model_client_has_unknown_http_status() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)
        set_current_context(RunLogContext(run_id="test_run", task_id="tsp20", worker_id="worker-0", llm_call_logger=logger))

        config = {
            "model": "local_mock",
            "model_path": "mock_path",
        }
        client = LocalModelClient(config)
        client.messages = [{"role": "user", "content": "hello"}]
        client.pipeline = MagicMock(return_value=[{"generated_text": "local response"}])
        client.pipeline.tokenizer.apply_chat_template.return_value = "formatted prompt"

        reply = client.chat_once()
        assert reply == "local response"

        records = logger.load_all()
        assert len(records) == 1
        rec = records[0]
        # Status code is None / null (NOT fabricated 200)
        assert rec["status_code"] is None
        assert rec["backend"] == "local"
