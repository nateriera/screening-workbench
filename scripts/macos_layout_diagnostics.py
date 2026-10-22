"""Run unchanged failing layout tests under bounded diagnostic-only controls."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

TESTS = ["test_maybe_tab_uses_three_column_queue_detail_and_decision_layout",
         "test_prisma_flow_diagram_enters_reference_viewport_after_counts",
         "test_ttk_primary_controls_meet_minimum_target_height",
         "test_phase3_screening_decision_bars_fit_visible_cards_at_1280x800"]
CONTROLS = ["baseline", "maxsize-1280", "minsize-1280", "borderless-1280",
            "button-padding-plus2", "scaling-1.5"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for control in CONTROLS:
        directory = output / control
        directory.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env.update(SWB_LAYOUT_CONTROL=control, SWB_LAYOUT_DIR=str(directory), PYTHONUNBUFFERED="1")
        command = [sys.executable, "-m", "pytest", *[f"tests/test_app.py::{test}" for test in TESTS],
                   "-q", "-o", "faulthandler_timeout=20", "-p", "scripts.macos_layout_diagnostic_plugin",
                   f"--junitxml={directory / 'junit.xml'}"]
        start = time.monotonic()
        try:
            result = subprocess.run(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=60)
            log = result.stdout
            code = result.returncode
        except subprocess.TimeoutExpired as exc:
            log = exc.output or b""
            code = 124
        (directory / "pytest.log").write_bytes(log)
        outcomes = []
        if (directory / "outcomes.jsonl").is_file():
            outcomes = [json.loads(line) for line in (directory / "outcomes.jsonl").read_text().splitlines()]
        rows.append({"control": control, "exit_code": code,
                     "seconds": round(time.monotonic() - start, 3), "outcomes": outcomes})
        print(control, code, [(row["nodeid"], row["outcome"]) for row in outcomes], flush=True)
    (output / "layout-summary.json").write_text(json.dumps({"diagnostic_only": True, "cases": rows}, indent=2) + "\n")


if __name__ == "__main__":
    main()
