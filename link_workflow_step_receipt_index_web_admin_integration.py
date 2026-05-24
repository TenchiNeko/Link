#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "workflow step execution receipt index web admin integration OK"


def route_workflow_step_receipt_index_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_workflow_step_receipt_index_response(
    receipt_dir: Path | None = None,
    *,
    prompt: str = "show workflow step execution receipt index json limit 5",
    limit: int | None = None,
) -> dict[str, Any]:
    from link_workflow_step_receipt_index_web_admin import (
        build_workflow_step_receipt_index_web_admin_response,
    )

    if limit is not None and " limit " not in f" {prompt.lower()} ":
        prompt = f"{prompt} limit {limit}"

    return build_workflow_step_receipt_index_web_admin_response(prompt, receipt_dir)


def validate_workflow_step_receipt_index_web_admin_integration() -> list[str]:
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

        direct = build_integrated_workflow_step_receipt_index_response(
            receipt_dir,
            prompt="show workflow step execution receipt index json limit 5",
        )

        if not direct.get("ok"):
            problems.append("direct integrated response should be ok")
        if not direct.get("matched"):
            problems.append("direct integrated response should be matched")

        index = direct.get("index")
        if not isinstance(index, dict):
            problems.append("direct integrated response missing index")
        else:
            if index.get("receipt_count") != 1:
                problems.append("expected one workflow step receipt in temp index")
            latest = index.get("latest")
            if not isinstance(latest, dict):
                problems.append("expected latest workflow step receipt in temp index")
            elif latest.get("workflow_id") != "lu41-workflow-step-executor":
                problems.append("latest workflow id mismatch")

        rendered = str(direct.get("html") or "")
        if "Workflow step execution receipt index" not in rendered:
            problems.append("direct HTML missing title")

    routed = route_workflow_step_receipt_index_prompt(
        "show workflow step execution receipt index json limit 5"
    )
    if not routed:
        problems.append("main web admin route returned no output")
    else:
        joined = "\n".join(routed)
        if "link_workflow_step_receipt_index" not in joined:
            problems.append("main web admin route missing workflow step receipt index payload")
        if "workflow step execution receipt index" not in joined.lower():
            problems.append("main web admin route missing workflow step receipt title")

    # Unrelated prompts may legitimately return None from the main dispatcher.
    # LU44 only owns the workflow step execution receipt index routing contract.

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Workflow step execution receipt index web admin integration."
    )
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index_web_admin_integration()
        if problems:
            print("workflow step execution receipt index web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    response = build_integrated_workflow_step_receipt_index_response(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
