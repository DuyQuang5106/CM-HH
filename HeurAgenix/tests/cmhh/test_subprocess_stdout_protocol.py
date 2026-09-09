from __future__ import annotations

import json
import sys
from cmhh.agents.subprocess_runner import run_streaming_subprocess


def test_subprocess_stdout_json_protocol_unpolluted() -> None:
    # Emits extensive logging to stderr, only raw JSON to stdout
    script = (
        "import sys, json\n"
        "for i in range(10):\n"
        "    sys.stderr.write(f'[PROBE] step {i}\\n')\n"
        "    sys.stderr.flush()\n"
        "payload = {'candidates': ['heur_a', 'heur_b'], 'count': 2}\n"
        "sys.stdout.write(json.dumps(payload))\n"
        "sys.stdout.flush()\n"
    )
    cmd = [sys.executable, "-c", script]
    result = run_streaming_subprocess(cmd, timeout_seconds=10.0)

    assert result.returncode == 0
    # Must be directly parsable as JSON with no log junk
    parsed = json.loads(result.stdout.strip())
    assert parsed["count"] == 2
    assert parsed["candidates"] == ["heur_a", "heur_b"]
