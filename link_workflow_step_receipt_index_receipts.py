#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import os
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT_DIR = ROOT / ".link_execution_receipts"
MARKER = "workflow step execution receipt index execution receipt OK"
RECEIPT_KIND = "link_workflow_step_receipt_index_execution_receipt"
SCHEMA_VERSION = 1


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def default_receipt_dir() -> Path:
    configured = os.environ.get("LINK_WORKFLOW_STEP_RECEIPT_INDEX_EXECUTION_RECEIPT_DIR", "")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR


def parse_json_output(text: str) -> Any:
    text = text.strip()
    if not text:
        raise ValueError("empty JSON output")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def run_step_receipt_index(source_receipt_dir: Path, limit: int) -> dict[str, Any]:
    cmd = [
        "python3",
        str(ROOT / "link_workflow_step_receipt_index.py"),
        "--json",
        "--limit",
        str(limit),
        "--receipt-dir",
        str(source_receipt_dir),
    ]

    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    parsed: Any = None
    parse_error = ""
    if proc.stdout.strip():
        try:
            parsed = parse_json_output(proc.stdout)
        except Exception as exc:
            parse_error = str(exc)

    return {
        "command": cmd,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "index": parsed,
        "parse_error": parse_error,
    }


def render_index_html(index: dict[str, Any]) -> str:
    receipt_dir = html.escape(str(index.get("receipt_dir", "")))
    receipt_count = int(index.get("receipt_count", 0) or 0)
    ok_count = int(index.get("ok_count", 0) or 0)
    failed_count = int(index.get("failed_count", 0) or 0)
    receipts = index.get("receipts") or []

    parts = [
        '<section class="workflow-step-receipt-index-execution-receipt">',
        "<h2>Workflow step execution receipt index execution receipt</h2>",
        f"<p>Receipt directory: <code>{receipt_dir}</code></p>",
        f"<p>Total step execution receipts indexed: <strong>{receipt_count}</strong></p>",
        f"<p>OK: {ok_count} · Failed: {failed_count}</p>",
    ]

    if receipts:
        parts.append("<ul>")
        for item in receipts[:5]:
            name = html.escape(str(item.get("name", "unknown")))
            workflow_id = html.escape(str(item.get("workflow_id", "")))
            step_id = html.escape(str(item.get("step_id", "")))
            status = html.escape(str(item.get("status", "")))
            ok = "yes" if item.get("ok") else "no"
            finished = html.escape(str(item.get("finished_at", "")))
            parts.append(
                "<li>"
                f"<strong>{name}</strong><br>"
                f"workflow: {workflow_id or 'not recorded'}<br>"
                f"step: {step_id or 'all'}<br>"
                f"finished: {finished or 'not recorded'}<br>"
                f"status: {status or 'unknown'}<br>"
                f"ok: {ok}"
                "</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No workflow step execution receipts found.</p>")

    parts.append("</section>")
    return "".join(parts)


def summarize_index(index: dict[str, Any]) -> dict[str, Any]:
    latest = index.get("latest") or {}
    return {
        "receipt_count": int(index.get("receipt_count", 0) or 0),
        "shown_count": int(index.get("shown_count", 0) or 0),
        "ok_count": int(index.get("ok_count", 0) or 0),
        "failed_count": int(index.get("failed_count", 0) or 0),
        "latest": latest.get("name", ""),
        "latest_status": latest.get("status", ""),
    }


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=str(path.parent),
        text=True,
    )
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, sort_keys=True)
            f.write("\n")
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def build_execution_receipt(
    *,
    source_receipt_dir: Path | None = None,
    receipt_dir: Path | None = None,
    limit: int = 5,
    write: bool = True,
) -> dict[str, Any]:
    source_dir = (source_receipt_dir or default_receipt_dir()).expanduser().resolve()
    output_dir = (receipt_dir or default_receipt_dir()).expanduser().resolve()

    problems: list[str] = []
    result = run_step_receipt_index(source_dir, limit)
    index = result.get("index")

    if result["returncode"] != 0:
        problems.append(f"index command failed with return code {result['returncode']}")
    if result.get("parse_error"):
        problems.append(f"could not parse index JSON: {result['parse_error']}")
    if not isinstance(index, dict):
        problems.append("index output was not a JSON object")
        index = {}
    if index and index.get("kind") != "link_workflow_step_receipt_index":
        problems.append(f"unexpected index kind: {index.get('kind')!r}")

    html_output = render_index_html(index)
    ok = not problems

    receipt_path = ""
    if write:
        receipt_path = str(output_dir / f"workflow-step-receipt-index-execution-{stamp()}.json")

    receipt = {
        "kind": RECEIPT_KIND,
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "status": "ok" if ok else "failed",
        "ok": ok,
        "non_destructive": True,
        "source_receipt_dir": str(source_dir),
        "receipt_path": receipt_path,
        "command": result.get("command", []),
        "returncode": result.get("returncode"),
        "problems": problems,
        "step_receipt_index": index,
        "summary": summarize_index(index),
        "has_html": True,
        "html": html_output,
    }

    if write:
        atomic_write_json(Path(receipt_path), receipt)

    return receipt


def validate_workflow_step_receipt_index_execution_receipt() -> list[str]:
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        receipt = build_execution_receipt(
            source_receipt_dir=tmpdir,
            receipt_dir=tmpdir,
            limit=5,
            write=True,
        )

        if receipt.get("kind") != RECEIPT_KIND:
            problems.append("unexpected receipt kind")
        if receipt.get("schema_version") != SCHEMA_VERSION:
            problems.append("unexpected schema version")
        if not receipt.get("non_destructive"):
            problems.append("receipt is not marked non_destructive")
        if not receipt.get("ok"):
            problems.append("execution receipt validation did not return ok")
        if not receipt.get("has_html"):
            problems.append("receipt did not include HTML marker")
        path = receipt.get("receipt_path", "")
        if not path or not Path(path).exists():
            problems.append("receipt file was not written")
        index = receipt.get("step_receipt_index", {})
        if index.get("kind") != "link_workflow_step_receipt_index":
            problems.append("nested step receipt index kind was not recorded")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a receipt for the workflow step execution receipt index.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--source-receipt-dir", type=Path, default=None)
    parser.add_argument("--receipt-dir", type=Path, default=None)
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index_execution_receipt()
        if problems:
            print("workflow step execution receipt index execution receipt FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt = build_execution_receipt(
        source_receipt_dir=args.source_receipt_dir,
        receipt_dir=args.receipt_dir,
        limit=args.limit,
        write=not args.no_write,
    )

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print(MARKER if receipt.get("ok") else "workflow step execution receipt index execution receipt FAILED")
        if receipt.get("receipt_path"):
            print(receipt["receipt_path"])

    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
