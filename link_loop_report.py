#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path
from typing import Any

from link_common import ROOT, json_print, latest_engine_report, read_json, write_json, redact_obj

LOOP_RE = re.compile(r"(stuck loop|same commands repeated|repeated\s+\d+x|hit max rounds)", re.I)


def summarize_event(event: dict[str, Any]) -> str:
    return " | ".join(str(event.get(k, "")) for k in ("phase", "level", "title", "detail", "raw") if event.get(k))


def build_report(data: dict[str, Any]) -> dict[str, Any]:
    events = data.get("events", [])
    if not isinstance(events, list):
        events = []

    loop_events = [e for e in events if isinstance(e, dict) and LOOP_RE.search(summarize_event(e))]
    error_events = [
        e for e in events
        if isinstance(e, dict) and str(e.get("level", "")).lower() in {"error", "warning"}
    ]

    last_success = None
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("level", "")).lower() in {"success", "info"}:
            last_success = event

    phase = None
    if loop_events:
        phase = loop_events[-1].get("phase")
    elif error_events:
        phase = error_events[-1].get("phase")
    else:
        phase = data.get("phase")

    failure_type = "stuck_loop" if loop_events else ("failure" if data.get("exit_code") else "unknown")

    repeated_clues = []
    for event in loop_events:
        text = summarize_event(event)
        repeated_clues.append(text[:500])

    recommended = [
        "Stop retrying the same command/tool sequence.",
        "Summarize known state from the latest successful observation.",
        "Name the exact missing information or file section.",
        "Switch to a smaller deterministic patch or ask for one specific human input.",
        "For audit-only tasks, avoid sending the full orchestrator through build/verify phases when no write is expected.",
    ]

    report = {
        "run_id": data.get("run_id"),
        "failure_type": failure_type,
        "phase": phase,
        "exit_code": data.get("exit_code"),
        "engine_status": data.get("status"),
        "changed_files": data.get("changed_files", []),
        "diff_lines": data.get("diff_lines"),
        "loop_event_count": len(loop_events),
        "error_event_count": len(error_events),
        "repeated_command_clues": repeated_clues,
        "last_successful_observation": summarize_event(last_success) if isinstance(last_success, dict) else None,
        "recommended_next_action": recommended,
        "safe_to_retry": failure_type == "stuck_loop" and not data.get("changed_files"),
        "source_report": data.get("_path") or data.get("report_path"),
    }
    return redact_obj(report)


def write_markdown(report: dict[str, Any]) -> Path:
    out_dir = ROOT / ".agents" / "loop_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = report.get("run_id") or f"unknown-{int(time.time())}"
    md = out_dir / f"loop-report-{run_id}.md"
    lines = [
        f"# Link Loop Report: {run_id}",
        "",
        f"- failure_type: `{report.get('failure_type')}`",
        f"- phase: `{report.get('phase')}`",
        f"- safe_to_retry: `{report.get('safe_to_retry')}`",
        f"- source_report: `{report.get('source_report')}`",
        "",
        "## Last successful observation",
        "",
        str(report.get("last_successful_observation") or "None found."),
        "",
        "## Repeated command clues",
        "",
    ]
    for clue in report.get("repeated_command_clues", []):
        lines.append(f"- {clue}")
    lines += ["", "## Recommended next action", ""]
    for item in report.get("recommended_next_action", []):
        lines.append(f"- {item}")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return md


def main() -> int:
    parser = argparse.ArgumentParser(description="Create structured diagnostics for stuck-loop Link runs.")
    parser.add_argument("--report", help="Path to engine_report.json")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    if args.report:
        path = Path(args.report)
        data = read_json(path)
        if data:
            data["_path"] = str(path)
    else:
        data = latest_engine_report()

    if not data:
        raise SystemExit("No engine report found.")

    report = build_report(data)

    if args.write:
        out_json = ROOT / ".agents" / "loop_reports" / f"loop-report-{report.get('run_id')}.json"
        write_json(out_json, report)
        out_md = write_markdown(report)
        report["written_json"] = str(out_json)
        report["written_markdown"] = str(out_md)

    if args.json:
        json_print(report)
    else:
        print(f"failure_type: {report['failure_type']}")
        print(f"phase: {report['phase']}")
        print(f"safe_to_retry: {report['safe_to_retry']}")
        print(f"last_successful_observation: {report.get('last_successful_observation')}")
        print("recommended_next_action:")
        for item in report["recommended_next_action"]:
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
