#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path
from typing import Any

from link_worker_dashboard_card import (
    WORKER_DASHBOARD_VERSION,
    build_worker_dashboard_card,
    render_worker_dashboard_html,
    render_worker_dashboard_markdown,
    validate_worker_dashboard_card,
)


WORKER_DASHBOARD_WEB_ADMIN_VERSION = "LU95-worker-dashboard-web-admin-route-v1"


def infer_format(prompt: str) -> str:
    text = (prompt or "").lower()
    if "json" in text:
        return "json"
    if "html" in text or "card" in text:
        return "html"
    return "markdown"


def infer_profile(prompt: str) -> str:
    text = (prompt or "").lower()
    if "read only" in text or "read-only" in text or "auditor" in text:
        return "read_only_auditor"
    if "qa" in text or "review" in text:
        return "qa_worker"
    if "self update" in text or "self-update" in text:
        return "self_update_preflight"
    return "patch_worker"


def infer_pending_approval(prompt: str) -> bool:
    text = (prompt or "").lower()
    return "pending" in text or "approval" in text or "approve" in text


def infer_current_task(prompt: str) -> str:
    text = (prompt or "").strip()
    if not text:
        return "Worker dashboard web admin route"

    lowered = text.lower()
    for marker in ["task:", "current task:", "for task:"]:
        idx = lowered.find(marker)
        if idx != -1:
            candidate = text[idx + len(marker):].strip()
            if candidate:
                return candidate[:160]

    cleaned = re.sub(r"\b(show|open|render|display|worker|dashboard|card|json|html|markdown)\b", " ", text, flags=re.I)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" :-")
    return cleaned[:160] if cleaned else "Worker dashboard web admin route"


def worker_dashboard_web_admin_command(prompt: str) -> list[str]:
    text = (prompt or "").lower()
    wants_dashboard = "worker dashboard" in text or "dashboard worker" in text
    if not wants_dashboard:
        return []

    command = [
        "python3",
        "link_worker_dashboard_card.py",
        "--task",
        infer_current_task(prompt),
        "--profile",
        infer_profile(prompt),
        "--latest-test-result",
        "web-admin route preview",
        "--format",
        infer_format(prompt),
    ]

    if infer_pending_approval(prompt):
        command.insert(-2, "--pending-approval")

    return command


def build_worker_dashboard_web_response(
    prompt: str = "show worker dashboard",
    root: Path | None = None,
    write: bool = False,
) -> dict[str, Any]:
    root = (root or Path.cwd()).resolve()
    command = worker_dashboard_web_admin_command(prompt)

    response: dict[str, Any] = {
        "receipt_version": WORKER_DASHBOARD_WEB_ADMIN_VERSION,
        "card_version": WORKER_DASHBOARD_VERSION,
        "prompt": prompt,
        "repo": str(root),
        "command": command,
        "non_destructive": True,
        "write_requested": bool(write),
        "ok": False,
        "format": infer_format(prompt),
    }

    if not command:
        response["error"] = "prompt did not request worker dashboard"
        return response

    card = build_worker_dashboard_card(
        root,
        current_task=infer_current_task(prompt),
        worker_profile=infer_profile(prompt),
        pending_approval=infer_pending_approval(prompt),
        latest_test_result="web-admin route preview",
    )

    problems = validate_worker_dashboard_card(card)

    if response["format"] == "json":
        rendered = json.dumps(card, indent=2, sort_keys=True)
    elif response["format"] == "html":
        rendered = render_worker_dashboard_html(card)
    else:
        rendered = render_worker_dashboard_markdown(card)

    response.update(
        {
            "ok": not problems,
            "validation_problems": problems,
            "card": card,
            "rendered": rendered,
        }
    )
    return response


def render_worker_dashboard_web_response(response: dict[str, Any]) -> str:
    fmt = response.get("format")
    rendered = response.get("rendered", "")

    if fmt == "html" and "link-worker-dashboard-card" in rendered:
        return rendered

    if fmt == "json":
        escaped = html.escape(rendered)
        return (
            '<section class="link-worker-dashboard-web-admin" '
            f'data-version="{html.escape(str(response.get("receipt_version", "")))}">'
            "<h2>Worker Dashboard JSON</h2>"
            f"<pre>{escaped}</pre>"
            "</section>"
        )

    escaped = html.escape(rendered)
    return (
        '<section class="link-worker-dashboard-web-admin" '
        f'data-version="{html.escape(str(response.get("receipt_version", "")))}">'
        "<h2>Worker Dashboard</h2>"
        f"<pre>{escaped}</pre>"
        "</section>"
    )


def validate_worker_dashboard_web_admin_route() -> list[str]:
    problems: list[str] = []

    markdown_command = worker_dashboard_web_admin_command("show worker dashboard")
    json_command = worker_dashboard_web_admin_command("show worker dashboard json pending approval")
    miss_command = worker_dashboard_web_admin_command("show recovery plan dashboard")

    if not markdown_command:
        problems.append("worker dashboard command did not route")

    if "--format" not in markdown_command or "markdown" not in markdown_command:
        problems.append("markdown worker dashboard route missing format")

    if "--format" not in json_command or "json" not in json_command:
        problems.append("json worker dashboard route missing format")

    if "--pending-approval" not in json_command:
        problems.append("pending approval route missing flag")

    if miss_command:
        problems.append("non-worker dashboard prompt should not route")

    response = build_worker_dashboard_web_response("show worker dashboard html pending approval")
    if not response.get("ok"):
        problems.append(f"web response failed validation: {response.get('validation_problems')}")

    if response.get("non_destructive") is not True:
        problems.append("web response must be non-destructive")

    html_response = render_worker_dashboard_web_response(response)
    if "link-worker-dashboard-card" not in html_response:
        problems.append("rendered web response missing dashboard card marker")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in html_response:
            problems.append(f"rendered web response contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Route Link worker dashboard web-admin prompts.")
    parser.add_argument("prompt", nargs="*", help="Prompt to route.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["web", "json", "command"], default="web")
    args = parser.parse_args()

    prompt = " ".join(args.prompt).strip() or "show worker dashboard"
    response = build_worker_dashboard_web_response(prompt=prompt, root=Path(args.root))

    if args.format == "json":
        print(json.dumps(response, indent=2, sort_keys=True))
    elif args.format == "command":
        print(json.dumps(response.get("command", []), indent=2))
    else:
        print(render_worker_dashboard_web_response(response))

    return 0 if response.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
