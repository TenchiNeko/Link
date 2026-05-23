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
MARKER = "workflow preflight receipt index OK"
INDEX_KIND = "link_workflow_preflight_receipt_index"
RECEIPT_KIND = "link_workflow_preflight_execution_receipt"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    try:
        from link_workflow_preflight_executor import default_receipt_dir as _default

        return Path(_default()).resolve()
    except Exception:
        return (ROOT / ".link_execution_receipts").resolve()


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if isinstance(data, dict):
        return data
    return None


def receipt_sort_key(item: dict[str, Any]) -> str:
    return str(
        item.get("finished_at")
        or item.get("started_at")
        or item.get("created_at")
        or item.get("name")
        or ""
    )


def summarize_receipt(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    checks = data.get("checks") if isinstance(data.get("checks"), list) else []
    problems = data.get("problems") if isinstance(data.get("problems"), list) else []

    return {
        "name": path.name,
        "path": str(path.resolve()),
        "receipt_path": str(data.get("receipt_path") or path.resolve()),
        "kind": data.get("kind", ""),
        "workflow_id": data.get("workflow_id", ""),
        "goal": data.get("goal", ""),
        "status": data.get("status", ""),
        "ok": data.get("ok") is True,
        "dry_run": data.get("dry_run") is True,
        "repo_root": data.get("repo_root", ""),
        "started_at": data.get("started_at", ""),
        "finished_at": data.get("finished_at", ""),
        "check_count": len(checks),
        "problem_count": len(problems),
        "summary": {
            "total": summary.get("total", 0),
            "ok": summary.get("ok", 0),
            "failed": summary.get("failed", 0),
            "blocked": summary.get("blocked", 0),
            "optional_failed": summary.get("optional_failed", 0),
        },
        "non_destructive": data.get("non_destructive") is True,
    }


def find_workflow_preflight_receipts(receipt_dir: Path | None = None) -> list[dict[str, Any]]:
    root = (receipt_dir or default_receipt_dir()).expanduser().resolve()
    if not root.exists():
        return []

    receipts: list[dict[str, Any]] = []
    candidates = sorted(root.glob("workflow-preflight-*.json"))

    for path in candidates:
        data = load_json_file(path)
        if not data:
            continue
        if data.get("kind") != RECEIPT_KIND:
            continue
        receipts.append(summarize_receipt(path, data))

    receipts.sort(key=receipt_sort_key, reverse=True)
    return receipts


def build_workflow_preflight_receipt_index(
    receipt_dir: Path | None = None,
    *,
    limit: int | None = None,
) -> dict[str, Any]:
    root = (receipt_dir or default_receipt_dir()).expanduser().resolve()
    receipts = find_workflow_preflight_receipts(root)

    if limit is not None:
        try:
            safe_limit = max(0, int(limit))
        except Exception:
            safe_limit = 50
        shown = receipts[:safe_limit]
    else:
        shown = receipts

    latest = shown[0] if shown else None

    return {
        "kind": INDEX_KIND,
        "schema_version": 1,
        "created_at": utc_now(),
        "receipt_dir": str(root),
        "receipt_count": len(receipts),
        "shown_count": len(shown),
        "ok_count": sum(1 for item in receipts if item.get("ok") is True),
        "failed_count": sum(1 for item in receipts if item.get("ok") is not True),
        "latest": latest,
        "receipts": shown,
        "non_destructive": True,
    }


def render_workflow_preflight_receipt_index_html(index: dict[str, Any]) -> str:
    receipts = index.get("receipts") if isinstance(index.get("receipts"), list) else []

    chunks: list[str] = [
        '<section class="workflow-preflight-receipt-index">',
        "<h2>Workflow preflight receipt index</h2>",
        f"<p>Receipt directory: <code>{html.escape(str(index.get('receipt_dir', '')))}</code></p>",
        f"<p>Total receipts: <strong>{html.escape(str(index.get('receipt_count', 0)))}</strong></p>",
        f"<p>OK: {html.escape(str(index.get('ok_count', 0)))} · Failed: {html.escape(str(index.get('failed_count', 0)))}</p>",
    ]

    if not receipts:
        chunks.append("<p>No workflow preflight receipts found.</p>")
    else:
        chunks.append("<ul>")
        for item in receipts:
            summary = item.get("summary") if isinstance(item.get("summary"), dict) else {}
            name = html.escape(str(item.get("name", "")))
            workflow_id = html.escape(str(item.get("workflow_id", "")))
            status = html.escape(str(item.get("status", "")))
            ok = "yes" if item.get("ok") is True else "no"
            finished = html.escape(str(item.get("finished_at", "")))
            dry_run = "yes" if item.get("dry_run") is True else "no"
            total = html.escape(str(summary.get("total", 0)))
            passed = html.escape(str(summary.get("ok", 0)))
            failed = html.escape(str(summary.get("failed", 0)))
            blocked = html.escape(str(summary.get("blocked", 0)))

            chunks.append(
                "<li>"
                f"<strong>{name}</strong><br>"
                f"workflow: {workflow_id}<br>"
                f"finished: {finished}<br>"
                f"status: {status}<br>"
                f"ok: {ok} · dry run: {dry_run}<br>"
                f"checks: {passed}/{total} ok · failed: {failed} · blocked: {blocked}"
                "</li>"
            )
        chunks.append("</ul>")

    chunks.append("</section>")
    return "".join(chunks)


def validate_workflow_preflight_receipt_index() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        receipt_dir = Path(tmp)

        good = {
            "kind": RECEIPT_KIND,
            "schema_version": 1,
            "workflow_id": "test-workflow",
            "goal": "Test workflow preflight receipt indexing.",
            "started_at": "2026-01-01T00:00:00+00:00",
            "finished_at": "2026-01-01T00:00:01+00:00",
            "repo_root": str(receipt_dir),
            "dry_run": False,
            "non_destructive": True,
            "ok": True,
            "status": "ok",
            "checks": [{"id": "x", "ok": True, "status": "ok"}],
            "summary": {"total": 1, "ok": 1, "failed": 0, "blocked": 0, "optional_failed": 0},
            "problems": [],
            "receipt_path": str(receipt_dir / "workflow-preflight-test.json"),
        }
        bad_kind = dict(good)
        bad_kind["kind"] = "other"

        (receipt_dir / "workflow-preflight-test.json").write_text(json.dumps(good), encoding="utf-8")
        (receipt_dir / "workflow-preflight-ignore.json").write_text(json.dumps(bad_kind), encoding="utf-8")
        (receipt_dir / "not-json.json").write_text("{", encoding="utf-8")

        index = build_workflow_preflight_receipt_index(receipt_dir)
        if index.get("receipt_count") != 1:
            problems.append(f"expected exactly one indexed receipt, got {index.get('receipt_count')}")

        latest = index.get("latest")
        if not isinstance(latest, dict) or latest.get("workflow_id") != "test-workflow":
            problems.append("latest indexed workflow receipt was incorrect")

        html_output = render_workflow_preflight_receipt_index_html(index)
        if "Workflow preflight receipt index" not in html_output:
            problems.append("html output missing expected heading")

        limited = build_workflow_preflight_receipt_index(receipt_dir, limit=0)
        if limited.get("shown_count") != 0:
            problems.append("limit=0 should show zero receipts")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Index Link workflow preflight execution receipts.")
    parser.add_argument("--receipt-dir", help="Receipt directory to scan")
    parser.add_argument("--limit", type=int, default=None, help="Maximum receipts to show")
    parser.add_argument("--json", action="store_true", help="Print JSON index")
    parser.add_argument("--html", action="store_true", help="Print HTML index")
    parser.add_argument("--self-test", action="store_true", help="Run built-in validation")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_preflight_receipt_index()
        if problems:
            print("workflow preflight receipt index FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None
    index = build_workflow_preflight_receipt_index(receipt_dir, limit=args.limit)

    if args.html:
        print(render_workflow_preflight_receipt_index_html(index))
    else:
        print(json.dumps(index, indent=2, sort_keys=True))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
