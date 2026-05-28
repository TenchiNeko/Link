#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_evidence_index_web_admin import (
    WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION,
    build_worker_dashboard_evidence_index_web_response,
    render_worker_dashboard_evidence_index_web_response,
    worker_dashboard_evidence_index_web_admin_command,
)


WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION = (
    "LU100-worker-dashboard-evidence-index-web-admin-integration-v1"
)


def worker_dashboard_evidence_index_web_admin_dispatch(
    prompt: str,
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    command = worker_dashboard_evidence_index_web_admin_command(prompt)

    if not command:
        return {
            "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION,
            "route": "",
            "handled": False,
            "ok": False,
            "prompt": prompt,
            "command": [],
            "repo": str(root),
            "non_destructive": True,
            "write_requested": bool(write),
            "response": {},
            "rendered": "",
        }

    response = build_worker_dashboard_evidence_index_web_response(
        prompt=prompt,
        root=root,
        write=write,
    )
    rendered = render_worker_dashboard_evidence_index_web_response(response)

    return {
        "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION,
        "route": "worker_dashboard_evidence_index_web_admin",
        "handled": True,
        "ok": bool(response.get("ok")),
        "prompt": prompt,
        "command": command,
        "repo": str(root),
        "non_destructive": True,
        "write_requested": bool(write),
        "response_version": response.get("receipt_version"),
        "response_format": response.get("format"),
        "response": response,
        "rendered": rendered,
    }


def render_worker_dashboard_evidence_index_web_admin_dispatch(dispatch: dict[str, Any]) -> str:
    if not dispatch.get("handled"):
        return (
            '<section class="link-worker-dashboard-evidence-index-web-admin-integration" '
            f'data-version="{html.escape(str(dispatch.get("receipt_version", "")))}">'
            "<h2>Worker Dashboard Evidence Index Web Admin Integration</h2>"
            "<p>Prompt was not handled by this route.</p>"
            "</section>"
        )

    rendered = str(dispatch.get("rendered", ""))
    return (
        '<section class="link-worker-dashboard-evidence-index-web-admin-integration" '
        f'data-version="{html.escape(str(dispatch.get("receipt_version", "")))}">'
        "<h2>Worker Dashboard Evidence Index Web Admin Integration</h2>"
        f"{rendered}"
        "</section>"
    )


def validate_worker_dashboard_evidence_index_web_admin_integration() -> list[str]:
    problems: list[str] = []

    dispatch = worker_dashboard_evidence_index_web_admin_dispatch(
        "show worker dashboard evidence index html",
        write=False,
    )
    if dispatch.get("receipt_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_INTEGRATION_VERSION:
        problems.append("integration receipt version mismatch")

    if dispatch.get("handled") is not True:
        problems.append(f"dispatch should handle evidence index prompt: {dispatch}")

    if dispatch.get("route") != "worker_dashboard_evidence_index_web_admin":
        problems.append(f"dispatch route mismatch: {dispatch.get('route')}")

    if dispatch.get("response_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_WEB_ADMIN_VERSION:
        problems.append(f"response version mismatch: {dispatch.get('response_version')}")

    if dispatch.get("ok") is not True:
        problems.append(f"dispatch response should be OK: {dispatch}")

    if dispatch.get("non_destructive") is not True:
        problems.append("dispatch must be non-destructive")

    if dispatch.get("write_requested") is not False:
        problems.append("dispatch smoke should not request writes")

    rendered = render_worker_dashboard_evidence_index_web_admin_dispatch(dispatch)
    if "link-worker-dashboard-evidence-index-web-admin-integration" not in rendered:
        problems.append("integration wrapper marker missing")

    if "link-worker-dashboard-evidence-index-web-admin" not in rendered:
        problems.append("web-admin route marker missing")

    if "link-worker-dashboard-evidence-index" not in rendered:
        problems.append("inner evidence index marker missing")

    miss = worker_dashboard_evidence_index_web_admin_dispatch("show recovery plan dashboard")
    if miss.get("handled") is not False:
        problems.append(f"dispatch should ignore unrelated prompt: {miss}")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in rendered:
            problems.append(f"integration rendered forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Dispatch Link worker dashboard evidence index web-admin prompts."
    )
    parser.add_argument("prompt", nargs="*", default=["show", "worker", "dashboard", "evidence", "index"])
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    prompt = " ".join(args.prompt)
    if args.format:
        prompt = f"{prompt} {args.format}"

    dispatch = worker_dashboard_evidence_index_web_admin_dispatch(
        prompt=prompt,
        root=Path(args.root),
        write=args.write,
    )

    if args.format == "json" or "json" in prompt.lower():
        print(json.dumps(dispatch, indent=2, sort_keys=True))
    else:
        print(render_worker_dashboard_evidence_index_web_admin_dispatch(dispatch))

    if not dispatch.get("handled"):
        return 2
    return 0 if dispatch.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
