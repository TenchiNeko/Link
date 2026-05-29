#!/usr/bin/env python3
from __future__ import annotations

"""
Autonomous wrapper for Link full-engine runs.

This keeps audit and micro-patch fast paths separate, while giving the full
autonomous path a stateful loop controller.
"""

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from link_loop_state import (
    ROOT,
    changed_files,
    evaluate_loop_risk,
    is_stuck_loop_report,
    prompt_hash,
    read_json,
    write_loop_handoff,
    write_loop_report,
)

RUN_ROOT = ROOT / ".agents" / "engine_runs"


def add_event(events: list[dict[str, Any]], level: str, title: str, detail: str = "", phase: str = "autonomous", raw: str = "") -> None:
    event = {
        "ts": time.time(),
        "level": level,
        "title": title,
        "detail": detail,
        "phase": phase,
        "raw": raw,
    }
    events.append(event)

    prefix = {
        "success": "✓",
        "warning": "!",
        "error": "✗",
        "info": "•",
    }.get(level, "•")

    if detail:
        print(f"{prefix} {title} — {detail}", flush=True)
    else:
        print(f"{prefix} {title}", flush=True)


def latest_report_since(start_ts: float, own_run_id: str) -> tuple[Path, dict[str, Any]] | None:
    if not RUN_ROOT.exists():
        return None

    paths = [
        p
        for p in RUN_ROOT.glob("*/engine_report.json")
        if p.parent.name != "selftest"
        and p.parent.name != own_run_id
        and not p.parent.name.startswith("audit-")
        and p.stat().st_mtime >= start_ts - 1
    ]

    for path in sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True):
        data = read_json(path)
        if data:
            return path, data

    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Link autonomous wrapper")
    parser.add_argument("command", nargs="?", default="run")
    parser.add_argument("--prompt-file", required=True)
    parser.add_argument("--max-iterations", default="1")
    parser.add_argument("--max-changed-files", default="8")
    parser.add_argument("--max-diff-lines", default="1200")
    parser.add_argument("--auto-restore-on-failure", action="store_true")
    args = parser.parse_args()

    run_id = f"auto-{uuid.uuid4().hex[:12]}"
    events: list[dict[str, Any]] = []
    prompt = Path(args.prompt_file).read_text(encoding="utf-8")

    add_event(events, "info", "Autonomous wrapper started", run_id)
    add_event(events, "info", "Prompt fingerprint", prompt_hash(prompt))

    decision = evaluate_loop_risk(ROOT, prompt)
    if decision.get("action") == "stop_with_handoff":
        handoff = write_loop_handoff(ROOT, prompt, decision)
        add_event(events, "warning", "Loop controller blocked repeat", decision.get("reason", "repeat loop"), phase="loop_guard")
        add_event(events, "warning", "Handoff written", str(handoff), phase="loop_guard")
        report = write_loop_report(
            ROOT,
            run_id=run_id,
            prompt=prompt,
            status="blocked",
            phase="loop_guard",
            exit_code=2,
            events=events,
            handoff=str(handoff),
            failure_type="stuck_loop",
        )
        add_event(events, "info", "Loop controller report", str(report), phase="loop_guard")
        return 2

    add_event(events, "info", "Loop controller allowed run", decision.get("reason", "allowed"))

    cmd = [
        sys.executable,
        str(ROOT / "link_engine.py"),
        "run",
        "--prompt-file",
        str(args.prompt_file),
        "--max-iterations",
        str(args.max_iterations),
        "--max-changed-files",
        str(args.max_changed_files),
        "--max-diff-lines",
        str(args.max_diff_lines),
    ]

    if args.auto_restore_on_failure:
        cmd.append("--auto-restore-on-failure")

    add_event(events, "info", "Child engine started", " ".join(cmd).replace(str(args.prompt_file), "<prompt>"))
    start_ts = time.time()

    process = subprocess.Popen(
        cmd,
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    assert process.stdout is not None
    for line in process.stdout:
        print(line, end="", flush=True)

    exit_code = process.wait()
    add_event(
        events,
        "success" if exit_code == 0 else "error",
        "Child engine exited",
        f"exit {exit_code}",
    )

    child = latest_report_since(start_ts, run_id)
    child_report_path: str | None = None
    child_report: dict[str, Any] | None = None

    if child:
        path, data = child
        child_report_path = str(path)
        child_report = data
        add_event(events, "info", "Child report found", child_report_path)
    else:
        add_event(events, "warning", "Child report missing", "could not locate latest engine_report.json")

    failure_type = None
    handoff_path = None

    if exit_code != 0 and child_report and is_stuck_loop_report(child_report) and not changed_files(child_report):
        failure_type = "stuck_loop"
        decision = {
            "action": "stop_with_handoff",
            "reason": "child engine hit stuck loop with no changed files",
            "prompt_hash": prompt_hash(prompt),
            "prior_report": child_report_path,
            "recommendation": [
                "Do not rerun this same autonomous prompt blindly.",
                "Use audit-only to inspect exact missing context.",
                "Convert the task into a one-file or small deterministic patch.",
                "Spawn fresh with a narrower prompt if a full run is still required.",
            ],
        }
        handoff = write_loop_handoff(ROOT, prompt, decision, child_report=child_report_path)
        handoff_path = str(handoff)
        add_event(events, "warning", "Loop controller handoff written", handoff_path, phase="loop_guard")

    status = "completed" if exit_code == 0 else "failed"
    report = write_loop_report(
        ROOT,
        run_id=run_id,
        prompt=prompt,
        status=status,
        phase="autonomous" if exit_code == 0 else "failed",
        exit_code=exit_code,
        events=events,
        child_report=child_report_path,
        handoff=handoff_path,
        failure_type=failure_type,
    )
    add_event(events, "info", "Autonomous wrapper report", str(report))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
