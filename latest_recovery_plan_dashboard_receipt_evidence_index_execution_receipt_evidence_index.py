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
MARKER = "latest recovery plan dashboard receipt evidence index execution receipt evidence index OK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    try:
        from latest_recovery_plan_dashboard_receipt_evidence_index_receipts import (
            default_receipt_dir as _default,
        )

        return Path(_default()).resolve()
    except Exception:
        return (ROOT / ".link_execution_receipts").resolve()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def is_evidence_index_execution_receipt(path: Path, data: dict[str, Any]) -> bool:
    kind = str(data.get("kind", "")).lower()
    haystack = " ".join(
        str(x).lower()
        for x in (
            path.name,
            data.get("kind", ""),
            data.get("command", ""),
            data.get("status", ""),
        )
    )

    return (
        kind == "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt"
        or (
            "receipt" in haystack
            and "evidence" in haystack
            and "index" in haystack
            and "execution" in haystack
        )
    )


def receipt_created_at(path: Path, data: dict[str, Any]) -> datetime:
    parsed = parse_datetime(data.get("created_at") or data.get("timestamp"))
    if parsed:
        return parsed
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def summarize_execution_receipt(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    evidence_index = data.get("evidence_index") if isinstance(data.get("evidence_index"), dict) else {}
    latest = evidence_index.get("latest") if isinstance(evidence_index.get("latest"), dict) else {}

    created = receipt_created_at(path, data)

    return {
        "name": path.name,
        "path": str(path),
        "created_at": created.isoformat(),
        "kind": str(data.get("kind", "")),
        "status": str(data.get("status", "")),
        "ok": bool(data.get("ok", False)),
        "non_destructive": data.get("non_destructive") is not False,
        "command": str(data.get("command", "")),
        "source_receipt_dir": str(data.get("source_receipt_dir", "")),
        "receipt_path": str(data.get("receipt_path") or path),
        "indexed_receipt_count": int(summary.get("receipt_count") or evidence_index.get("receipt_count") or 0),
        "shown_count": int(summary.get("shown_count") or evidence_index.get("shown_count") or 0),
        "latest_indexed_receipt": str(
            (summary.get("latest") if not isinstance(summary.get("latest"), dict) else summary["latest"].get("name"))
            or latest.get("name")
            or ""
        ),
    }


def iter_receipt_files(receipt_dir: Path | None = None) -> list[Path]:
    root = Path(receipt_dir or default_receipt_dir()).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def build_execution_receipt_evidence_index(
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
) -> dict[str, Any]:
    root = Path(receipt_dir or default_receipt_dir()).expanduser().resolve()
    entries: list[dict[str, Any]] = []

    for path in iter_receipt_files(root):
        data = load_json_file(path)
        if not data:
            continue
        if not is_evidence_index_execution_receipt(path, data):
            continue
        entries.append(summarize_execution_receipt(path, data))

    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    limited = entries[: max(1, int(limit))]

    return {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index",
        "schema_version": 1,
        "created_at": utc_now(),
        "receipt_dir": str(root),
        "receipt_count": len(entries),
        "shown_count": len(limited),
        "latest": limited[0] if limited else None,
        "receipts": limited,
        "non_destructive": True,
    }


def render_execution_receipt_evidence_index(index: dict[str, Any]) -> str:
    receipts = index.get("receipts") if isinstance(index.get("receipts"), list) else []
    items: list[str] = []

    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        name = html.escape(str(receipt.get("name", "")))
        status = html.escape(str(receipt.get("status", "")))
        created_at = html.escape(str(receipt.get("created_at", "")))
        indexed_count = html.escape(str(receipt.get("indexed_receipt_count", 0)))
        latest_indexed = html.escape(str(receipt.get("latest_indexed_receipt", "")))
        ok = "yes" if receipt.get("ok") else "no"
        items.append(
            "<li>"
            f"<strong>{name}</strong>"
            f"<br>created: {created_at}"
            f"<br>status: {status or 'unknown'}"
            f"<br>ok: {ok}"
            f"<br>indexed receipts: {indexed_count}"
            f"<br>latest indexed receipt: {latest_indexed or 'not recorded'}"
            "</li>"
        )

    if not items:
        items.append("<li>No matching execution receipt evidence files found.</li>")

    receipt_dir = html.escape(str(index.get("receipt_dir", "")))
    count = html.escape(str(index.get("receipt_count", 0)))

    return (
        '<section class="latest-recovery-receipt-evidence-index-execution-receipt-evidence-index">'
        "<h2>Latest recovery plan dashboard receipt evidence index execution receipt evidence index</h2>"
        f"<p>Receipt directory: <code>{receipt_dir}</code></p>"
        f"<p>Total matching execution receipts: {count}</p>"
        "<ul>"
        + "".join(items)
        + "</ul>"
        "</section>"
    )


def write_sample_execution_receipts(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    samples = [
        {
            "filename": "latest-recovery-receipt-evidence-index-execution-old.json",
            "created_at": "2026-01-01T00:00:00+00:00",
            "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt",
            "status": "ok",
            "ok": True,
            "non_destructive": True,
            "command": "latest_recovery_plan_dashboard_receipt_evidence_index.py",
            "summary": {"receipt_count": 1, "shown_count": 1, "latest": "old-source.json"},
            "evidence_index": {
                "receipt_count": 1,
                "shown_count": 1,
                "latest": {"name": "old-source.json"},
            },
        },
        {
            "filename": "latest-recovery-receipt-evidence-index-execution-new.json",
            "created_at": "2026-01-02T00:00:00+00:00",
            "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt",
            "status": "ok",
            "ok": True,
            "non_destructive": True,
            "command": "latest_recovery_plan_dashboard_receipt_evidence_index.py",
            "summary": {"receipt_count": 2, "shown_count": 2, "latest": "new-source.json"},
            "evidence_index": {
                "receipt_count": 2,
                "shown_count": 2,
                "latest": {"name": "new-source.json"},
            },
        },
        {
            "filename": "unrelated.json",
            "created_at": "2026-01-03T00:00:00+00:00",
            "kind": "unrelated_receipt",
            "status": "ok",
            "ok": True,
        },
    ]

    for sample in samples:
        filename = str(sample.pop("filename"))
        (root / filename).write_text(json.dumps(sample, indent=2, sort_keys=True))


def validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_sample_execution_receipts(root)

        index = build_execution_receipt_evidence_index(root, limit=10)
        html_card = render_execution_receipt_evidence_index(index)

        if index.get("kind") != "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index":
            problems.append("bad_index_kind")
        if index.get("non_destructive") is not True:
            problems.append("index_must_be_non_destructive")
        if index.get("receipt_count") != 2:
            problems.append("sample_receipt_count_wrong")
        latest = index.get("latest")
        if not isinstance(latest, dict):
            problems.append("latest_receipt_missing")
        elif latest.get("name") != "latest-recovery-receipt-evidence-index-execution-new.json":
            problems.append("latest_receipt_sort_wrong")
        elif latest.get("indexed_receipt_count") != 2:
            problems.append("latest_summary_wrong")
        if "execution receipt evidence index" not in html_card.lower():
            problems.append("html_marker_missing")
        forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
        for item in forbidden:
            if item in html_card.lower():
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an evidence index for latest recovery receipt evidence index execution receipts."
    )
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt evidence index FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    index = build_execution_receipt_evidence_index(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(index, indent=2, sort_keys=True))
    elif args.html:
        print(render_execution_receipt_evidence_index(index))
    else:
        print("Latest recovery plan dashboard receipt evidence index execution receipt evidence index")
        print(f"receipt_dir: {index.get('receipt_dir')}")
        print(f"receipt_count: {index.get('receipt_count')}")
        latest = index.get("latest")
        if isinstance(latest, dict):
            print(f"latest: {latest.get('name')}")
            print(f"status: {latest.get('status')}")
            print(f"indexed_receipt_count: {latest.get('indexed_receipt_count')}")
            print(f"latest_indexed_receipt: {latest.get('latest_indexed_receipt')}")
        else:
            print("latest: none")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
