#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


MARKER = "workflow preflight receipt index web admin integration OK"


def route_workflow_preflight_receipt_index_prompt(prompt: str) -> list[str] | None:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_workflow_preflight_receipt_index_response(
    receipt_dir: Path | None = None,
    *,
    prompt: str = "show workflow preflight receipt index json limit 5",
    limit: int | None = None,
    force_json: bool | None = None,
) -> dict[str, Any]:
    from link_workflow_preflight_receipt_index_web_admin import (
        build_workflow_preflight_receipt_index_web_admin_response,
    )

    response = build_workflow_preflight_receipt_index_web_admin_response(
        receipt_dir,
        prompt=prompt,
        limit=limit,
        force_json=force_json,
    )
    response["integrated"] = True
    response["integration_marker"] = MARKER
    return response


def validate_workflow_preflight_receipt_index_web_admin_integration() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        receipt_dir = Path(tmp)
        receipt = {
            "kind": "link_workflow_preflight_execution_receipt",
            "schema_version": 1,
            "workflow_id": "integration-test-workflow",
            "goal": "Test workflow preflight receipt index web admin integration.",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:02+00:00",
            "repo_root": str(receipt_dir),
            "dry_run": False,
            "non_destructive": True,
            "ok": True,
            "status": "ok",
            "checks": [{"id": "repo-clean", "ok": True, "status": "ok"}],
            "summary": {"total": 1, "ok": 1, "failed": 0, "blocked": 0, "optional_failed": 0},
            "problems": [],
            "receipt_path": str(receipt_dir / "workflow-preflight-integration-test.json"),
        }
        (receipt_dir / "workflow-preflight-integration-test.json").write_text(
            json.dumps(receipt),
            encoding="utf-8",
        )

        command = route_workflow_preflight_receipt_index_prompt(
            "show workflow preflight receipt index json limit 3"
        )
        if not command:
            problems.append("expected integrated recovery dashboard route command")
        elif "link_workflow_preflight_receipt_index.py" not in " ".join(command):
            problems.append(f"unexpected integrated command: {command!r}")

        unrelated = route_workflow_preflight_receipt_index_prompt("show latest recovery plan dashboard")
        if unrelated and "link_workflow_preflight_receipt_index.py" in " ".join(unrelated):
            problems.append("unexpected preflight receipt route match for unrelated prompt")

        response = build_integrated_workflow_preflight_receipt_index_response(
            receipt_dir,
            prompt="show workflow preflight receipt index json limit 5",
            force_json=True,
        )
        if not response.get("ok"):
            problems.append("expected ok integrated response")

        if response.get("integrated") is not True:
            problems.append("integrated response missing integrated=true")

        index = response.get("index")
        if not isinstance(index, dict) or index.get("receipt_count") != 1:
            problems.append("expected one indexed integration test receipt")

        rendered = json.dumps(response, sort_keys=True)
        if "integration-test-workflow" not in rendered:
            problems.append("integrated response missing workflow id")

        if MARKER not in rendered:
            problems.append("integrated response missing marker")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Integration validation for workflow preflight receipt index web admin route."
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt", default="show workflow preflight receipt index json limit 5")
    parser.add_argument("--receipt-dir")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_preflight_receipt_index_web_admin_integration()
        if problems:
            print("workflow preflight receipt index web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None
    response = build_integrated_workflow_preflight_receipt_index_response(
        receipt_dir,
        prompt=args.prompt,
        force_json=True if args.json else None,
    )
    print(json.dumps(response, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
