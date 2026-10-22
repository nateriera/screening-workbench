#!/usr/bin/env python3
"""Run the complete pytest suite with a hard timeout and retained output."""
from __future__ import annotations

import argparse
import json
import os
import selectors
import signal
import subprocess
import sys
import time
from pathlib import Path


def run(output: Path, timeout: int) -> int:
    output.mkdir(parents=True, exist_ok=True)
    junit = output / "pytest-junit.xml"
    log_path = output / "pytest.log"
    command = [
        sys.executable, "-m", "pytest", "tests/", "-q",
        f"--junitxml={junit}", "-o", "faulthandler_timeout=120",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    started = time.monotonic()
    timed_out = False
    proc = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        env=env, start_new_session=True,
    )
    assert proc.stdout is not None
    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    with log_path.open("wb") as log:
        while proc.poll() is None or selector.get_map():
            remaining = started + timeout - time.monotonic()
            if remaining <= 0 and proc.poll() is None:
                timed_out = True
                os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
            for key, _ in selector.select(max(0.0, min(0.25, remaining))):
                chunk = os.read(key.fd, 65536)
                if chunk:
                    log.write(chunk)
                    log.flush()
                    sys.stdout.buffer.write(chunk)
                    sys.stdout.buffer.flush()
                else:
                    selector.unregister(key.fileobj)
        exit_code = 124 if timed_out else int(proc.returncode or 0)
    result = {
        "command": command,
        "exit_code": exit_code,
        "suite": "tests/ (no deselections)",
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "duration_seconds": round(time.monotonic() - started, 3),
        "log": str(log_path),
        "junit_xml": str(junit),
        "candidate_status": "candidate_with_test_timeout" if timed_out else (
            "passed" if exit_code == 0 else "candidate_with_test_failures"
        ),
    }
    (output / "test-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="directory for pytest log, JUnit XML, and JSON result")
    parser.add_argument("--timeout", type=int, default=300, help="maximum run time in seconds (default: 300)")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be at least one second")
    return run(args.output.expanduser().resolve(), args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
