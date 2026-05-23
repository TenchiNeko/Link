#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any


MARKER = "workflow step execution receipt index web admin route OK"

WORKFLOW_STEP_RECEIPT_INDEX_TRIGGERS = (
    "workflow step execution receipt index",
    "show workflow step execution receipt index",
    "latest workflow step execution receipt index",
    "workflow step receipts",
    "show workflow step receipts",
    "step receipt index",
    "show step receipt index",
    "workflow step execution receipts",
    "show workflow step execution receipts",
)


def wants_json(prompt: str) -> bool:
    lowered = prompt.lower()
    return " json" in f" {lowered} " or lowered.strip().endswith("json")


def parse_limit(prompt: str, default: int = 5) -> int:
    lowered = prompt.lower()
    match = re.search(r"\blimit\s+(\d+)\b", lowered)
    if not match:
        match = re.search(r"\btop\s+(\d+)\b", lowered)
    if not match:
        return default
    try:
        return max(0, min(50, int(match.group(1))))
    except Exception:
        return default


def matches_workflow_step_receipt_index_prompt(prompt: str) -> bool:
    lowered = " ".join(prompt.lower().split())
    return any(trigger in lowered for trigger in WORKFLOW_STEP_RECEIPT_INDEX_TRIGGERS)


def build_workflow_step_receipt_index_web_admin_response(
    prompt: str,
    receipt_dir: Path | None = None,
) -> dict[str, Any]:
    from link_workflow_step_receipt_index import (
        build_workflow_step_receipt_index,
        render_workflow_step_receipt_index_html,
    )

    matched = matches_workflow_step_receipt_index_prompt(prompt)
    limit = parse_limit(prompt)
    index = build_workflow_step_receipt_index(receipt_dir, limit=limit)
    rendered = render_workflow_step_receipt_index_html(index)

    return {
        "ok": True,
        "matched": matched,
        "json_requested": wants_json(prompt),
        "non_destructive": True,
        "command": [
            "python3",
            "link_workflow_step_receipt_index.py",
            "--json",
            "--limit",
            str(limit),
        ],
        "index": index,
        "html": rendered,
    }


def route_workflow_step_receipt_index_prompt(
    prompt: str,
    receipt_dir: Path | None = None,
) -> list[str] | None:
    if not matches_workflow_step_receipt_index_prompt(prompt):
        return None

    response = build_workflow_step_receipt_index_web_admin_response(prompt, receipt_dir)
    if wants_json(prompt):
        return [json.dumps(response, indent=2, sort_keys=True)]

    return [str(response.get("html") or "")]


def validate_workflow_step_receipt_index_web_admin_route() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        receipt_dir = Path(tmp)

        from link_workflow_step_executor import execute_workflow_steps, sample_workflow_spec

        receipt = execute_workflow_steps(
            sample_workflow_spec(),
            dry_run=True,
            receipt_dir=receipt_dir,
            write_receipt=True,
        )

        if not receipt.get("ok"):
            problems.append("expected generated workflow step receipt to be ok")

        prompt = "show workflow step execution receipt index json limit 5"
        response = build_workflow_step_receipt_index_web_admin_response(prompt, receipt_dir)
        if not response.get("ok"):
            problems.append("response should be ok")
        if not response.get("matched"):
            problems.append("response should be matched")
        if not response.get("json_requested"):
            problems.append("response should detect json request")

        index = response.get("index")
        if not isinstance(index, dict):
            problems.append("response index missing")
        else:
            if index.get("receipt_count") != 1:
                problems.append("expected one indexed workflow step receipt")
            latest = index.get("latest")
            if not isinstance(latest, dict):
                problems.append("expected latest workflow step receipt")
            elif latest.get("workflow_id") != "lu41-workflow-step-executor":
                problems.append("latest workflow id mismatch")

        rendered = str(response.get("html") or "")
        if "Workflow step execution receipt index" not in rendered:
            problems.append("HTML missing title")
        if "lu41-workflow-step-executor" not in rendered:
            problems.append("HTML missing workflow id")

        routed = route_workflow_step_receipt_index_prompt(prompt, receipt_dir)
        if not routed:
            problems.append("route returned no output for matching prompt")
        elif "link_workflow_step_receipt_index" not in routed[0]:
            problems.append("json route output missing command/index reference")

        nonmatch = route_workflow_step_receipt_index_prompt("show recovery dashboard", receipt_dir)
        if nonmatch is not None:
            problems.append("route should ignore unrelated prompts")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Workflow step receipt index web admin route.")
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--receipt-dir")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index_web_admin_route()
        if problems:
            print("workflow step execution receipt index web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt) if args.prompt else "show workflow step execution receipt index"
    if args.json and " json" not in f" {prompt.lower()} ":
        prompt = f"{prompt} json"

    response = build_workflow_step_receipt_index_web_admin_response(
        prompt,
        Path(args.receipt_dir) if args.receipt_dir else None,
    )

    if wants_json(prompt):
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response["html"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
