from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from cmhh.tracking.context import RunLogContext, set_current_context
from cmhh.tracking.llm_call_logger import LLMCallLogger
from src.util.llm_client.api_model_client import APIModelClient


def test_api_client_http_200_logging_and_record() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)
        set_current_context(RunLogContext(run_id="test_run", task_id="tsp20", worker_id="worker-0", llm_call_logger=logger))

        config = {
            "model": "gpt-5-mini",
            "url": "https://api.openai.com/v1/chat/completions",
            "api_key": "test_key",
            "timeout": 10,
        }
        client = APIModelClient(config)
        client.messages = [{"role": "user", "content": "hello"}]

        mock_resp = MagicMock()
        mock_resp.ok = True
        mock_resp.status_code = 200
        mock_resp.reason = "OK"
        mock_resp.text = json.dumps({
            "choices": [{"message": {"content": "response content"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        })

        with patch("requests.request", return_value=mock_resp):
            reply = client.chat_once()

        assert reply == "response content"
        records = logger.load_all()
        assert len(records) == 1
        rec = records[0]
        assert rec["status_code"] == 200
        assert rec["reason"] == "OK"
        assert rec["prompt_tokens"] == 10
        assert rec["completion_tokens"] == 5
        assert rec["total_tokens"] == 15
        assert rec["backend"] == "api"
        assert rec["schema_version"] == 1


def test_api_client_http_429_retry_logging() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)
        set_current_context(RunLogContext(run_id="test_run", task_id="tsp20", worker_id="worker-0", llm_call_logger=logger))

        config = {
            "model": "gpt-5-mini",
            "url": "https://api.openai.com/v1/chat/completions",
            "api_key": "test_key",
            "timeout": 10,
        }
        client = APIModelClient(config)
        client.messages = [{"role": "user", "content": "hello"}]

        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 429
        mock_resp.reason = "Too Many Requests"
        mock_resp.text = json.dumps({"error": "rate limit"})

        import pytest
        with patch("requests.request", return_value=mock_resp):
            with pytest.raises(Exception):
                client.chat_once()

        records = logger.load_all()
        assert len(records) == 1
        rec = records[0]
        assert rec["status_code"] == 429
        assert rec["reason"] == "Too Many Requests"


def test_api_client_multi_key_rotation() -> None:
    config = {
        "model": "deepseek-ai/deepseek-r1",
        "url": "https://integrate.api.nvidia.com/v1/chat/completions",
        "api_key": "nvapi-key1, nvapi-key2, nvapi-key3, nvapi-key4",
        "timeout": 10,
    }
    client = APIModelClient(config)
    assert len(client.api_keys) == 4
    assert client.api_keys == ["nvapi-key1", "nvapi-key2", "nvapi-key3", "nvapi-key4"]

    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.status_code = 200
    mock_resp.reason = "OK"
    mock_resp.text = json.dumps({
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    })

    used_auth_headers = []
    def fake_request(method, url, json=None, headers=None, timeout=None):
        used_auth_headers.append(headers.get("Authorization"))
        return mock_resp

    with patch("requests.request", side_effect=fake_request):
        for _ in range(6):
            client.chat_once()

    assert used_auth_headers == [
        "Bearer nvapi-key1",
        "Bearer nvapi-key2",
        "Bearer nvapi-key3",
        "Bearer nvapi-key4",
        "Bearer nvapi-key1",
        "Bearer nvapi-key2",
    ]
