from __future__ import annotations

import logging
import re
from typing import Any, Iterable


DEFAULT_REDACTION_PATTERNS = [
    re.compile(r"(?i)(authorization\s*:\s*bearer\s+)([A-Za-z0-9_\-\.]+)", re.IGNORECASE),
    re.compile(r"(?i)(authorization\s*:\s*basic\s+)([A-Za-z0-9+/=]+)", re.IGNORECASE),
    re.compile(r"(?i)(api[_-]?key\s*[:=]\s*['\"]?)([A-Za-z0-9_\-\.]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(?i)(token\s*[:=]\s*['\"]?)([A-Za-z0-9_\-\.]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(?i)(secret\s*[:=]\s*['\"]?)([A-Za-z0-9_\-\.]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(?i)(x-api-key\s*[:=]\s*['\"]?)([A-Za-z0-9_\-\.]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(?i)(azure_ad_token\s*[:=]\s*['\"]?)([A-Za-z0-9_\-\.]+)(['\"]?)", re.IGNORECASE),
    re.compile(r"(sk-[A-Za-z0-9_\-]{16,})", re.IGNORECASE),
]


def redact_secrets(text: str, extra_secrets: Iterable[str] | None = None) -> str:
    """Helper function to redact sensitive tokens/keys from text."""
    if not isinstance(text, str):
        return text
    filter_ = SecretRedactionFilter(extra_secrets=extra_secrets)
    return filter_._redact_text(text)


class SecretRedactionFilter(logging.Filter):
    """Logging filter that redacts API keys, bearer tokens, and secret patterns."""

    def __init__(self, name: str = "", extra_secrets: Iterable[str] | None = None) -> None:
        super().__init__(name)
        self._exact_secrets: set[str] = set()
        if extra_secrets:
            for s in extra_secrets:
                if s and len(s) >= 4:
                    self._exact_secrets.add(s)

    def register_secret(self, secret: str | None) -> None:
        if secret and len(secret) >= 4:
            self._exact_secrets.add(secret)

    def _redact_text(self, text: str) -> str:
        if not isinstance(text, str):
            return text

        for secret in self._exact_secrets:
            if secret in text:
                text = text.replace(secret, "[REDACTED]")

        for pattern in DEFAULT_REDACTION_PATTERNS:
            if pattern.groups == 1:
                text = pattern.sub("[REDACTED]", text)
            elif pattern.groups == 2:
                text = pattern.sub(r"\1[REDACTED]", text)
            elif pattern.groups == 3:
                text = pattern.sub(r"\1[REDACTED]\3", text)

        return text

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self._redact_text(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self._redact_text(v) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self._redact_text(v) if isinstance(v, str) else v for v in record.args)
            elif isinstance(record.args, list):
                record.args = [self._redact_text(v) if isinstance(v, str) else v for v in record.args]
        return True
