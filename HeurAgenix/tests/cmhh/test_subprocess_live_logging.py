from __future__ import annotations

import sys
from cmhh.agents.subprocess_runner import run_streaming_subprocess


def test_subprocess_streams_stderr_and_captures_stdout() -> None:
    # Child script prints structured message to stderr and clean machine result to stdout
    script = (
        "import sys\n"
        "sys.stderr.write('[LLM] test live log 1\\n')\n"
        "sys.stderr.flush()\n"
        "sys.stderr.write('[GEN] test live log 2\\n')\n"
        "sys.stderr.flush()\n"
        "sys.stdout.write('{\"status\": \"ok\", \"val\": 42}\\n')\n"
        "sys.stdout.flush()\n"
    )
    cmd = [sys.executable, "-c", script]
    result = run_streaming_subprocess(cmd, timeout_seconds=10.0)

    assert result.returncode == 0
    assert '{"status": "ok", "val": 42}' in result.stdout
    assert "[LLM] test live log 1" not in result.stdout
