#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
from typing import Any

from link_task_patch_runner import build_plan


CONCISE_RECEIPT_VERSION = "LU92-concise-task-receipt-v1"


def compact_head(head: str) -> str:
    head = (head or "").strip()
    if not head:
        return ""
    return head if len(head) <= 96 else head[:93] + "..."


def build_concise_task_receipt(root: Path, goal: str) -> dict[str, Any]:
    plan = build_plan(root, goal)
    classification = plan.get("goal_classification", {})
    tests = plan.get("recommended_tests", [])
    gates = plan.get("required_gates", [])
    blockers = plan.get("blockers", [])

    if blockers:
        next_action = "Resolve blockers before patching."
    elif plan.get("working_tree_clean"):
        next_action = "Proceed with the smallest useful patch, then run recommended checks."
    else:
        next_action = "Review dirty working tree before patching."

    return {
        "receipt_version": CONCISE_RECEIPT_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": plan.get("repo", str(root)),
        "goal": plan.get("goal", goal),
        "branch": plan.get("branch", ""),
        "head": plan.get("head", ""),
        "working_tree_clean": bool(plan.get("working_tree_clean")),
        "readiness": {
            "grade": plan.get("readiness_grade"),
            "score": plan.get("readiness_score"),
        },
        "risk_level": classification.get("risk_level"),
        "suggested_worker_profile": classification.get("suggested_worker_profile"),
        "categories": classification.get("categories", []),
        "blockers": blockers,
        "gate_count": len(gates),
        "test_count": len(tests),
        "top_tests": tests[:4],
        "next_action": next_action,
    }


def render_concise_task_receipt(receipt: dict[str, Any]) -> str:
    readiness = receipt.get("readiness", {})
    clean = "yes" if receipt.get("working_tree_clean") else "no"
    blockers = receipt.get("blockers", [])
    categories = receipt.get("categories", [])
    tests = receipt.get("top_tests", [])

    lines: list[str] = [
        "# Link Concise Task Receipt",
        "",
        f"Goal: {receipt.get('goal', '')}",
        f"Branch: `{receipt.get('branch', '')}`",
        f"HEAD: `{compact_head(receipt.get('head', ''))}`",
        f"Working tree clean: **{clean}**",
        f"Readiness: **{readiness.get('grade')} / {readiness.get('score')}**",
        f"Risk: **{receipt.get('risk_level')}**",
        f"Worker: `{receipt.get('suggested_worker_profile')}`",
        f"Categories: {', '.join(f'`{x}`' for x in categories) if categories else '`none`'}",
        f"Gates: **{receipt.get('gate_count', 0)}**",
        f"Tests: **{receipt.get('test_count', 0)}**",
        "",
        "## Top Checks",
    ]

    if tests:
        lines.extend(f"- `{test}`" for test in tests)
    else:
        lines.append("- none")

    lines.extend(["", "## Blockers"])
    if blockers:
        lines.extend(f"- {item}" for item in blockers)
    else:
        lines.append("- none")

    lines.extend(["", "## Next"])
    lines.append(receipt.get("next_action", ""))

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a concise Link task receipt.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--root", default=".", help="repository root, default current directory")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output", "--receipt-out", dest="receipt_out", help="optional path to write receipt")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    data = build_concise_task_receipt(root, args.goal)

    if args.format == "json":
        text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    else:
        text = render_concise_task_receipt(data)

    if args.receipt_out:
        Path(args.receipt_out).write_text(text, encoding="utf-8")

    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
