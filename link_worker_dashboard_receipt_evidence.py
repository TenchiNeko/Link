#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_web_admin_integration import (
    WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION,
    worker_dashboard_web_admin_dispatch,
)


WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION = "LU97-worker-dashboard-receipt-evidence-v1"


def _find_first(obj: Any, names: set[str]) -> Any:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in names:
                return value
        for value in obj.values():
            found = _find_first(value, names)
            if found not in (None, "", [], {}):
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_first(item, names)
            if found not in (None, "", [], {}):
                return found
    return None


def _compact(value: Any, limit: int = 220) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def build_worker_dashboard_receipt_evidence(
    root: Path,
    prompt: str = "show worker dashboard html pending approval",
    write: bool = False,
    output: Path | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    dispatch = worker_dashboard_web_admin_dispatch(prompt=prompt, root=root, write=False)
    response = dispatch.get("response", {}) if isinstance(dispatch.get("response"), dict) else {}
    rendered = str(dispatch.get("rendered", ""))

    worker_profile = _find_first(dispatch, {"worker_profile", "profile"}) or ""
    current_task = _find_first(dispatch, {"current_task", "task"}) or ""
    status = _find_first(dispatch, {"status"}) or ""
    pending_approval = _find_first(dispatch, {"pending_approval"})
    latest_test = _find_first(dispatch, {"latest_test", "latest_test_result"}) or ""
    branch = _find_first(dispatch, {"branch"}) or ""
    head = _find_first(dispatch, {"head"}) or ""
    working_tree_clean = _find_first(dispatch, {"working_tree_clean"})

    evidence: dict[str, Any] = {
        "receipt_version": WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "prompt": prompt,
        "source_integration_version": WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION,
        "dispatch_handled": dispatch.get("handled") is True,
        "dispatch_ok": dispatch.get("ok") is True,
        "non_destructive": dispatch.get("non_destructive") is True,
        "route": dispatch.get("route", ""),
        "command": dispatch.get("command", []),
        "dashboard_marker_present": "link-worker-dashboard-card" in rendered,
        "summary": {
            "worker_profile": _compact(worker_profile),
            "current_task": _compact(current_task),
            "status": _compact(status),
            "pending_approval": pending_approval,
            "latest_test": _compact(latest_test),
            "branch": _compact(branch),
            "head": _compact(head),
            "working_tree_clean": working_tree_clean,
        },
        "evidence": {
            "response_keys": sorted(response.keys()),
            "rendered_excerpt": _compact(rendered, 900),
        },
        "written": False,
        "output": "",
    }

    if write:
        if output is None:
            stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
            output = root / ".link" / "worker-dashboard-evidence" / f"{stamp}-worker-dashboard-evidence.json"
        output = output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        evidence["written"] = True
        evidence["output"] = str(output)

    return evidence


def render_worker_dashboard_receipt_evidence_markdown(evidence: dict[str, Any]) -> str:
    summary = evidence.get("summary", {})
    lines = [
        "# Link Worker Dashboard Receipt Evidence",
        "",
        f"Version: `{evidence.get('receipt_version')}`",
        f"Prompt: {evidence.get('prompt')}",
        f"Route: `{evidence.get('route')}`",
        f"Dispatch handled: **{'yes' if evidence.get('dispatch_handled') else 'no'}**",
        f"Dispatch OK: **{'yes' if evidence.get('dispatch_ok') else 'no'}**",
        f"Non-destructive: **{'yes' if evidence.get('non_destructive') else 'no'}**",
        f"Dashboard marker present: **{'yes' if evidence.get('dashboard_marker_present') else 'no'}**",
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
        "",
        "## Evidence",
        "",
        "- Response keys: " + ", ".join(f"`{x}`" for x in evidence.get("evidence", {}).get("response_keys", [])),
        f"- Written: **{'yes' if evidence.get('written') else 'no'}**",
    ]

    if evidence.get("output"):
        lines.append(f"- Output: `{evidence.get('output')}`")

    return "\n".join(lines).rstrip() + "\n"


def render_worker_dashboard_receipt_evidence_html(evidence: dict[str, Any]) -> str:
    md = render_worker_dashboard_receipt_evidence_markdown(evidence)
    return (
        '<section class="link-worker-dashboard-receipt-evidence" '
        f'data-version="{html.escape(str(evidence.get("receipt_version", "")))}">'
        "<h2>Link Worker Dashboard Receipt Evidence</h2>"
        f"<pre>{html.escape(md)}</pre>"
        "</section>"
    )


def validate_worker_dashboard_receipt_evidence() -> list[str]:
    problems: list[str] = []
    evidence = build_worker_dashboard_receipt_evidence(Path.cwd())

    if evidence.get("receipt_version") != WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION:
        problems.append("receipt evidence version mismatch")

    if evidence.get("source_integration_version") != WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION:
        problems.append("source integration version mismatch")

    if evidence.get("dispatch_handled") is not True:
        problems.append("dashboard dispatch was not handled")

    if evidence.get("dispatch_ok") is not True:
        problems.append(f"dashboard dispatch failed: {evidence}")

    if evidence.get("non_destructive") is not True:
        problems.append("receipt evidence must remain non-destructive by default")

    if evidence.get("dashboard_marker_present") is not True:
        problems.append("dashboard marker missing from evidence source")

    if evidence.get("written") is not False:
        problems.append("default evidence build should not write files")

    rendered = render_worker_dashboard_receipt_evidence_html(evidence)
    if "link-worker-dashboard-receipt-evidence" not in rendered:
        problems.append("HTML evidence marker missing")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in rendered:
            problems.append(f"rendered evidence contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Link worker dashboard receipt evidence.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--prompt", default="show worker dashboard html pending approval")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--write", action="store_true", help="write evidence JSON to disk")
    parser.add_argument("--output", default="", help="optional explicit evidence output path")
    args = parser.parse_args()

    output = Path(args.output) if args.output else None
    evidence = build_worker_dashboard_receipt_evidence(
        root=Path(args.root),
        prompt=args.prompt,
        write=args.write,
        output=output,
    )

    if args.format == "json":
        print(json.dumps(evidence, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_worker_dashboard_receipt_evidence_html(evidence))
    else:
        print(render_worker_dashboard_receipt_evidence_markdown(evidence), end="")

    return 0 if evidence.get("dispatch_ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
