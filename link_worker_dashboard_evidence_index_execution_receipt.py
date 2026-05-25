#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_evidence_index_web_admin_integration import (
    WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION,
    render_worker_dashboard_evidence_index_web_admin_dispatch,
    validate_worker_dashboard_evidence_index_web_admin_integration,
    worker_dashboard_evidence_index_web_admin_dispatch,
)


WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_VERSION = (
    "LU101-worker-dashboard-evidence-index-execution-receipt-v1"
)


def build_worker_dashboard_evidence_index_execution_receipt(
    prompt: str = "show worker dashboard evidence index html",
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    generated = dt.datetime.now().replace(microsecond=0).isoformat()

    integration_problems = validate_worker_dashboard_evidence_index_web_admin_integration()
    dispatch = worker_dashboard_evidence_index_web_admin_dispatch(
        prompt=prompt,
        root=root,
        write=write,
    )
    rendered = render_worker_dashboard_evidence_index_web_admin_dispatch(dispatch)

    response = dispatch.get("response") if isinstance(dispatch.get("response"), dict) else {}
    card = response.get("index") if isinstance(response.get("index"), dict) else {}
    latest = card.get("latest") if isinstance(card.get("latest"), dict) else {}

    required_markers = [
        "link-worker-dashboard-evidence-index-web-admin-integration",
        "link-worker-dashboard-evidence-index-web-admin",
        "link-worker-dashboard-evidence-index",
    ]
    marker_results = {
        marker: marker in rendered
        for marker in required_markers
    }

    command = dispatch.get("command")
    if not isinstance(command, list):
        command = []

    checks = [
        {
            "name": "integration validation",
            "ok": not integration_problems,
            "detail": integration_problems,
        },
        {
            "name": "dispatch handled",
            "ok": dispatch.get("handled") is True,
            "detail": dispatch.get("route"),
        },
        {
            "name": "dispatch ok",
            "ok": dispatch.get("ok") is True,
            "detail": dispatch.get("response_version"),
        },
        {
            "name": "non destructive",
            "ok": dispatch.get("non_destructive") is True and dispatch.get("write_requested") is bool(write),
            "detail": {"write_requested": bool(write)},
        },
        {
            "name": "marker coverage",
            "ok": all(marker_results.values()),
            "detail": marker_results,
        },
    ]

    ok = all(bool(check.get("ok")) for check in checks)

    return {
        "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_VERSION,
        "generated": generated,
        "repo": str(root),
        "prompt": prompt,
        "status": "passed" if ok else "failed",
        "ok": ok,
        "non_destructive": True,
        "write_requested": bool(write),
        "integration_version": WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION,
        "dispatch_receipt_version": dispatch.get("receipt_version"),
        "dispatch_route": dispatch.get("route"),
        "dispatch_handled": dispatch.get("handled"),
        "dispatch_ok": dispatch.get("ok"),
        "command": command,
        "checks": checks,
        "markers": marker_results,
        "summary": {
            "worker_profile": latest.get("worker_profile"),
            "current_task": latest.get("current_task"),
            "status": latest.get("status"),
            "pending_approval": latest.get("pending_approval"),
            "latest_test": latest.get("latest_test"),
            "branch": latest.get("branch"),
            "head": latest.get("head"),
            "working_tree_clean": latest.get("working_tree_clean"),
            "entries_count": card.get("entries_count"),
            "stored_entries_count": card.get("stored_entries_count"),
            "errors_count": card.get("errors_count"),
        },
        "rendered_preview": rendered[:2000],
    }


def validate_worker_dashboard_evidence_index_execution_receipt() -> list[str]:
    problems: list[str] = []
    receipt = build_worker_dashboard_evidence_index_execution_receipt(write=False)

    if receipt.get("receipt_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_EXECUTION_RECEIPT_VERSION:
        problems.append("execution receipt version mismatch")

    if receipt.get("ok") is not True:
        problems.append(f"execution receipt should pass: {receipt}")

    if receipt.get("status") != "passed":
        problems.append(f"execution receipt status should be passed: {receipt.get('status')}")

    if receipt.get("non_destructive") is not True:
        problems.append("execution receipt must be non-destructive")

    if receipt.get("write_requested") is not False:
        problems.append("execution receipt smoke should not request writes")

    if receipt.get("dispatch_handled") is not True:
        problems.append("execution receipt dispatch should be handled")

    if receipt.get("dispatch_ok") is not True:
        problems.append("execution receipt dispatch should be ok")

    markers = receipt.get("markers")
    if not isinstance(markers, dict) or not all(markers.values()):
        problems.append(f"execution receipt marker coverage failed: {markers}")

    checks = receipt.get("checks")
    if not isinstance(checks, list) or not checks:
        problems.append("execution receipt checks missing")
    elif not all(check.get("ok") for check in checks if isinstance(check, dict)):
        problems.append(f"execution receipt checks failed: {checks}")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    rendered = str(receipt.get("rendered_preview", ""))
    for item in forbidden:
        if item in rendered:
            problems.append(f"execution receipt rendered forbidden text: {item}")

    return problems


def render_worker_dashboard_evidence_index_execution_receipt_markdown(receipt: dict[str, Any]) -> str:
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
    checks = receipt.get("checks") if isinstance(receipt.get("checks"), list) else []
    markers = receipt.get("markers") if isinstance(receipt.get("markers"), dict) else {}

    lines = [
        "# Link Worker Dashboard Evidence Index Execution Receipt",
        "",
        f"Version: `{receipt.get('receipt_version')}`",
        f"Generated: {receipt.get('generated')}",
        f"Status: **{receipt.get('status')}**",
        f"Prompt: {receipt.get('prompt')}",
        f"Route: `{receipt.get('dispatch_route')}`",
        f"Dispatch handled: **{receipt.get('dispatch_handled')}**",
        f"Dispatch OK: **{receipt.get('dispatch_ok')}**",
        f"Non-destructive: **{'yes' if receipt.get('non_destructive') else 'no'}**",
        "",
        "## Dashboard Summary",
        "",
        f"- Worker profile: `{summary.get('worker_profile')}`",
        f"- Current task: {summary.get('current_task')}",
        f"- Status: **{summary.get('status')}**",
        f"- Pending approval: **{summary.get('pending_approval')}**",
        f"- Latest test: `{summary.get('latest_test')}`",
        f"- Branch: `{summary.get('branch')}`",
        f"- HEAD: `{summary.get('head')}`",
        f"- Working tree clean: **{summary.get('working_tree_clean')}**",
        f"- Entries: **{summary.get('entries_count')}**",
        "",
        "## Checks",
        "",
    ]

    for check in checks:
        if isinstance(check, dict):
            icon = "PASS" if check.get("ok") else "FAIL"
            lines.append(f"- {icon}: {check.get('name')}")

    lines.extend(["", "## Markers", ""])
    for marker, ok in markers.items():
        icon = "PASS" if ok else "FAIL"
        lines.append(f"- {icon}: `{marker}`")

    return "\n".join(lines).rstrip() + "\n"


def render_worker_dashboard_evidence_index_execution_receipt_html(receipt: dict[str, Any]) -> str:
    markdown = render_worker_dashboard_evidence_index_execution_receipt_markdown(receipt)
    return (
        '<section class="link-worker-dashboard-evidence-index-execution-receipt" '
        f'data-version="{html.escape(str(receipt.get("receipt_version", "")))}">'
        "<h2>Link Worker Dashboard Evidence Index Execution Receipt</h2>"
        f"<pre>{html.escape(markdown)}</pre>"
        "</section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a Link worker dashboard evidence index execution receipt."
    )
    parser.add_argument("prompt", nargs="*", default=["show", "worker", "dashboard", "evidence", "index", "html"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    receipt = build_worker_dashboard_evidence_index_execution_receipt(
        prompt=prompt,
        root=Path(args.root),
        write=args.write,
    )

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_worker_dashboard_evidence_index_execution_receipt_html(receipt))
    else:
        print(render_worker_dashboard_evidence_index_execution_receipt_markdown(receipt))

    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
