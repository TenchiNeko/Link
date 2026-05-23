#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import tempfile
from pathlib import Path
from typing import Any


MARKER = "workflow preflight receipt index web admin route OK"

WORKFLOW_PREFLIGHT_RECEIPT_INDEX_TRIGGERS = (
    "workflow preflight receipt index",
    "show workflow preflight receipt index",
    "latest workflow preflight receipt index",
    "workflow preflight receipts",
    "show workflow preflight receipts",
    "preflight receipt index",
    "show preflight receipt index",
)


def wants_json(prompt: str) -> bool:
    lowered = prompt.lower()
    return any(token in lowered for token in (" json", "json ", "raw", "machine", "structured"))


def extract_limit(prompt: str, default: int = 10) -> int:
    lowered = prompt.lower()
    patterns = (
        r"\blimit\s+(\d+)\b",
        r"\blast\s+(\d+)\b",
        r"\blatest\s+(\d+)\b",
        r"\bshow\s+(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            try:
                return max(0, min(100, int(match.group(1))))
            except Exception:
                return default
    return default


def matches_workflow_preflight_receipt_index_prompt(prompt: str) -> bool:
    lowered = " ".join(prompt.lower().split())
    return any(trigger in lowered for trigger in WORKFLOW_PREFLIGHT_RECEIPT_INDEX_TRIGGERS)


def workflow_preflight_receipt_index_web_admin_command(prompt: str) -> list[str] | None:
    if not matches_workflow_preflight_receipt_index_prompt(prompt):
        return None

    command = ["python3", "link_workflow_preflight_receipt_index.py"]
    command.append("--json" if wants_json(prompt) else "--html")
    command.extend(["--limit", str(extract_limit(prompt))])
    return command


def build_workflow_preflight_receipt_index_web_admin_response(
    receipt_dir: Path | None = None,
    *,
    prompt: str = "show workflow preflight receipt index",
    limit: int | None = None,
    force_json: bool | None = None,
) -> dict[str, Any]:
    from link_workflow_preflight_receipt_index import (
        build_workflow_preflight_receipt_index,
        render_workflow_preflight_receipt_index_html,
    )

    effective_limit = extract_limit(prompt) if limit is None else limit
    json_requested = wants_json(prompt) if force_json is None else bool(force_json)

    index = build_workflow_preflight_receipt_index(receipt_dir, limit=effective_limit)
    html_output = render_workflow_preflight_receipt_index_html(index)

    command = ["python3", "link_workflow_preflight_receipt_index.py"]
    command.append("--json" if json_requested else "--html")
    command.extend(["--limit", str(effective_limit)])

    return {
        "matched": True,
        "ok": True,
        "non_destructive": True,
        "json_requested": json_requested,
        "command": command,
        "index": index,
        "html": html_output,
    }


def render_web_admin_response(response: dict[str, Any]) -> str:
    if response.get("json_requested"):
        return json.dumps(response, indent=2, sort_keys=True)
    return str(response.get("html", ""))


def validate_workflow_preflight_receipt_index_web_admin_route() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        receipt_dir = Path(tmp)
        receipt = {
            "kind": "link_workflow_preflight_execution_receipt",
            "schema_version": 1,
            "workflow_id": "route-test-workflow",
            "goal": "Test web admin route for workflow preflight receipts.",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
            "repo_root": str(receipt_dir),
            "dry_run": False,
            "non_destructive": True,
            "ok": True,
            "status": "ok",
            "checks": [{"id": "repo-clean", "ok": True, "status": "ok"}],
            "summary": {"total": 1, "ok": 1, "failed": 0, "blocked": 0, "optional_failed": 0},
            "problems": [],
            "receipt_path": str(receipt_dir / "workflow-preflight-route-test.json"),
        }
        (receipt_dir / "workflow-preflight-route-test.json").write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )

        prompt = "show workflow preflight receipt index json limit 5"
        command = workflow_preflight_receipt_index_web_admin_command(prompt)
        if not command:
            problems.append("expected route command for workflow preflight receipt index prompt")
        elif "--json" not in command:
            problems.append("expected json command flag for json prompt")

        if workflow_preflight_receipt_index_web_admin_command("show latest recovery plan") is not None:
            problems.append("unexpected command match for unrelated prompt")

        response = build_workflow_preflight_receipt_index_web_admin_response(
            receipt_dir,
            prompt=prompt,
        )
        if not response.get("ok"):
            problems.append("expected ok response")

        index = response.get("index")
        if not isinstance(index, dict) or index.get("receipt_count") != 1:
            problems.append("expected one indexed test receipt")

        html_output = str(response.get("html", ""))
        if "Workflow preflight receipt index" not in html_output:
            problems.append("html response missing workflow preflight heading")

        rendered = render_web_admin_response(response)
        if "route-test-workflow" not in rendered:
            problems.append("rendered response missing workflow id")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Web admin route for workflow preflight receipt index.")
    parser.add_argument("--prompt", default="show workflow preflight receipt index")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_preflight_receipt_index_web_admin_route()
        if problems:
            print("workflow preflight receipt index web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = args.prompt or "show workflow preflight receipt index"
    if args.json and "json" not in prompt.lower():
        prompt = f"{prompt} json"

    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None
    response = build_workflow_preflight_receipt_index_web_admin_response(
        receipt_dir,
        prompt=prompt,
        limit=args.limit,
        force_json=True if args.json else (False if args.html else None),
    )

    if args.html:
        print(response["html"])
    else:
        print(render_web_admin_response(response))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
