from __future__ import annotations

import json
import tempfile
import threading
from pathlib import Path

from cmhh.tracking.llm_call_logger import LLMCallLogger, LLMCallRecord


def test_concurrent_jsonl_writes_no_corruption() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        jsonl_path = Path(tmpdir) / "llm_calls.jsonl"
        logger = LLMCallLogger(jsonl_path)

        def worker(worker_num: int) -> None:
            for i in range(20):
                rec = LLMCallRecord(
                    call_id=f"worker-{worker_num}-call-{i}",
                    worker_id=f"w-{worker_num}",
                    attempt=1,
                    model="gpt-test",
                    backend="api",
                    status_code=200,
                    reason="OK",
                    latency_s=0.01,
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                    error_type=None,
                    error_message=None,
                )
                logger.log_attempt(rec)

        threads = [threading.Thread(target=worker, args=(w,)) for w in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        lines = jsonl_path.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 100

        # Each line must parse cleanly as JSON
        for line in lines:
            parsed = json.loads(line)
            assert parsed["status_code"] == 200
            assert parsed["schema_version"] == 1
