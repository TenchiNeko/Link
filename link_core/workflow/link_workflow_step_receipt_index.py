#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
MARKER = "workflow step execution receipt index OK"
INDEX_KIND = "link_workflow_step_receipt_index"
RECEIPT_KIND = "link_workflow_step_execution_receipt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    try:
        from link_workflow_step_executor import default_receipt_dir as _default

        return _default()
    except Exception:
        return ROOT / ".link_execution_receipts"


def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def summarize_receipt(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    steps = data.get("steps") if isinstance(data.get("steps"), list) else []
    return {
        "name": path.name,
        "path": str(path),
        "receipt_path": str(data.get("receipt_path") or path),
        "kind": str(data.get("kind") or ""),
        "schema_version": data.get("schema_version"),
        "workflow_id": str(data.get("workflow_id") or ""),
        "goal": str(data.get("goal") or ""),
        "repo_root": str(data.get("repo_root") or ""),
        "started_at": str(data.get("started_at") or ""),
        "finished_at": str(data.get("finished_at") or ""),
        "status": str(data.get("status") or ""),
        "ok": bool(data.get("ok")),
        "dry_run": bool(data.get("dry_run")),
        "non_destructive": bool(data.get("non_destructive")),
        "step_id": str(data.get("step_id") or ""),
        "step_count": len(steps),
        "problem_count": len(data.get("problems") or []),
        "summary": summary,
        "ok_steps": int(summary.get("ok") or 0),
        "blocked_steps": int(summary.get("blocked") or 0),
        "failed_steps": int(summary.get("failed") or 0),
        "dry_run_steps": int(summary.get("dry_run") or 0),
    }


def sort_key(item: dict[str, Any]) -> tuple[str, str]:
    return (str(item.get("finished_at") or item.get("started_at") or ""), str(item.get("name") or ""))


def build_workflow_step_receipt_index(
    receipt_dir: Path | None = None,
    *,
    limit: int = 10,
) -> dict[str, Any]:
    directory = (receipt_dir or default_receipt_dir()).resolve()
    receipts: list[dict[str, Any]] = []

    if directory.exists():
        for path in directory.glob("*.json"):
            data = load_json(path)
            if not data:
                continue
            if data.get("kind") != RECEIPT_KIND:
                continue
            receipts.append(summarize_receipt(path, data))

    receipts.sort(key=sort_key, reverse=True)
    shown = receipts[: max(0, limit)]
    ok_count = sum(1 for item in receipts if item.get("ok"))
    failed_count = len(receipts) - ok_count

    return {
        "kind": INDEX_KIND,
        "schema_version": 1,
        "created_at": utc_now(),
        "receipt_dir": str(directory),
        "non_destructive": True,
        "receipt_count": len(receipts),
        "shown_count": len(shown),
        "ok_count": ok_count,
        "failed_count": failed_count,
        "latest": receipts[0] if receipts else None,
        "receipts": shown,
    }


def render_workflow_step_receipt_index_html(index: dict[str, Any]) -> str:
    receipt_dir = html.escape(str(index.get("receipt_dir") or ""))
    receipt_count = int(index.get("receipt_count") or 0)
    ok_count = int(index.get("ok_count") or 0)
    failed_count = int(index.get("failed_count") or 0)

    parts = [
        '<section class="workflow-step-receipt-index">',
        "<h2>Workflow step execution receipt index</h2>",
        f"<p>Receipt directory: <code>{receipt_dir}</code></p>",
        f"<p>Total receipts: <strong>{receipt_count}</strong></p>",
        f"<p>OK: {ok_count} · Failed: {failed_count}</p>",
    ]

    receipts = index.get("receipts")
    if isinstance(receipts, list) and receipts:
        parts.append("<ul>")
        for item in receipts:
            name = html.escape(str(item.get("name") or ""))
            workflow_id = html.escape(str(item.get("workflow_id") or ""))
            finished_at = html.escape(str(item.get("finished_at") or ""))
            status = html.escape(str(item.get("status") or ""))
            ok = "yes" if item.get("ok") else "no"
            dry_run = "yes" if item.get("dry_run") else "no"
            step_count = int(item.get("step_count") or 0)
            ok_steps = int(item.get("ok_steps") or 0)
            failed_steps = int(item.get("failed_steps") or 0)
            blocked_steps = int(item.get("blocked_steps") or 0)
            dry_run_steps = int(item.get("dry_run_steps") or 0)
            parts.append(
                "<li>"
                f"<strong>{name}</strong><br>"
                f"workflow: {workflow_id}<br>"
                f"finished: {finished_at}<br>"
                f"status: {status}<br>"
                f"ok: {ok} · dry run: {dry_run}<br>"
                f"steps: {ok_steps}/{step_count} ok · failed: {failed_steps} · "
                f"blocked: {blocked_steps} · dry-run steps: {dry_run_steps}"
                "</li>"
            )
        parts.append("</ul>")
    else:
        parts.append("<p>No workflow step execution receipts found.</p>")

    parts.append("</section>")
    return "".join(parts)


def validate_workflow_step_receipt_index() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        receipt_dir = Path(tmp)

        from link_workflow_step_executor import execute_workflow_steps, sample_workflow_spec

        receipt = execute_workflow_steps(
            sample_workflow_spec(),
            dry_run=True,
            receipt_dir=receipt_dir,
            write_receipt=True,
        )

        receipt_path = Path(str(receipt.get("receipt_path") or ""))
        if not receipt_path.exists():
            problems.append("expected workflow step receipt to be written")

        index = build_workflow_step_receipt_index(receipt_dir, limit=5)
        if index.get("kind") != INDEX_KIND:
            problems.append("index kind mismatch")
        if index.get("receipt_count") != 1:
            problems.append("expected exactly one indexed receipt")
        if index.get("ok_count") != 1:
            problems.append("expected one ok receipt")
        if not index.get("latest"):
            problems.append("expected latest receipt summary")
        else:
            latest = index["latest"]
            if latest.get("workflow_id") != "lu41-workflow-step-executor":
                problems.append("latest workflow id mismatch")
            if latest.get("step_count") != 3:
                problems.append("latest step count mismatch")

        rendered = render_workflow_step_receipt_index_html(index)
        if "Workflow step execution receipt index" not in rendered:
            problems.append("HTML missing title")
        if "lu41-workflow-step-executor" not in rendered:
            problems.append("HTML missing workflow id")

    empty_index = build_workflow_step_receipt_index(Path(tempfile.mkdtemp()), limit=5)
    if empty_index.get("receipt_count") != 0:
        problems.append("empty index should have zero receipts")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Index workflow step execution receipts.")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_receipt_index()
        if problems:
            print("workflow step execution receipt index FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    index = build_workflow_step_receipt_index(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.html:
        print(render_workflow_step_receipt_index_html(index))
    else:
        print(json.dumps(index, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
