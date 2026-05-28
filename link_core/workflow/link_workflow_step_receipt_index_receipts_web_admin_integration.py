#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MARKER = "workflow step execution receipt index execution receipt web admin integration OK"


def normalize_command(command: Any) -> list[str] | None:
    if command is None:
        return None
    if isinstance(command, str):
        return shlex.split(command)
    if isinstance(command, (list, tuple)):
        return [str(part) for part in command]
    return None


def route_workflow_step_receipt_index_execution_receipt_prompt(prompt: str) -> Any:
    from recovery_plan_dashboard_web_admin import recovery_plan_dashboard_web_admin_command

    return recovery_plan_dashboard_web_admin_command(prompt)


def build_integrated_workflow_step_receipt_index_execution_receipt_response(
    receipt_dir: Path | None = None,
    *,
    prompt: str = "show workflow step execution receipt index execution receipt json limit 5",
    limit: int | None = None,
) -> dict[str, Any]:
    routed = route_workflow_step_receipt_index_execution_receipt_prompt(prompt)
    command = normalize_command(routed)

    if command is None:
        command = [
            "python3",
            "link_workflow_step_receipt_index_receipts.py",
            "--json",
            "--limit",
            str(limit or 5),
            "--no-write",
        ]

    if receipt_dir is not None and "--receipt-dir" not in command:
        command.extend(["--receipt-dir", str(receipt_dir)])

    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
    )

    receipt: dict[str, Any]
    try:
        receipt = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        receipt = {
            "ok": False,
            "status": "invalid-json",
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }

    ok = proc.returncode == 0 and bool(receipt.get("ok", False))

    return {
        "ok": ok,
        "matched": routed is not None,
        "non_destructive": True,
        "command": command,
        "raw_command": routed,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "receipt": receipt,
        "html": receipt.get("html", ""),
        "json_requested": "--json" in command,
        "no_write": "--no-write" in command,
    }


def validate_workflow_step_receipt_index_execution_receipt_web_admin_integration() -> list[str]:
    problems: list[str] = []

    prompt = "show workflow step execution receipt index execution receipt json limit 5"
    routed = route_workflow_step_receipt_index_execution_receipt_prompt(prompt)
    command = normalize_command(routed)

    if command is None:
        problems.append("main dispatcher did not route LU47 prompt")
    else:
        command_text = " ".join(command)
        if "link_workflow_step_receipt_index_receipts.py" not in command_text:
            problems.append(f"main dispatcher routed to wrong command: {routed}")
        if "--json" not in command:
            problems.append("main dispatcher command did not include --json")
        if "--no-write" not in command:
            problems.append("main dispatcher command did not preserve no-write web route behavior")

    with tempfile.TemporaryDirectory() as td:
        response = build_integrated_workflow_step_receipt_index_execution_receipt_response(
            Path(td),
            prompt=prompt,
            limit=5,
        )

    if not response.get("ok"):
        problems.append("integrated LU47 response was not ok")
    if not response.get("matched"):
        problems.append("integrated LU47 response did not use dispatcher match")
    if not response.get("json_requested"):
        problems.append("integrated LU47 response was not JSON routed")
    if not response.get("no_write"):
        problems.append("integrated LU47 response did not preserve --no-write")
    if response.get("receipt", {}).get("kind") != "link_workflow_step_receipt_index_execution_receipt":
        problems.append("integrated LU47 receipt kind mismatch")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--receipt-dir", default="")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index_execution_receipt_web_admin_integration()
        if problems:
            print("workflow step execution receipt index execution receipt web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None
    response = build_integrated_workflow_step_receipt_index_execution_receipt_response(
        receipt_dir,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(MARKER if response.get("ok") else "workflow step execution receipt index execution receipt web admin integration FAILED")
        if response.get("html"):
            print(response["html"])
        else:
            print(json.dumps(response, indent=2, sort_keys=True))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
