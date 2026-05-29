#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index web admin integration OK"


def route_latest_recovery_receipt_evidence_index_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_evidence_index_response(
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index_web_admin import (
        build_latest_recovery_plan_dashboard_receipt_evidence_index_web_response,
    )

    response = build_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
        receipt_dir,
        limit=limit,
    )
    return {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration",
        "status": "ok",
        "ok": True,
        "non_destructive": True,
        "integrated_response": response,
        "receipt_count": response.get("receipt_count", 0),
        "shown_count": response.get("shown_count", 0),
    }


def self_test() -> list[str]:
    problems: list[str] = []

    html_command = route_latest_recovery_receipt_evidence_index_prompt(
        "show latest recovery plan dashboard receipt evidence index"
    )
    json_command = route_latest_recovery_receipt_evidence_index_prompt(
        "show latest recovery plan dashboard receipt evidence index as json"
    )
    base_command = route_latest_recovery_receipt_evidence_index_prompt(
        "show recovery plan dashboard"
    )

    if not html_command:
        problems.append("integrated_html_command_missing")
    elif "latest_recovery_plan_dashboard_receipt_evidence_index.py" not in html_command:
        problems.append("integrated_html_command_wrong_target")
    elif "--html" not in html_command:
        problems.append("integrated_html_command_missing_html_flag")

    if not json_command:
        problems.append("integrated_json_command_missing")
    elif "latest_recovery_plan_dashboard_receipt_evidence_index.py" not in json_command:
        problems.append("integrated_json_command_wrong_target")
    elif "--json" not in json_command:
        problems.append("integrated_json_command_missing_json_flag")

    if not base_command:
        problems.append("base_recovery_dashboard_command_broken")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        from latest_recovery_plan_dashboard_receipt_evidence_index import write_sample_receipts
        from latest_recovery_plan_dashboard_receipt_evidence_index_web_admin import (
            render_latest_recovery_plan_dashboard_receipt_evidence_index_web_response,
        )

        write_sample_receipts(root)
        response = build_integrated_evidence_index_response(root, limit=10)
        integrated = response.get("integrated_response")
        rendered = render_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
            integrated if isinstance(integrated, dict) else {}
        )

    if response.get("status") != "ok":
        problems.append("integrated_response_status_not_ok")
    if response.get("non_destructive") is not True:
        problems.append("integrated_response_must_be_non_destructive")
    if response.get("receipt_count") != 2:
        problems.append("integrated_receipt_count_wrong")
    if "receipt evidence index" not in rendered.lower():
        problems.append("integrated_render_marker_missing")

    forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
    for item in forbidden:
        if item in rendered.lower():
            problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integration checks for latest recovery dashboard receipt evidence index web admin route."
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("latest recovery plan dashboard receipt evidence index web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    if args.prompt:
        command = route_latest_recovery_receipt_evidence_index_prompt(args.prompt)
        if args.json:
            print(json.dumps({"command": command}, indent=2, sort_keys=True))
        else:
            print(command)
        return 0

    response = build_integrated_evidence_index_response()
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
