from __future__ import annotations

from time import sleep
from typing import Any


class LLMBudgetExceeded(RuntimeError):
    pass


class BudgetedLLMClient:
    """Proxy that applies a hard budget to actual provider attempts."""

    def __init__(self, delegate: Any, max_calls: int) -> None:
        if max_calls <= 0:
            raise ValueError("max_calls must be positive")
        self.delegate = delegate
        self.max_calls = max_calls
        self.calls_used = 0
        # Delegate methods such as load_background() call self.chat() internally.
        # Replace those entry points so indirect calls cannot bypass the budget.
        self.delegate.chat = self.chat
        self.delegate.chat_with_tools = self.chat_with_tools

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def _reserve(self) -> None:
        if self.calls_used >= self.max_calls:
            raise LLMBudgetExceeded(f"LLM call budget exhausted ({self.max_calls})")
        self.calls_used += 1

    def chat(self) -> str:
        last_error: Exception | None = None
        for attempt in range(self.delegate.max_attempts):
            self._reserve()
            try:
                response = self.delegate.chat_once()
                self.delegate.messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": response}],
                })
                return response
            except LLMBudgetExceeded:
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.delegate.max_attempts and self.calls_used < self.max_calls:
                    sleep(self.delegate.sleep_time)
        raise RuntimeError(f"LLM request failed after {self.calls_used} attempts: {last_error}")

    def chat_with_tools(self, tools):
        last_error: Exception | None = None
        for attempt in range(self.delegate.max_attempts):
            self._reserve()
            try:
                response, calls = self.delegate.chat_once_with_tools(tools)
                choices = "\n".join(
                    f"function: {name}, parameters: {parameters}" for name, parameters in calls
                )
                self.delegate.messages.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": f"{response}\n\nChoices:\n{choices}"}],
                })
                return calls
            except LLMBudgetExceeded:
                raise
            except Exception as exc:
                last_error = exc
                if attempt + 1 < self.delegate.max_attempts and self.calls_used < self.max_calls:
                    sleep(self.delegate.sleep_time)
        raise RuntimeError(f"LLM tool request failed after {self.calls_used} attempts: {last_error}")
