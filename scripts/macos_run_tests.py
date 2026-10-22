#!/usr/bin/env python3
"""Run pytest with retained output and a hard timeout."""
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


def run(output: Path, timeout: int, test_path: str) -> int:
    output.mkdir(parents=True, exist_ok=True)
    junit = output / "pytest-junit.xml"
    log_path = output / "pytest.log"
    test_records = output / "pytest-tests.jsonl"
    phase_records = output / "pytest-phases.jsonl"
    active_path = output / "active-node.json"
    for path in (test_records, phase_records, active_path):
        path.unlink(missing_ok=True)
    command = [
        sys.executable, "-m", "pytest", test_path, "-q",
        f"--junitxml={junit}", "-o", "faulthandler_timeout=120",
        "-p", "scripts.macos_pytest_evidence",
    ]
    env = os.environ.copy()
    env["PYTHONUNBUFFERED"] = "1"
    env["SWB_TEST_EVIDENCE_DIR"] = str(output)
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

    completed = []
    if test_records.is_file():
        with test_records.open(encoding="utf-8") as records:
            completed = [json.loads(line) for line in records if line.strip()]
    counts = {status: sum(row.get("status") == status for row in completed)
              for status in ("passed", "failed", "skipped", "other")}
    failures = [
        {"nodeid": row["nodeid"], "failure_traces": row.get("failure_traces", [])}
        for row in completed if row.get("status") == "failed"
    ]
    active_node = None
    if active_path.is_file():
        active_node = json.loads(active_path.read_text(encoding="utf-8")).get("nodeid")
    result = {
        "command": command,
        "exit_code": exit_code,
        "suite": test_path,
        "no_deselections": True,
        "timed_out": timed_out,
        "timeout_seconds": timeout,
        "duration_seconds": round(time.monotonic() - started, 3),
        "completed_test_counts": counts,
        "completed_test_count": len(completed),
        "failed_tests": failures,
        "active_node_at_end": active_node,
        "log": str(log_path),
        "junit_xml": str(junit),
        "phase_records_jsonl": str(phase_records),
        "candidate_status": "candidate_with_test_timeout" if timed_out else (
            "passed" if exit_code == 0 else "candidate_with_test_failures"
        ),
    }
    (output / "test-results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return exit_code


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path, help="directory for logs and result evidence")
    parser.add_argument("--timeout", type=int, default=300, help="maximum run time in seconds (default: 300)")
    parser.add_argument("--test-path", default="tests/", help="pytest target (default: full tests/ suite)")
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error("--timeout must be at least one second")
    return run(args.output.expanduser().resolve(), args.timeout, args.test_path)


if __name__ == "__main__":
    raise SystemExit(main())
