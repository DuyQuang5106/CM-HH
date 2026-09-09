import logging
from time import sleep
from typing import Any

_LOGGER = logging.getLogger("cmhh.llm")


class LLMBudgetExceeded(RuntimeError):
    pass


BudgetExceededError = LLMBudgetExceeded


class BudgetedLLMClient:
    """Proxy that applies a hard budget to actual provider attempts."""

    def __init__(self, delegate: Any, max_calls: int | None = None, max_llm_calls: int | None = None) -> None:
        budget = max_calls if max_calls is not None else max_llm_calls
        if budget is None or budget <= 0:
            raise ValueError("max_calls/max_llm_calls must be positive")
        self.delegate = delegate
        self.max_calls = budget
        self.calls_used = 0
        # Delegate methods such as load_background() call self.chat() internally.
        # Replace those entry points so indirect calls cannot bypass the budget.
        self.delegate.chat = self.chat
        self.delegate.chat_with_tools = self.chat_with_tools

    @property
    def calls_made(self) -> int:
        return self.calls_used

    @property
    def remaining_budget(self) -> int:
        return max(0, self.max_calls - self.calls_used)

    def __getattr__(self, name: str) -> Any:
        return getattr(self.delegate, name)

    def _reserve(self) -> None:
        if self.calls_used >= self.max_calls:
            raise LLMBudgetExceeded(f"LLM call budget exhausted ({self.max_calls})")
        self.calls_used += 1

    def chat(self) -> str:
        last_error: Exception | None = None
        call_id = getattr(self.delegate, "_next_call_id", lambda: "call#001")()
        setattr(self.delegate, "current_call_id", call_id)
        backend_name = getattr(self.delegate, "backend_name", "base")
        model_name = getattr(self.delegate, "name", "unknown_model")
        _LOGGER.info("[LLM] %s request | backend=%s | model=%s", call_id, backend_name, model_name)

        for attempt in range(self.delegate.max_attempts):
            setattr(self.delegate, "current_attempt", attempt + 1)
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
                    _LOGGER.warning(
                        "[LLM] %s retry %d/%d | %s: %s",
                        call_id,
                        attempt + 1,
                        self.delegate.max_attempts,
                        type(exc).__name__,
                        exc,
                    )
                    sleep(self.delegate.sleep_time)
                else:
                    _LOGGER.error(
                        "[LLM] %s failed permanently | attempts=%d | %s: %s",
                        call_id,
                        self.delegate.max_attempts,
                        type(exc).__name__,
                        exc,
                    )
        raise RuntimeError(f"LLM request failed after {self.calls_used} attempts: {last_error}")

    def chat_with_tools(self, tools):
        last_error: Exception | None = None
        call_id = getattr(self.delegate, "_next_call_id", lambda: "call#001")()
        setattr(self.delegate, "current_call_id", call_id)
        backend_name = getattr(self.delegate, "backend_name", "base")
        model_name = getattr(self.delegate, "name", "unknown_model")
        _LOGGER.info("[LLM] %s request | backend=%s | model=%s", call_id, backend_name, model_name)

        for attempt in range(self.delegate.max_attempts):
            setattr(self.delegate, "current_attempt", attempt + 1)
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
                    _LOGGER.warning(
                        "[LLM] %s retry %d/%d | %s: %s",
                        call_id,
                        attempt + 1,
                        self.delegate.max_attempts,
                        type(exc).__name__,
                        exc,
                    )
                    sleep(self.delegate.sleep_time)
                else:
                    _LOGGER.error(
                        "[LLM] %s failed permanently | attempts=%d | %s: %s",
                        call_id,
                        self.delegate.max_attempts,
                        type(exc).__name__,
                        exc,
                    )
        raise RuntimeError(f"LLM tool request failed after {self.calls_used} attempts: {last_error}")

