from __future__ import annotations

import threading
from src.util.llm_client.base_llm_client import BaseLLMClient


class DummyClient(BaseLLMClient):
    def chat_once(self) -> str:
        return f"result_{self.current_call_id}"


def test_call_id_counter_thread_safe_and_monotonic() -> None:
    client = DummyClient({"model": "dummy"})
    generated_call_ids: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        call_id = client._next_call_id()
        with lock:
            generated_call_ids.append(call_id)

    threads = [threading.Thread(target=worker) for _ in range(50)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(generated_call_ids) == 50
    # All IDs must be unique
    assert len(set(generated_call_ids)) == 50
    # All IDs must follow call-N pattern
    for call_id in generated_call_ids:
        assert call_id.startswith("call-")
