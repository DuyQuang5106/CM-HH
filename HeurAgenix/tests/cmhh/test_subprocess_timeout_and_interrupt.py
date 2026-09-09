from __future__ import annotations

import subprocess
import sys
import pytest
from cmhh.agents.subprocess_runner import run_streaming_subprocess


def test_subprocess_timeout_raises_and_cleans_up() -> None:
    # Sleep longer than timeout
    script = (
        "import time, sys\n"
        "sys.stderr.write('Sleeping...\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(10)\n"
    )
    cmd = [sys.executable, "-c", script]

    with pytest.raises(subprocess.TimeoutExpired):
        run_streaming_subprocess(cmd, timeout_seconds=0.5)
