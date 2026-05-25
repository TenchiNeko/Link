#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_evidence_index_execution_receipt import (
    WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_VERSION,
    build_worker_dashboard_evidence_index_execution_receipt,
    render_worker_dashboard_evidence_index_execution_receipt_html,
    render_worker_dashboard_evidence_index_execution_receipt_markdown,
    validate_worker_dashboard_evidence_index_execution_receipt,
)


WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_WEB_ADMIN_VERSION = (
    "LU102-worker-dashboard-evidence-index-execution-receipt-web-admin-route-v1"
)


def infer_format(prompt: str) -> str:
    text = (prompt or "").lower()
    if "json" in text:
        return "json"
    if "html" in text or "card" in text:
        return "html"
    return "markdown"


def worker_dashboard_evidence_index_execution_receipt_web_admin_command(prompt: str) -> list[str]:
    text = (prompt or "").lower()
    if "worker dashboard" not in text:
        return []
    if "evidence index" not in text:
        return []
    if "execution receipt" not in text and "receipt" not in text:
        return []

    fmt = infer_format(prompt)
    return [
        "python3",
        "link_worker_dashboard_evidence_index_execution_receipt.py",
        "show",
        "worker",
        "dashboard",
        "evidence",
        "index",
        "html",
        "--format",
        fmt,
    ]


def build_worker_dashboard_evidence_index_execution_receipt_web_response(
    prompt: str = "show worker dashboard evidence index execution receipt html",
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    fmt = infer_format(prompt)
    command = worker_dashboard_evidence_index_execution_receipt_web_admin_command(prompt)

    receipt = build_worker_dashboard_evidence_index_execution_receipt(
        prompt="show worker dashboard evidence index html",
        root=root,
        write=write,
    )
    problems = validate_worker_dashboard_evidence_index_execution_receipt()

    if fmt == "json":
        rendered = json.dumps(receipt, indent=2, sort_keys=True)
    elif fmt == "html":
        rendered = render_worker_dashboard_evidence_index_execution_receipt_html(receipt)
    else:
        rendered = render_worker_dashboard_evidence_index_execution_receipt_markdown(receipt)

    ok = not problems and receipt.get("ok") is True and bool(command)

    return {
        "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_WEB_ADMIN_VERSION,
        "repo": str(root),
        "prompt": prompt,
        "format": fmt,
        "ok": ok,
        "non_destructive": True,
        "write_requested": bool(write),
        "command": command,
        "receipt_version_inner": WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_VERSION,
        "receipt": receipt,
        "validation_problems": problems,
        "rendered": rendered,
    }


def render_worker_dashboard_evidence_index_execution_receipt_web_response(
    response: dict[str, Any],
) -> str:
    rendered = str(response.get("rendered", ""))
    fmt = response.get("format")

    if fmt == "html":
        body = rendered
    else:
        body = f"<pre>{html.escape(rendered)}</pre>"

    return (
        '<section class="link-worker-dashboard-evidence-index-execution-receipt-web-admin" '
        f'data-version="{html.escape(str(response.get("receipt_version", "")))}">'
        "<h2>Worker Dashboard Evidence Index Execution Receipt</h2>"
        f"{body}"
        "</section>"
    )


def validate_worker_dashboard_evidence_index_execution_receipt_web_admin_route() -> list[str]:
    problems: list[str] = []

    command = worker_dashboard_evidence_index_execution_receipt_web_admin_command(
        "show worker dashboard evidence index execution receipt json"
    )
    expected = [
        "python3",
        "link_worker_dashboard_evidence_index_execution_receipt.py",
        "show",
        "worker",
        "dashboard",
        "evidence",
        "index",
        "html",
        "--format",
        "json",
    ]
    if command != expected:
        problems.append(f"unexpected worker dashboard evidence index execution receipt route: {command}")

    miss = worker_dashboard_evidence_index_execution_receipt_web_admin_command(
        "show unrelated dashboard thing"
    )
    if miss:
        problems.append(f"route should not match unrelated prompt: {miss}")

    response = build_worker_dashboard_evidence_index_execution_receipt_web_response(
        "show worker dashboard evidence index execution receipt html",
        write=False,
    )
    if response.get("receipt_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_WEB_ADMIN_VERSION:
        problems.append("web-admin response version mismatch")

    if response.get("ok") is not True:
        problems.append(f"web-admin response should be ok: {response}")

    if response.get("non_destructive") is not True:
        problems.append("web-admin response must be non-destructive")

    rendered = render_worker_dashboard_evidence_index_execution_receipt_web_response(response)
    required = [
        "link-worker-dashboard-evidence-index-execution-receipt-web-admin",
        "link-worker-dashboard-evidence-index-execution-receipt",
    ]
    for marker in required:
        if marker not in rendered:
            problems.append(f"rendered web-admin response missing marker: {marker}")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in rendered:
            problems.append(f"rendered web-admin response contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the Link worker dashboard evidence index execution receipt web-admin route."
    )
    parser.add_argument("prompt", nargs="*", default=["show", "worker", "dashboard", "evidence", "index", "execution", "receipt", "html"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["auto", "markdown", "json", "html"], default="auto")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    if args.format != "auto":
        prompt = f"{prompt} {args.format}"

    response = build_worker_dashboard_evidence_index_execution_receipt_web_response(
        prompt=prompt,
        root=Path(args.root),
        write=args.write,
    )

    if response.get("format") == "json":
        print(json.dumps(response, indent=2, sort_keys=True))
    elif response.get("format") == "html":
        print(render_worker_dashboard_evidence_index_execution_receipt_web_response(response))
    else:
        print(str(response.get("rendered", "")))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
