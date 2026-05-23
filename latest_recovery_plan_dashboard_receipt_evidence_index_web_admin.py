#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index web admin route OK"

EVIDENCE_INDEX_WEB_ADMIN_TRIGGERS = (
    "latest recovery plan dashboard receipt evidence index",
    "latest rollback plan dashboard receipt evidence index",
    "latest recovery dashboard receipt evidence index",
    "latest rollback dashboard receipt evidence index",
    "show latest recovery plan dashboard receipt evidence index",
    "show latest rollback plan dashboard receipt evidence index",
    "latest recovery receipt evidence index",
    "latest rollback receipt evidence index",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(
    prompt: str,
) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    if not any(trigger in text for trigger in EVIDENCE_INDEX_WEB_ADMIN_TRIGGERS):
        return None

    command = ["python3", "latest_recovery_plan_dashboard_receipt_evidence_index.py"]
    if wants_json(text):
        command.append("--json")
    else:
        command.append("--html")
    return command


def build_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index import (
        build_receipt_evidence_index,
        render_receipt_evidence_index,
    )

    index = build_receipt_evidence_index(receipt_dir, limit=limit)
    card_html = render_receipt_evidence_index(index)

    return {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_response",
        "status": "ok",
        "ok": True,
        "non_destructive": True,
        "title": "Latest recovery plan dashboard receipt evidence index",
        "index": index,
        "html": card_html,
        "receipt_count": index.get("receipt_count", 0),
        "shown_count": index.get("shown_count", 0),
    }


def render_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
    response: dict[str, Any],
) -> str:
    if response.get("html"):
        return str(response["html"])

    title = html.escape(str(response.get("title", "Receipt evidence index")))
    status = html.escape(str(response.get("status", "unknown")))
    return (
        '<section class="latest-recovery-receipt-evidence-index-web-admin">'
        f"<h2>{title}</h2>"
        f"<p>Status: {status}</p>"
        "</section>"
    )


def self_test() -> list[str]:
    problems: list[str] = []

    command = latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(
        "show latest recovery plan dashboard receipt evidence index"
    )
    json_command = latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(
        "show latest recovery plan dashboard receipt evidence index as json"
    )
    unrelated = latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(
        "show recovery plan dashboard"
    )

    if not command or "--html" not in command:
        problems.append("evidence_index_html_command_failed")
    if not json_command or "--json" not in json_command:
        problems.append("evidence_index_json_command_failed")
    if unrelated is not None:
        problems.append("unrelated_prompt_should_not_route")

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        from latest_recovery_plan_dashboard_receipt_evidence_index import write_sample_receipts

        write_sample_receipts(root)
        response = build_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
            root,
            limit=10,
        )
        rendered = render_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
            response
        )

    if response.get("status") != "ok":
        problems.append("response_status_not_ok")
    if response.get("non_destructive") is not True:
        problems.append("response_must_be_non_destructive")
    if response.get("receipt_count") != 2:
        problems.append("response_receipt_count_wrong")
    if "receipt evidence index" not in rendered.lower():
        problems.append("rendered_marker_missing")

    forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
    for item in forbidden:
        if item in rendered.lower():
            problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Web admin route for latest recovery dashboard receipt evidence index."
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--prompt")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("latest recovery plan dashboard receipt evidence index web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    if args.prompt is not None:
        command = latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(
            args.prompt
        )
        if args.json:
            print(json.dumps({"command": command}, indent=2, sort_keys=True))
        else:
            print(command)
        return 0

    response = build_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(render_latest_recovery_plan_dashboard_receipt_evidence_index_web_response(response))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
