#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_evidence_index import (
    WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION,
    build_worker_dashboard_evidence_index,
    render_worker_dashboard_evidence_index_html,
    render_worker_dashboard_evidence_index_markdown,
    validate_worker_dashboard_evidence_index,
)


WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION = (
    "LU99-worker-dashboard-evidence-index-web-admin-route-v1"
)


def infer_format(prompt: str) -> str:
    text = (prompt or "").lower()
    if "json" in text:
        return "json"
    if "html" in text or "card" in text:
        return "html"
    return "markdown"


def worker_dashboard_evidence_index_web_admin_command(prompt: str) -> list[str]:
    text = (prompt or "").lower()
    needles = [
        "worker dashboard evidence index",
        "dashboard evidence index",
        "worker evidence index",
        "show worker dashboard evidence",
        "latest worker dashboard evidence",
    ]

    if not any(needle in text for needle in needles):
        return []

    fmt = infer_format(text)
    return ["python3", "link_worker_dashboard_evidence_index.py", "--format", fmt]


def build_worker_dashboard_evidence_index_web_response(
    prompt: str = "show worker dashboard evidence index",
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    fmt = infer_format(prompt)
    index = build_worker_dashboard_evidence_index(root=root, include_live_preview=True)
    validation_problems = validate_worker_dashboard_evidence_index()

    if fmt == "json":
        rendered = json.dumps(index, indent=2, sort_keys=True)
    elif fmt == "html":
        rendered = render_worker_dashboard_evidence_index_html(index)
    else:
        rendered = render_worker_dashboard_evidence_index_markdown(index)

    return {
        "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION,
        "index_version": WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION,
        "prompt": prompt,
        "command": worker_dashboard_evidence_index_web_admin_command(prompt),
        "format": fmt,
        "repo": str(root),
        "ok": not validation_problems,
        "validation_problems": validation_problems,
        "non_destructive": True,
        "write_requested": bool(write),
        "index": index,
        "rendered": rendered,
    }


def render_worker_dashboard_evidence_index_web_response(response: dict[str, Any]) -> str:
    rendered = str(response.get("rendered", ""))
    fmt = response.get("format")

    if fmt == "html":
        body = rendered
    else:
        body = f"<pre>{html.escape(rendered)}</pre>"

    return (
        '<section class="link-worker-dashboard-evidence-index-web-admin" '
        f'data-version="{html.escape(str(response.get("receipt_version", "")))}">'
        "<h2>Worker Dashboard Evidence Index</h2>"
        f"{body}"
        "</section>"
    )


def validate_worker_dashboard_evidence_index_web_admin_route() -> list[str]:
    problems: list[str] = []

    command = worker_dashboard_evidence_index_web_admin_command(
        "show worker dashboard evidence index json"
    )
    expected = ["python3", "link_worker_dashboard_evidence_index.py", "--format", "json"]
    if command != expected:
        problems.append(f"json route mismatch: {command}")

    html_command = worker_dashboard_evidence_index_web_admin_command(
        "show worker dashboard evidence index html"
    )
    expected_html = ["python3", "link_worker_dashboard_evidence_index.py", "--format", "html"]
    if html_command != expected_html:
        problems.append(f"html route mismatch: {html_command}")

    miss = worker_dashboard_evidence_index_web_admin_command("show recovery plan dashboard")
    if miss:
        problems.append(f"route should ignore unrelated prompt: {miss}")

    response = build_worker_dashboard_evidence_index_web_response(
        "show worker dashboard evidence index html",
        write=False,
    )
    if response.get("receipt_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION:
        problems.append("web-admin receipt version mismatch")

    if response.get("index_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION:
        problems.append("index version mismatch")

    if response.get("non_destructive") is not True:
        problems.append("web-admin evidence index route must be non-destructive")

    if response.get("ok") is not True:
        problems.append(f"web-admin evidence index response not OK: {response.get('validation_problems')}")

    index = response.get("index", {})
    if not isinstance(index, dict) or index.get("entry_count", 0) < 1:
        problems.append(f"web-admin evidence index missing entries: {index}")

    html_response = render_worker_dashboard_evidence_index_web_response(response)
    if "link-worker-dashboard-evidence-index-web-admin" not in html_response:
        problems.append("web-admin wrapper marker missing")

    if "link-worker-dashboard-evidence-index" not in html_response:
        problems.append("inner evidence index marker missing")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in html_response:
            problems.append(f"web-admin evidence index contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Route Link worker dashboard evidence index web-admin prompts.")
    parser.add_argument("prompt", nargs="*", default=["show", "worker", "dashboard", "evidence", "index"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    if args.format:
        prompt = f"{prompt} {args.format}"

    command = worker_dashboard_evidence_index_web_admin_command(prompt)
    if not command:
        payload = {
            "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION,
            "handled": False,
            "prompt": prompt,
            "non_destructive": True,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 2

    response = build_worker_dashboard_evidence_index_web_response(
        prompt=prompt,
        root=Path(args.root),
        write=args.write,
    )

    if response["format"] == "json":
        print(json.dumps(response, indent=2, sort_keys=True))
    elif response["format"] == "html":
        print(render_worker_dashboard_evidence_index_web_response(response))
    else:
        print(response["rendered"], end="")

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
