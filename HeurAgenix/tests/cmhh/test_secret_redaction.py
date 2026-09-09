from __future__ import annotations

import logging
from cmhh.tracking.redaction import SecretRedactionFilter, redact_secrets


def test_redact_secrets_bearer_and_basic_auth() -> None:
    text = "Sending request with header Authorization: Bearer secret_token_xyz_123 and user pass Authorization: Basic dXNlcjpwYXNz"
    redacted = redact_secrets(text)
    assert "secret_token_xyz_123" not in redacted
    assert "dXNlcjpwYXNz" not in redacted
    assert "[REDACTED]" in redacted


def test_redact_secrets_api_key_patterns() -> None:
    text = "Error with api_key=sk-proj-999988887777 and token: 'my_secret_token_abc'"
    redacted = redact_secrets(text)
    assert "sk-proj-999988887777" not in redacted
    assert "my_secret_token_abc" not in redacted
    assert "[REDACTED]" in redacted


def test_redaction_filter_on_log_record() -> None:
    filter_ = SecretRedactionFilter()
    record = logging.LogRecord(
        name="cmhh.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Connecting to OpenAI with api_key: %s",
        args=("sk-1234567890abcdef",),
        exc_info=None,
    )
    filter_.filter(record)
    formatted = record.getMessage()
    assert "sk-1234567890abcdef" not in formatted
    assert "[REDACTED]" in formatted
