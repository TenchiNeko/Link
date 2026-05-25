#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_web_admin import (
    WORKER_DASHBOARD_WEB_ADMIN_VERSION,
    build_worker_dashboard_web_response,
    render_worker_dashboard_web_response,
    worker_dashboard_web_admin_command,
)


WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION = "LU96-worker-dashboard-web-admin-integration-v1"


def worker_dashboard_web_admin_dispatch(
    prompt: str,
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    command = worker_dashboard_web_admin_command(prompt)

    payload: dict[str, Any] = {
        "receipt_version": WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION,
        "route_version": WORKER_DASHBOARD_WEB_ADMIN_VERSION,
        "prompt": prompt,
        "repo": str(root),
        "handled": bool(command),
        "non_destructive": True,
        "write_requested": bool(write),
        "command": command,
        "route": "worker_dashboard_web_admin" if command else "",
        "ok": False,
    }

    if not command:
        payload["error"] = "prompt did not match worker dashboard web-admin route"
        return payload

    response = build_worker_dashboard_web_response(prompt=prompt, root=root, write=write)
    rendered = render_worker_dashboard_web_response(response)

    payload.update(
        {
            "ok": bool(response.get("ok")) and response.get("non_destructive") is True,
            "response": response,
            "rendered": rendered,
        }
    )
    return payload


def render_worker_dashboard_web_admin_dispatch(payload: dict[str, Any]) -> str:
    rendered = payload.get("rendered", "")
    if payload.get("handled") and "link-worker-dashboard-card" in rendered:
        return rendered

    escaped = html.escape(json.dumps(payload, indent=2, sort_keys=True))
    return (
        '<section class="link-worker-dashboard-web-admin-integration" '
        f'data-version="{html.escape(str(payload.get("receipt_version", "")))}">'
        "<h2>Worker Dashboard Web Admin Integration</h2>"
        f"<pre>{escaped}</pre>"
        "</section>"
    )


def validate_worker_dashboard_web_admin_integration() -> list[str]:
    problems: list[str] = []

    payload = worker_dashboard_web_admin_dispatch("show worker dashboard html pending approval")
    if payload.get("receipt_version") != WORKER_DASHBOARD_WEB_ADMIN_INTEGRATION_VERSION:
        problems.append("integration receipt version mismatch")

    if payload.get("route_version") != WORKER_DASHBOARD_WEB_ADMIN_VERSION:
        problems.append("route version mismatch")

    if payload.get("handled") is not True:
        problems.append("worker dashboard prompt was not handled")

    if payload.get("ok") is not True:
        problems.append(f"worker dashboard dispatch failed: {payload}")

    if payload.get("non_destructive") is not True:
        problems.append("dispatch payload must be non-destructive")

    if payload.get("write_requested") is not False:
        problems.append("default dispatch should not request writes")

    rendered = render_worker_dashboard_web_admin_dispatch(payload)
    if "link-worker-dashboard-card" not in rendered:
        problems.append("dispatch render missing worker dashboard card marker")

    miss = worker_dashboard_web_admin_dispatch("show recovery plan dashboard")
    if miss.get("handled"):
        problems.append("unrelated dashboard prompt should not be handled by worker dashboard integration")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in rendered:
            problems.append(f"rendered integration contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatch Link worker dashboard web-admin prompts.")
    parser.add_argument("prompt", nargs="*", help="Prompt to dispatch.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["web", "json"], default="web")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip() or "show worker dashboard"
    payload = worker_dashboard_web_admin_dispatch(prompt=prompt, root=Path(args.root))

    if args.format == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_worker_dashboard_web_admin_dispatch(payload))

    return 0 if payload.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
