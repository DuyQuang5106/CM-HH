from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
from collections import deque
from pathlib import Path
from typing import Mapping


class SubprocessResult:
    def __init__(self, stdout: str, stderr_tail: list[str], returncode: int, elapsed_s: float) -> None:
        self.stdout = stdout
        self.stderr_tail = stderr_tail
        self.returncode = returncode
        self.elapsed_s = elapsed_s

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def run_streaming_subprocess(
    command: list[str],
    *,
    cwd: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = 3600.0,
    stream_stderr: bool = True,
    max_tail_lines: int = 100,
) -> SubprocessResult:
    """Runs a subprocess with unbuffered stderr real-time streaming and safe stdout capture."""
    sub_env = dict(env or os.environ)
    sub_env["PYTHONUNBUFFERED"] = "1"

    process = subprocess.Popen(
        command,
        cwd=str(cwd) if cwd is not None else None,
        env=sub_env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )

    stdout_chunks: list[str] = []
    stderr_tail: deque[str] = deque(maxlen=max_tail_lines)

    def _read_stdout() -> None:
        if process.stdout is not None:
            for line in process.stdout:
                stdout_chunks.append(line)

    def _read_stderr() -> None:
        if process.stderr is not None:
            for line in process.stderr:
                stderr_tail.append(line)
                if stream_stderr:
                    try:
                        sys.stderr.write(line)
                        sys.stderr.flush()
                    except Exception:
                        pass

    stdout_thread = threading.Thread(target=_read_stdout, daemon=True)
    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stdout_thread.start()
    stderr_thread.start()

    start_time = time.perf_counter()
    timed_out = False

    try:
        while True:
            ret = process.poll()
            if ret is not None:
                break

            elapsed = time.perf_counter() - start_time
            if elapsed > timeout_seconds:
                timed_out = True
                try:
                    process.terminate()
                    time.sleep(2.0)
                    if process.poll() is None:
                        process.kill()
                except Exception:
                    pass
                break

            time.sleep(0.1)

    except KeyboardInterrupt:
        # Contract D8: Safe Windows / cross-platform process cleanup on Ctrl+C
        try:
            process.terminate()
            time.sleep(1.0)
            if process.poll() is None:
                process.kill()
        except Exception:
            pass
        raise

    stdout_thread.join(timeout=5.0)
    stderr_thread.join(timeout=5.0)

    elapsed_s = time.perf_counter() - start_time

    if timed_out:
        raise subprocess.TimeoutExpired(command, timeout_seconds)

    return SubprocessResult(
        stdout="".join(stdout_chunks),
        stderr_tail=list(stderr_tail),
        returncode=process.returncode or 0,
        elapsed_s=elapsed_s,
    )
