#!/usr/bin/env python3
from __future__ import annotations

"""
Link Loop controller.

Purpose:
- Detect repeated autonomous stuck-loop failures.
- Avoid blindly rerunning the same failing full-engine prompt.
- Write a deterministic handoff when the autonomous path should stop/pivot.
"""

import argparse
import hashlib
import json
import re
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
RUN_ROOT = ROOT / ".agents" / "engine_runs"
HANDOFF_ROOT = ROOT / ".agents" / "reports"

POLICY_MARKER = "[LINK_ENGINE_POLICY_V2]"


def normalize_prompt(prompt: str) -> str:
    text = str(prompt or "")

    if POLICY_MARKER in text:
        marker = "NON-TRIVIAL CHANGE RULE:"
        idx = text.find(marker)
        if idx != -1:
            tail = text[idx:]
            parts = tail.split("\n\n", 1)
            if len(parts) == 2:
                text = parts[1]

    return " ".join(text.strip().split())


def prompt_hash(prompt: str) -> str:
    normalized = normalize_prompt(prompt)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def report_paths(root: Path = ROOT, limit: int = 80) -> list[Path]:
    run_root = root / ".agents" / "engine_runs"
    if not run_root.exists():
        return []
    paths = [
        p
        for p in run_root.glob("*/engine_report.json")
        if p.parent.name != "selftest"
    ]
    return sorted(paths, key=lambda p: p.stat().st_mtime, reverse=True)[:limit]


def event_text(report: dict[str, Any]) -> str:
    chunks: list[str] = []
    for event in report.get("events", []) or []:
        if not isinstance(event, dict):
            continue
        for key in ("phase", "level", "kind", "title", "message", "detail", "raw"):
            value = event.get(key)
            if value:
                chunks.append(str(value))
    for key in ("failure_type", "phase", "status", "last_successful_observation"):
        value = report.get(key)
        if value:
            chunks.append(str(value))
    return "\n".join(chunks).lower()


def report_prompt_hash(report: dict[str, Any]) -> str | None:
    existing = report.get("prompt_hash")
    if existing:
        return str(existing)

    prompt = report.get("prompt")
    if prompt:
        return prompt_hash(str(prompt))

    return None


def changed_files(report: dict[str, Any]) -> list[str]:
    value = report.get("changed_files") or []
    if isinstance(value, list):
        return [str(v) for v in value]
    return []


def is_stuck_loop_report(report: dict[str, Any]) -> bool:
    text = event_text(report)
    return (
        report.get("failure_type") == "stuck_loop"
        or "stuck loop" in text
        or "same tool calls repeated" in text
        or "same commands repeated" in text
        or "agent hit max rounds" in text
    )


def is_failed_report(report: dict[str, Any]) -> bool:
    status = str(report.get("status") or "").lower()
    exit_code = report.get("exit_code")
    return status in {"failed", "restored", "blocked"} or exit_code not in {0, None}


def find_prior_same_prompt_loop(root: Path, prompt: str, limit: int = 80) -> tuple[Path, dict[str, Any]] | None:
    target_hash = prompt_hash(prompt)

    for path in report_paths(root, limit=limit):
        report = read_json(path)
        if not report:
            continue

        if report.get("run_id", "").startswith("audit-"):
            continue

        if report_prompt_hash(report) != target_hash:
            continue

        if is_failed_report(report) and is_stuck_loop_report(report) and not changed_files(report):
            return path, report

    return None


def evaluate_loop_risk(root: Path, prompt: str) -> dict[str, Any]:
    target_hash = prompt_hash(prompt)
    prior = find_prior_same_prompt_loop(root, prompt)

    if prior:
        path, report = prior
        return {
            "action": "stop_with_handoff",
            "reason": "same prompt previously hit a stuck loop with no changed files",
            "prompt_hash": target_hash,
            "prior_report": str(path),
            "prior_run_id": report.get("run_id"),
            "recommendation": [
                "Do not rerun the same full autonomous path blindly.",
                "Switch to a narrower deterministic patch.",
                "Ask for one missing file/section if needed.",
                "Use audit-only for investigation or micro/surgical patch for small writes.",
            ],
        }

    return {
        "action": "allow",
        "reason": "no prior same-prompt no-change stuck loop found",
        "prompt_hash": target_hash,
        "recommendation": [],
    }


def write_loop_handoff(root: Path, prompt: str, decision: dict[str, Any], child_report: str | None = None) -> Path:
    handoff_root = root / ".agents" / "reports"
    handoff_root.mkdir(parents=True, exist_ok=True)

    path = handoff_root / f"handoff-loop-{uuid.uuid4().hex[:8]}.md"
    recommendations = decision.get("recommendation") or []

    body = [
        "# Link loop-controller handoff",
        "",
        f"- prompt_hash: `{decision.get('prompt_hash')}`",
        f"- reason: {decision.get('reason')}",
        f"- prior_report: {decision.get('prior_report') or 'none'}",
        f"- child_report: {child_report or 'none'}",
        "",
        "## Recommended next action",
        "",
    ]

    for item in recommendations:
        body.append(f"- {item}")

    body.extend([
        "",
        "## Prompt",
        "",
        "```text",
        normalize_prompt(prompt),
        "```",
        "",
    ])

    path.write_text("\n".join(body), encoding="utf-8")
    return path


def write_loop_report(
    root: Path,
    *,
    run_id: str,
    prompt: str,
    status: str,
    phase: str,
    exit_code: int,
    events: list[dict[str, Any]],
    child_report: str | None = None,
    handoff: str | None = None,
    failure_type: str | None = None,
) -> Path:
    run_dir = root / ".agents" / "engine_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    report = {
        "run_id": run_id,
        "status": status,
        "phase": phase,
        "started_at": events[0]["ts"] if events else time.time(),
        "ended_at": time.time(),
        "exit_code": exit_code,
        "prompt_hash": prompt_hash(prompt),
        "prompt": normalize_prompt(prompt),
        "changed_files": [],
        "child_report": child_report,
        "handoff": handoff,
        "failure_type": failure_type or ("unknown" if exit_code else None),
        "events": events,
        "report_path": str(run_dir / "engine_report.json"),
    }

    path = run_dir / "engine_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Link loop controller")
    parser.add_argument("command", choices=["audit", "decision"], nargs="?", default="audit")
    parser.add_argument("--prompt-file", required=True)
    args = parser.parse_args()

    prompt = Path(args.prompt_file).read_text(encoding="utf-8")
    decision = evaluate_loop_risk(ROOT, prompt)
    print(json.dumps(decision, indent=2))


if __name__ == "__main__":
    main()
