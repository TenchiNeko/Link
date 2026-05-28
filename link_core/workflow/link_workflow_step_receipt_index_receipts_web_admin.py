#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MARKER = "workflow step execution receipt index execution receipt web admin route OK"

WORKFLOW_STEP_RECEIPT_INDEX_EXECUTION_RECEIPT_TRIGGERS = (
    "workflow step execution receipt index execution receipt",
    "show workflow step execution receipt index execution receipt",
    "latest workflow step execution receipt index execution receipt",
    "workflow step receipt index execution receipt",
    "show workflow step receipt index execution receipt",
    "step execution receipt index execution receipt",
    "show step execution receipt index execution receipt",
    "workflow step receipt index receipts",
    "show workflow step receipt index receipts",
)


def wants_json(prompt: str) -> bool:
    lowered = prompt.lower()
    return " json" in f" {lowered} " or lowered.strip().endswith("json")


def parse_limit(prompt: str, default: int = 5) -> int:
    match = re.search(r"\blimit\s+(\d+)\b", prompt.lower())
    if not match:
        return default
    value = int(match.group(1))
    return max(1, min(value, 50))


def matches_workflow_step_receipt_index_execution_receipt_prompt(prompt: str) -> bool:
    lowered = " ".join(prompt.lower().split())
    return any(trigger in lowered for trigger in WORKFLOW_STEP_RECEIPT_INDEX_EXECUTION_RECEIPT_TRIGGERS)


def command_for_workflow_step_receipt_index_execution_receipt(
    prompt: str,
    *,
    receipt_dir: Path | None = None,
    source_receipt_dir: Path | None = None,
    no_write: bool = True,
) -> list[str] | None:
    if not matches_workflow_step_receipt_index_execution_receipt_prompt(prompt):
        return None

    cmd = [
        "python3",
        "link_workflow_step_receipt_index_receipts.py",
        "--json",
        "--limit",
        str(parse_limit(prompt)),
    ]

    if no_write:
        cmd.append("--no-write")

    if source_receipt_dir is not None:
        cmd.extend(["--source-receipt-dir", str(source_receipt_dir)])

    if receipt_dir is not None:
        cmd.extend(["--receipt-dir", str(receipt_dir)])

    return cmd


def parse_json_output(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        parsed = json.loads(text[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("JSON output was not an object")
    return parsed


def fallback_html(receipt: dict[str, Any]) -> str:
    summary = receipt.get("summary") or {}
    receipt_path = html.escape(str(receipt.get("receipt_path", "")))
    status = html.escape(str(receipt.get("status", "unknown")))
    ok = "yes" if receipt.get("ok") else "no"
    count = html.escape(str(summary.get("receipt_count", 0)))
    shown = html.escape(str(summary.get("shown_count", 0)))
    latest = html.escape(str(summary.get("latest", "")))
    latest_status = html.escape(str(summary.get("latest_status", "")))

    parts = [
        '<section class="workflow-step-receipt-index-execution-receipt-admin">',
        "<h2>Workflow step execution receipt index execution receipt</h2>",
        f"<p>Status: <strong>{status}</strong> · ok: {ok}</p>",
        f"<p>Indexed step receipts: <strong>{count}</strong> · shown: {shown}</p>",
    ]

    if latest:
        parts.append(f"<p>Latest: <code>{latest}</code> ({latest_status or 'unknown'})</p>")
    else:
        parts.append("<p>No latest workflow step execution receipt was found.</p>")

    if receipt_path:
        parts.append(f"<p>Receipt path: <code>{receipt_path}</code></p>")

    parts.append("</section>")
    return "".join(parts)


def handle_workflow_step_receipt_index_execution_receipt_prompt(
    prompt: str,
    *,
    receipt_dir: Path | None = None,
    source_receipt_dir: Path | None = None,
) -> dict[str, Any]:
    cmd = command_for_workflow_step_receipt_index_execution_receipt(
        prompt,
        receipt_dir=receipt_dir,
        source_receipt_dir=source_receipt_dir,
        no_write=True,
    )

    if cmd is None:
        return {
            "matched": False,
            "ok": False,
            "non_destructive": True,
            "json_requested": wants_json(prompt),
            "command": [],
            "receipt": {},
            "html": "",
            "problems": ["prompt did not match workflow step receipt index execution receipt route"],
        }

    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    problems: list[str] = []
    receipt: dict[str, Any] = {}

    if proc.returncode != 0:
        problems.append(f"route command failed with return code {proc.returncode}")

    try:
        receipt = parse_json_output(proc.stdout)
    except Exception as exc:
        problems.append(f"could not parse route JSON: {exc}")

    if receipt and receipt.get("kind") != "link_workflow_step_receipt_index_execution_receipt":
        problems.append(f"unexpected receipt kind: {receipt.get('kind')!r}")

    rendered_html = str(receipt.get("html") or fallback_html(receipt))

    return {
        "matched": True,
        "ok": not problems,
        "non_destructive": True,
        "json_requested": wants_json(prompt),
        "command": cmd,
        "receipt": receipt,
        "html": rendered_html,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "returncode": proc.returncode,
        "problems": problems,
    }


def validate_workflow_step_receipt_index_execution_receipt_web_admin_route() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)

        command = command_for_workflow_step_receipt_index_execution_receipt(
            "show workflow step execution receipt index execution receipt json limit 5",
            receipt_dir=tmpdir,
            source_receipt_dir=tmpdir,
        )
        if command is None:
            problems.append("matching prompt did not return command")
        else:
            joined = " ".join(command)
            if "link_workflow_step_receipt_index_receipts.py" not in joined:
                problems.append("command did not target execution receipt module")
            if "--json" not in command:
                problems.append("command did not request JSON")
            if "--no-write" not in command:
                problems.append("route command should be non-writing by default")

        nonmatch = command_for_workflow_step_receipt_index_execution_receipt("show recovery dashboard")
        if nonmatch is not None:
            problems.append("unrelated prompt unexpectedly matched LU46 route")

        response = handle_workflow_step_receipt_index_execution_receipt_prompt(
            "show workflow step execution receipt index execution receipt json limit 5",
            receipt_dir=tmpdir,
            source_receipt_dir=tmpdir,
        )

        if not response.get("matched"):
            problems.append("handler did not mark matching prompt as matched")
        if not response.get("ok"):
            problems.append(f"handler did not return ok: {response.get('problems')}")
        if not response.get("non_destructive"):
            problems.append("handler did not mark response non_destructive")
        if not response.get("json_requested"):
            problems.append("handler did not detect JSON request")

        receipt = response.get("receipt") or {}
        if receipt.get("kind") != "link_workflow_step_receipt_index_execution_receipt":
            problems.append("handler did not return expected receipt kind")
        if receipt.get("receipt_path"):
            problems.append("web route should use --no-write and not create receipt_path")
        if "workflow-step-receipt-index-execution-receipt" not in response.get("html", ""):
            problems.append("handler HTML did not include expected section class")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Web-admin route for workflow step receipt index execution receipt.")
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--receipt-dir", type=Path, default=None)
    parser.add_argument("--source-receipt-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index_execution_receipt_web_admin_route()
        if problems:
            print("workflow step execution receipt index execution receipt web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt).strip() or "show workflow step execution receipt index execution receipt json limit 5"
    response = handle_workflow_step_receipt_index_execution_receipt_prompt(
        prompt,
        receipt_dir=args.receipt_dir,
        source_receipt_dir=args.source_receipt_dir,
    )

    if args.json or wants_json(prompt):
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
