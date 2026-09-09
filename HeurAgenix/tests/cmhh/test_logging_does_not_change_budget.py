from __future__ import annotations

import random
from cmhh.llm.budgeted_client import BudgetExceededError, BudgetedLLMClient
from src.util.llm_client.base_llm_client import BaseLLMClient


class MockLLM(BaseLLMClient):
    def chat_once(self) -> str:
        return "response"


def test_d1_contract_logging_does_not_affect_budget_accounting() -> None:
    delegate = MockLLM({"model": "test"})
    budgeted = BudgetedLLMClient(delegate, max_llm_calls=2)

    # Initial state
    assert budgeted.calls_made == 0
    assert budgeted.remaining_budget == 2

    # Call 1
    res1 = budgeted.chat()
    assert res1 == "response"
    assert budgeted.calls_made == 1
    assert budgeted.remaining_budget == 1

    # Call 2
    res2 = budgeted.chat()
    assert res2 == "response"
    assert budgeted.calls_made == 2
    assert budgeted.remaining_budget == 0

    # Call 3 exceeds budget
    try:
        budgeted.chat()
        assert False, "Should have raised BudgetExceededError"
    except BudgetExceededError:
        pass


def test_d1_contract_logging_does_not_advance_rng() -> None:
    random.seed(42)
    state_before = random.getstate()

    # Perform logging operations
    import logging
    logger = logging.getLogger("cmhh.observability")
    logger.info("Test log for RNG invariance")

    state_after = random.getstate()
    assert state_before == state_after
