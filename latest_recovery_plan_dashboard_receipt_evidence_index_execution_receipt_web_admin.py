#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "latest recovery plan dashboard receipt evidence index execution receipt web admin route OK"

EXECUTION_RECEIPT_WEB_ADMIN_TRIGGERS = (
    "latest recovery plan dashboard receipt evidence index execution receipt",
    "latest rollback plan dashboard receipt evidence index execution receipt",
    "latest recovery receipt evidence index execution receipt",
    "latest rollback receipt evidence index execution receipt",
    "show latest recovery plan dashboard receipt evidence index execution receipt",
    "show latest rollback plan dashboard receipt evidence index execution receipt",
    "latest evidence index execution receipt",
    "receipt evidence index execution receipt",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return " json " in text or " as json " in text or text.strip().endswith("json")


def matches_execution_receipt_web_admin_prompt(prompt: str) -> bool:
    text = (prompt or "").lower()
    return any(trigger in text for trigger in EXECUTION_RECEIPT_WEB_ADMIN_TRIGGERS)


def build_execution_receipt_command(prompt: str) -> list[str] | None:
    if not matches_execution_receipt_web_admin_prompt(prompt):
        return None

    command = [
        "python3",
        "latest_recovery_plan_dashboard_receipt_evidence_index_receipts.py",
        "--write",
    ]

    if wants_json(prompt):
        command.append("--json")

    return command


def build_execution_receipt_web_response(
    prompt: str,
    receipt_source_dir: Path | None = None,
    receipt_dir: Path | None = None,
    *,
    write: bool = True,
    as_json: bool | None = None,
) -> dict[str, Any]:
    import latest_recovery_plan_dashboard_receipt_evidence_index_receipts as receipts_mod

    builder = getattr(
        receipts_mod,
        "build_latest_recovery_receipt_evidence_index_execution_receipt",
        None,
    ) or getattr(
        receipts_mod,
        "build_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt",
        None,
    )

    if builder is None:
        raise RuntimeError("could not find LU29 execution receipt builder")

    json_requested = wants_json(prompt) if as_json is None else bool(as_json)

    receipt = builder(
        receipt_source_dir,
        receipt_dir=receipt_dir,
        write=write,
    )

    return {
        "ok": bool(receipt.get("ok")),
        "status": receipt.get("status", "unknown"),
        "matched": matches_execution_receipt_web_admin_prompt(prompt),
        "json_requested": json_requested,
        "command": build_execution_receipt_command(prompt),
        "receipt": receipt,
        "html": render_execution_receipt_web_response(receipt),
        "non_destructive": True,
    }


def render_execution_receipt_web_response(receipt: dict[str, Any]) -> str:
    status = html.escape(str(receipt.get("status", "unknown")))
    ok = "yes" if receipt.get("ok") else "no"
    receipt_path = html.escape(str(receipt.get("receipt_path", "")))

    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    receipt_count = html.escape(str(summary.get("receipt_count", 0)))
    shown_count = html.escape(str(summary.get("shown_count", 0)))

    latest = summary.get("latest") if isinstance(summary.get("latest"), dict) else {}
    latest_name = html.escape(str(latest.get("name", "none"))) if latest else "none"

    return (
        '<section class="latest-recovery-receipt-evidence-index-execution-receipt">'
        "<h2>Latest recovery plan dashboard receipt evidence index execution receipt</h2>"
        f"<p>Status: <strong>{status}</strong></p>"
        f"<p>OK: {ok}</p>"
        f"<p>Indexed receipts: {receipt_count}</p>"
        f"<p>Shown receipts: {shown_count}</p>"
        f"<p>Latest indexed receipt: <code>{latest_name}</code></p>"
        f"<p>Receipt path: <code>{receipt_path or 'not written'}</code></p>"
        "</section>"
    )


def validate_execution_receipt_web_admin_route() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        out = root / "out"

        from latest_recovery_plan_dashboard_receipt_evidence_index import write_sample_receipts

        write_sample_receipts(source)

        prompt = "show latest recovery plan dashboard receipt evidence index execution receipt json"
        command = build_execution_receipt_command(prompt)
        response = build_execution_receipt_web_response(
            prompt,
            receipt_source_dir=source,
            receipt_dir=out,
            write=True,
        )

        if not matches_execution_receipt_web_admin_prompt(prompt):
            problems.append("prompt_did_not_match")
        if command is None:
            problems.append("command_missing")
        elif "latest_recovery_plan_dashboard_receipt_evidence_index_receipts.py" not in command:
            problems.append("wrong_command_target")
        if command and "--write" not in command:
            problems.append("write_flag_missing")
        if command and "--json" not in command:
            problems.append("json_flag_missing")
        if response.get("non_destructive") is not True:
            problems.append("response_must_be_non_destructive")
        if response.get("ok") is not True:
            problems.append("response_not_ok")
        if "execution receipt" not in str(response.get("html", "")).lower():
            problems.append("html_marker_missing")

        receipt = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
        receipt_path = receipt.get("receipt_path")
        if not receipt_path:
            problems.append("receipt_path_missing")
        elif not Path(str(receipt_path)).exists():
            problems.append("receipt_file_missing")

        forbidden = ("<form", "rm -rf", "reset --hard", "git clean")
        blob = json.dumps(response, sort_keys=True).lower()
        for item in forbidden:
            if item in blob:
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Route latest recovery receipt evidence index execution receipt web admin prompts."
    )
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--receipt-source-dir")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_execution_receipt_web_admin_route()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt) if args.prompt else "latest recovery plan dashboard receipt evidence index execution receipt"

    response = build_execution_receipt_web_response(
        prompt,
        receipt_source_dir=Path(args.receipt_source_dir) if args.receipt_source_dir else None,
        receipt_dir=Path(args.receipt_dir) if args.receipt_dir else None,
        write=True,
        as_json=args.json,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    elif args.html:
        print(response["html"])
    else:
        command = response.get("command")
        print("Latest recovery plan dashboard receipt evidence index execution receipt web admin route")
        print(f"matched: {response.get('matched')}")
        print(f"status: {response.get('status')}")
        print(f"ok: {response.get('ok')}")
        if command:
            print("command: " + " ".join(command))
        receipt = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
        if receipt.get("receipt_path"):
            print(f"receipt_path: {receipt.get('receipt_path')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
