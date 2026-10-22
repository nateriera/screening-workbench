"""Append exact pytest phase reports and completed-node results for CI evidence."""
from __future__ import annotations

import json
import os
from pathlib import Path

_output = Path(os.environ.get("SWB_TEST_EVIDENCE_DIR", "artifacts/evidence"))
_active_path = _output / "active-node.json"
_tests_path = _output / "pytest-tests.jsonl"
_phases_path = _output / "pytest-phases.jsonl"
_reports: dict[str, list[dict]] = {}


def _append(path: Path, value: dict) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False) + "\n")
        stream.flush()


def _write_active(nodeid: str | None) -> None:
    temporary = _active_path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"nodeid": nodeid}) + "\n", encoding="utf-8")
    temporary.replace(_active_path)


def pytest_configure(config):
    _output.mkdir(parents=True, exist_ok=True)
    _tests_path.write_text("", encoding="utf-8")
    _phases_path.write_text("", encoding="utf-8")
    _write_active(None)


def pytest_runtest_logstart(nodeid, location):
    _reports[nodeid] = []
    _write_active(nodeid)


def pytest_runtest_logreport(report):
    entry = {
        "nodeid": report.nodeid,
        "when": report.when,
        "outcome": report.outcome,
        "duration_seconds": round(report.duration, 6),
    }
    if report.failed:
        entry["failure_trace"] = report.longreprtext
    if report.skipped:
        entry["skip_detail"] = report.longreprtext
    _reports.setdefault(report.nodeid, []).append(entry)
    _append(_phases_path, entry)


def pytest_runtest_logfinish(nodeid, location):
    reports = _reports.pop(nodeid, [])
    outcomes = [entry["outcome"] for entry in reports]
    if "failed" in outcomes:
        status = "failed"
    elif "skipped" in outcomes:
        status = "skipped"
    elif any(entry["when"] == "call" and entry["outcome"] == "passed" for entry in reports):
        status = "passed"
    else:
        status = "other"
    _append(_tests_path, {
        "nodeid": nodeid,
        "status": status,
        "duration_seconds": round(sum(entry["duration_seconds"] for entry in reports), 6),
        "failure_traces": [entry["failure_trace"] for entry in reports if "failure_trace" in entry],
        "phases": [{"when": entry["when"], "outcome": entry["outcome"]} for entry in reports],
    })
    _write_active(None)
