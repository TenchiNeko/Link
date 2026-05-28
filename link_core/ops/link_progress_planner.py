#!/usr/bin/env python3
from __future__ import annotations

"""
Link Progress Planner.

Terminal-only deterministic planner for deciding the next safe Link action.

It does not run autonomous.
It does not edit source files.
It reads repo state, latest engine reports, latest fanout reports, and route
intelligence to recommend the next safest patch target.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from link_route_intelligence import decide_route

ROOT = Path(__file__).resolve().parent


def _run(cmd: list[str], timeout: int = 10) -> tuple[int, str, str]:
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception as exc:
        return {"_load_error": str(exc)}
    return {}


def _latest_files(pattern: str, limit: int = 5) -> list[Path]:
    files = [p for p in ROOT.glob(pattern) if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files[:limit]


def repo_state() -> dict[str, Any]:
    code, status, _ = _run(["git", "status", "--short", "--untracked-files=all"])
    _, head, _ = _run(["git", "log", "--oneline", "--decorate", "-1"])
    _, latest, _ = _run(["git", "rev-parse", "--short", "safe-link-latest"])

    dirty_lines = [line for line in status.splitlines() if line.strip()]
    return {
        "head": head.strip(),
        "safe_link_latest": latest.strip(),
        "dirty": bool(dirty_lines),
        "dirty_files": dirty_lines,
        "status_exit_code": code,
    }


def latest_engine_reports(limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _latest_files(".agents/engine_runs/*/engine_report.json", limit=limit):
        data = _load_json(path)
        out.append(
            {
                "path": str(path),
                "run_id": data.get("run_id") or path.parent.name,
                "status": data.get("status"),
                "phase": data.get("phase"),
                "exit_code": data.get("exit_code"),
                "failure_type": (
                    data.get("failure_type")
                    or data.get("failure_summary", {}).get("failure_type")
                    if isinstance(data.get("failure_summary"), dict)
                    else data.get("failure_type")
                ),
            }
        )
    return out


def latest_fanout_reports(limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for path in _latest_files(".agents/tool_results/*/specialist_fanout.json", limit=limit):
        data = _load_json(path)
        out.append(
            {
                "path": str(path),
                "run_id": data.get("run_id") or path.parent.name,
                "summary_path": data.get("summary_path"),
                "keys": sorted([k for k in data.keys() if not k.startswith("_")])[:20],
            }
        )
    return out


def _latest_failure_kind(reports: list[dict[str, Any]]) -> str | None:
    for report in reports:
        text = json.dumps(report, sort_keys=True, default=str).lower()
        for marker in ["stuck_loop", "verification_failed", "blocked", "failed"]:
            if marker in text:
                return marker
    return None


def choose_next_action(prompt: str | None, audit_only: bool = False) -> dict[str, Any]:
    repo = repo_state()
    engine = latest_engine_reports()
    fanout = latest_fanout_reports()

    raw_prompt = str(prompt or "").strip()
    route = decide_route(raw_prompt, audit_only=audit_only, run_fanout=False)

    reasons: list[str] = []
    target = "audit_current_state"
    command = "python3 link_audit_fast.py '<prompt>'"

    latest_failure = _latest_failure_kind(engine)

    if repo["dirty"]:
        target = "inspect_or_commit_existing_dirty_state"
        command = "git diff --stat && git status --short --untracked-files=all"
        reasons.append("repo_dirty_never_start_autonomous")
    elif route["route"] == "audit_fastpath":
        target = "ask_for_specific_patch_or_run_audit"
        command = "python3 link_audit_fast.py '<specific audit prompt>'"
        reasons.append("route_intelligence_selected_audit_fastpath")
    elif route["route"] == "micro_patch":
        target = "run_micro_patch_only"
        command = "python3 link_micro_patch.py '<micro patch prompt>'"
        reasons.append("route_intelligence_selected_micro_patch")
    elif latest_failure == "stuck_loop":
        target = "patch_loop_or_route_guard_before_autonomous"
        command = "python3 link_progress_planner.py --prompt '<specific patch prompt>'"
        reasons.append("latest_failure_was_stuck_loop")
    else:
        target = "specific_autonomous_allowed_but_not_started_by_planner"
        command = "python3 link_autonomous.py '<specific implementation prompt>' --max-iterations 1"
        reasons.append("specific_prompt_required_before_autonomous")

    if not raw_prompt:
        reasons.append("no_prompt_supplied")

    broad_refusal = route["route"] == "audit_fastpath" and any(
        reason in route.get("reasons", [])
        for reason in [
            "broad_prompt_guard_routed_to_audit",
            "prompt_read_only_detected",
            "ui_audit_only_true",
        ]
    )

    return {
        "planner": "link_progress_planner",
        "repo": repo,
        "prompt": raw_prompt,
        "route": route,
        "broad_prompt_refuses_autonomous": bool(broad_refusal),
        "latest_failure_kind": latest_failure,
        "next_target": target,
        "suggested_command": command,
        "reasons": reasons,
        "latest_engine_reports": engine,
        "latest_fanout_reports": fanout,
    }


def print_text(plan: dict[str, Any]) -> None:
    repo = plan["repo"]
    route = plan["route"]

    print("LINK PROGRESS PLANNER")
    print(f"HEAD: {repo.get('head')}")
    print(f"safe-link-latest: {repo.get('safe_link_latest')}")
    print(f"dirty: {repo.get('dirty')}")

    if repo.get("dirty_files"):
        print("dirty files:")
        for item in repo["dirty_files"]:
            print(f"- {item}")

    print()
    print(f"route: {route.get('route')}")
    print(f"runner: {route.get('runner')}")
    print(f"confidence: {route.get('confidence')}")
    print("route reasons:")
    for reason in route.get("reasons", []):
        print(f"- {reason}")

    print()
    print(f"broad prompt refuses autonomous: {plan.get('broad_prompt_refuses_autonomous')}")
    print(f"latest failure kind: {plan.get('latest_failure_kind')}")
    print(f"next target: {plan.get('next_target')}")
    print(f"suggested command: {plan.get('suggested_command')}")

    print()
    print("planner reasons:")
    for reason in plan.get("reasons", []):
        print(f"- {reason}")

    print()
    print("latest engine reports:")
    for report in plan.get("latest_engine_reports", [])[:5]:
        print(f"- {report.get('run_id')} | {report.get('status')} | {report.get('phase')} | {report.get('failure_type')} | {report.get('path')}")

    print()
    print("latest fanout reports:")
    for report in plan.get("latest_fanout_reports", [])[:5]:
        print(f"- {report.get('run_id')} | {report.get('summary_path')} | {report.get('path')}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", default="", help="Prompt to classify before choosing next safe action.")
    ap.add_argument("--audit-only", action="store_true", help="Force audit route.")
    ap.add_argument("--json", action="store_true", help="Emit JSON.")
    args = ap.parse_args()

    plan = choose_next_action(args.prompt, audit_only=args.audit_only)

    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print_text(plan)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
