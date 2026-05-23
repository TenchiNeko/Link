#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin integration OK"


def route_latest_recovery_receipt_evidence_index_execution_receipt_evidence_index_prompt(
    prompt: str,
) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_execution_receipt_evidence_index_response(
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
    json_requested: bool = False,
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin import (
        build_execution_receipt_evidence_index_web_admin_response,
    )

    prompt = "show latest recovery plan dashboard receipt evidence index execution receipt evidence index"
    if json_requested:
        prompt += " json"

    return build_execution_receipt_evidence_index_web_admin_response(
        prompt,
        receipt_dir,
        limit=limit,
    )


def validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index import (
            write_sample_execution_receipts,
        )

        write_sample_execution_receipts(root)

        prompt = "show latest recovery plan dashboard receipt evidence index execution receipt evidence index"
        json_prompt = prompt + " json"

        command = route_latest_recovery_receipt_evidence_index_execution_receipt_evidence_index_prompt(prompt)
        json_command = route_latest_recovery_receipt_evidence_index_execution_receipt_evidence_index_prompt(json_prompt)

        response = build_integrated_execution_receipt_evidence_index_response(root)
        json_response = build_integrated_execution_receipt_evidence_index_response(
            root,
            json_requested=True,
        )

        if not isinstance(command, list):
            problems.append("integrated_command_missing")
        elif "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index.py" not in command:
            problems.append("integrated_command_wrong_module")
        elif "--html" not in command:
            problems.append("integrated_command_should_default_html")

        if not isinstance(json_command, list):
            problems.append("integrated_json_command_missing")
        elif "--json" not in json_command:
            problems.append("integrated_json_command_missing_json_flag")

        if response.get("matched") is not True:
            problems.append("integrated_response_not_matched")
        if response.get("ok") is not True:
            problems.append("integrated_response_not_ok")
        if response.get("non_destructive") is not True:
            problems.append("integrated_response_must_be_non_destructive")
        if json_response.get("json_requested") is not True:
            problems.append("integrated_json_response_not_requested")

        index = response.get("index")
        if not isinstance(index, dict):
            problems.append("integrated_index_missing")
        elif index.get("receipt_count") != 2:
            problems.append("integrated_index_receipt_count_wrong")

        html_card = str(response.get("html", ""))
        if "execution receipt evidence index" not in html_card.lower():
            problems.append("integrated_html_marker_missing")

        forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
        for item in forbidden:
            if item in html_card.lower():
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integration check for latest recovery receipt evidence index execution receipt evidence index web admin route."
    )
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_integration()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    response = build_integrated_execution_receipt_evidence_index_response(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
        json_requested=args.json,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html") or response)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
