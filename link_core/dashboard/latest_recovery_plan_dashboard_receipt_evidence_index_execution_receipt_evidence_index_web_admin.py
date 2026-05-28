#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin route OK"

EXECUTION_RECEIPT_EVIDENCE_INDEX_WEB_ADMIN_TRIGGERS = (
    "latest recovery plan dashboard receipt evidence index execution receipt evidence index",
    "latest rollback plan dashboard receipt evidence index execution receipt evidence index",
    "latest recovery receipt evidence index execution receipt evidence index",
    "latest rollback receipt evidence index execution receipt evidence index",
    "show latest recovery plan dashboard receipt evidence index execution receipt evidence index",
    "show latest rollback plan dashboard receipt evidence index execution receipt evidence index",
    "latest evidence index execution receipt evidence index",
    "receipt evidence index execution receipt evidence index",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return " json " in text or text.strip().endswith(" json") or "--json" in text


def prompt_matches_execution_receipt_evidence_index(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(trigger in text for trigger in EXECUTION_RECEIPT_EVIDENCE_INDEX_WEB_ADMIN_TRIGGERS)


def build_execution_receipt_evidence_index_web_admin_response(
    prompt: str,
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index import (
        build_execution_receipt_evidence_index,
        render_execution_receipt_evidence_index,
    )

    if not prompt_matches_execution_receipt_evidence_index(prompt):
        return {
            "matched": False,
            "ok": False,
            "non_destructive": True,
            "reason": "prompt_not_matched",
        }

    index = build_execution_receipt_evidence_index(receipt_dir, limit=limit)
    html_card = render_execution_receipt_evidence_index(index)
    json_requested = wants_json(prompt)

    command = [
        "python3",
        "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index.py",
        "--json" if json_requested else "--html",
    ]

    return {
        "matched": True,
        "ok": True,
        "non_destructive": True,
        "json_requested": json_requested,
        "command": command,
        "html": html_card,
        "index": index,
    }


def latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_command(
    prompt: str,
) -> list[str] | None:
    if not prompt_matches_execution_receipt_evidence_index(prompt):
        return None

    command = [
        "python3",
        "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index.py",
    ]
    command.append("--json" if wants_json(prompt) else "--html")
    return command


def render_response_summary(response: dict[str, Any]) -> str:
    if not response.get("matched"):
        return "No matching web admin route."

    index = response.get("index") if isinstance(response.get("index"), dict) else {}
    latest = index.get("latest") if isinstance(index.get("latest"), dict) else {}

    receipt_count = html.escape(str(index.get("receipt_count", 0)))
    shown_count = html.escape(str(index.get("shown_count", 0)))
    latest_name = html.escape(str(latest.get("name", "none")))

    return (
        "Latest recovery plan dashboard receipt evidence index execution receipt evidence index route"
        f"\nmatched: {response.get('matched')}"
        f"\nok: {response.get('ok')}"
        f"\nreceipt_count: {receipt_count}"
        f"\nshown_count: {shown_count}"
        f"\nlatest: {latest_name}"
        f"\ncommand: {' '.join(response.get('command', []))}"
    )


def validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index import (
            write_sample_execution_receipts,
        )

        write_sample_execution_receipts(root)

        prompt = "show latest recovery plan dashboard receipt evidence index execution receipt evidence index"
        response = build_execution_receipt_evidence_index_web_admin_response(prompt, root)
        json_response = build_execution_receipt_evidence_index_web_admin_response(prompt + " json", root)
        command = latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_command(prompt)
        miss = latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_command(
            "show something unrelated"
        )

        if response.get("matched") is not True:
            problems.append("route_did_not_match")
        if response.get("ok") is not True:
            problems.append("route_not_ok")
        if response.get("non_destructive") is not True:
            problems.append("route_must_be_non_destructive")
        if json_response.get("json_requested") is not True:
            problems.append("json_detection_failed")
        if not isinstance(command, list) or "--html" not in command:
            problems.append("html_command_wrong")
        json_command = json_response.get("command")
        if not isinstance(json_command, list) or "--json" not in json_command:
            problems.append("json_command_wrong")
        if miss is not None:
            problems.append("unrelated_prompt_matched")
        index = response.get("index")
        if not isinstance(index, dict):
            problems.append("index_missing")
        elif index.get("receipt_count") != 2:
            problems.append("index_receipt_count_wrong")
        html_card = str(response.get("html", ""))
        if "execution receipt evidence index" not in html_card.lower():
            problems.append("html_marker_missing")

        forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
        for item in forbidden:
            if item in html_card.lower():
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Web admin route for latest recovery receipt evidence index execution receipt evidence index."
    )
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_route()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt evidence index web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt) or "show latest recovery plan dashboard receipt evidence index execution receipt evidence index"
    if args.json and " json" not in prompt.lower():
        prompt += " json"

    response = build_execution_receipt_evidence_index_web_admin_response(
        prompt,
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(render_response_summary(response))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
