#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index execution receipt web admin integration OK"


def route_latest_recovery_receipt_evidence_index_execution_receipt_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_execution_receipt_response(
    receipt_source_dir: Path | None = None,
    receipt_dir: Path | None = None,
    *,
    prompt: str = "latest recovery plan dashboard receipt evidence index execution receipt json",
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin import (
        build_execution_receipt_command,
        build_execution_receipt_web_response,
    )

    command = build_execution_receipt_command(prompt)
    response = build_execution_receipt_web_response(
        prompt,
        receipt_source_dir=receipt_source_dir,
        receipt_dir=receipt_dir,
        write=True,
    )

    return {
        "ok": bool(response.get("ok")),
        "status": response.get("status", "unknown"),
        "command": command,
        "response": response,
        "non_destructive": True,
    }


def validate_latest_recovery_receipt_evidence_index_execution_receipt_web_admin_integration() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        out = root / "out"

        from latest_recovery_plan_dashboard_receipt_evidence_index import write_sample_receipts

        write_sample_receipts(source)

        prompt = "show latest recovery plan dashboard receipt evidence index execution receipt json"

        routed = route_latest_recovery_receipt_evidence_index_execution_receipt_prompt(prompt)
        integrated = build_integrated_execution_receipt_response(
            source,
            out,
            prompt=prompt,
        )

        if not routed:
            problems.append("integrated_route_missing")
        elif "latest_recovery_plan_dashboard_receipt_evidence_index_receipts.py" not in routed:
            problems.append("integrated_route_wrong_target")
        if routed and "--write" not in routed:
            problems.append("integrated_route_missing_write")
        if routed and "--json" not in routed:
            problems.append("integrated_route_missing_json")
        if integrated.get("non_destructive") is not True:
            problems.append("integrated_response_must_be_non_destructive")
        if integrated.get("ok") is not True:
            problems.append("integrated_response_not_ok")

        response = integrated.get("response") if isinstance(integrated.get("response"), dict) else {}
        receipt = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
        receipt_path = receipt.get("receipt_path")
        if not receipt_path:
            problems.append("receipt_path_missing")
        elif not Path(str(receipt_path)).exists():
            problems.append("receipt_file_missing")

        blob = json.dumps(
            {
                "routed": routed,
                "integrated": integrated,
            },
            sort_keys=True,
        ).lower()
        forbidden = ("rm -rf", "reset --hard", "git clean", "<form")
        for item in forbidden:
            if item in blob:
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate latest recovery receipt evidence index execution receipt web admin integration."
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("prompt", nargs="*", default=[])
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_receipt_evidence_index_execution_receipt_web_admin_integration()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt) if args.prompt else "latest recovery plan dashboard receipt evidence index execution receipt json"
    routed = route_latest_recovery_receipt_evidence_index_execution_receipt_prompt(prompt)

    if args.json:
        print(json.dumps({"command": routed}, indent=2, sort_keys=True))
    else:
        print("Latest recovery plan dashboard receipt evidence index execution receipt web admin integration")
        print(f"command: {' '.join(routed) if routed else 'none'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
