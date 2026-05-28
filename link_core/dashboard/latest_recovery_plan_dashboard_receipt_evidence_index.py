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
MARKER = "latest recovery plan dashboard receipt evidence index OK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    try:
        from latest_recovery_plan_dashboard_receipts import default_receipt_dir as _default

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


def is_recovery_dashboard_receipt(path: Path, data: dict[str, Any]) -> bool:
    haystack = " ".join(
        str(x).lower()
        for x in (
            path.name,
            data.get("kind", ""),
            data.get("command", ""),
            data.get("title", ""),
            data.get("status", ""),
        )
    )
    return (
        "receipt" in haystack
        and "recovery" in haystack
        and ("dashboard" in haystack or "plan" in haystack)
    )


def receipt_created_at(path: Path, data: dict[str, Any]) -> datetime:
    parsed = parse_datetime(data.get("created_at") or data.get("timestamp"))
    if parsed:
        return parsed
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def summarize_receipt(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    summary = data.get("summary") if isinstance(data.get("summary"), dict) else {}
    dashboard_response = (
        data.get("dashboard_response")
        if isinstance(data.get("dashboard_response"), dict)
        else {}
    )

    created = receipt_created_at(path, data)

    return {
        "name": path.name,
        "path": str(path),
        "created_at": created.isoformat(),
        "kind": str(data.get("kind", "")),
        "status": str(data.get("status", "")),
        "ok": bool(data.get("ok", False)),
        "non_destructive": data.get("non_destructive") is not False,
        "recommendation": str(
            summary.get("recommendation")
            or data.get("recommendation")
            or dashboard_response.get("recommendation")
            or ""
        ),
        "current_head": str(
            summary.get("current_head")
            or data.get("current_head")
            or dashboard_response.get("current_head")
            or ""
        ),
        "rollback_candidate": str(
            summary.get("rollback_candidate")
            or data.get("rollback_candidate")
            or dashboard_response.get("rollback_candidate")
            or ""
        ),
        "receipt_path": str(data.get("receipt_path") or path),
    }


def iter_receipt_files(receipt_dir: Path | None = None) -> list[Path]:
    root = Path(receipt_dir or default_receipt_dir()).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.json") if p.is_file())


def build_receipt_evidence_index(
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
        if not is_recovery_dashboard_receipt(path, data):
            continue
        entries.append(summarize_receipt(path, data))

    entries.sort(key=lambda item: item.get("created_at", ""), reverse=True)
    limited = entries[: max(1, int(limit))]

    return {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index",
        "schema_version": 1,
        "created_at": utc_now(),
        "receipt_dir": str(root),
        "receipt_count": len(entries),
        "shown_count": len(limited),
        "latest": limited[0] if limited else None,
        "receipts": limited,
        "non_destructive": True,
    }


def render_receipt_evidence_index(index: dict[str, Any]) -> str:
    receipts = index.get("receipts") if isinstance(index.get("receipts"), list) else []
    items: list[str] = []

    for receipt in receipts:
        if not isinstance(receipt, dict):
            continue
        name = html.escape(str(receipt.get("name", "")))
        status = html.escape(str(receipt.get("status", "")))
        recommendation = html.escape(str(receipt.get("recommendation", "")))
        created_at = html.escape(str(receipt.get("created_at", "")))
        ok = "yes" if receipt.get("ok") else "no"
        items.append(
            "<li>"
            f"<strong>{name}</strong>"
            f"<br>created: {created_at}"
            f"<br>status: {status or 'unknown'}"
            f"<br>ok: {ok}"
            f"<br>recommendation: {recommendation or 'not recorded'}"
            "</li>"
        )

    if not items:
        items.append("<li>No matching receipt evidence files found.</li>")

    receipt_dir = html.escape(str(index.get("receipt_dir", "")))
    count = html.escape(str(index.get("receipt_count", 0)))

    return (
        '<section class="latest-recovery-receipt-evidence-index">'
        "<h2>Latest recovery plan dashboard receipt evidence index</h2>"
        f"<p>Receipt directory: <code>{receipt_dir}</code></p>"
        f"<p>Total matching receipts: {count}</p>"
        "<ul>"
        + "".join(items)
        + "</ul>"
        "</section>"
    )


def write_sample_receipts(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    samples = [
        {
            "filename": "latest-recovery-dashboard-receipt-old.json",
            "created_at": "2026-01-01T00:00:00+00:00",
            "kind": "latest_recovery_plan_dashboard_execution_receipt",
            "status": "ok",
            "ok": True,
            "non_destructive": True,
            "summary": {
                "recommendation": "rollback_not_needed",
                "current_head": "abc123",
                "rollback_candidate": "def456",
            },
        },
        {
            "filename": "latest-recovery-dashboard-receipt-new.json",
            "created_at": "2026-01-02T00:00:00+00:00",
            "kind": "latest_recovery_plan_dashboard_execution_receipt",
            "status": "ok",
            "ok": True,
            "non_destructive": True,
            "summary": {
                "recommendation": "rollback_not_needed",
                "current_head": "new123",
                "rollback_candidate": "old456",
            },
        },
    ]

    for sample in samples:
        filename = sample.pop("filename")
        (root / filename).write_text(json.dumps(sample, indent=2, sort_keys=True))


def validate_latest_recovery_plan_dashboard_receipt_evidence_index() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        write_sample_receipts(root)

        index = build_receipt_evidence_index(root, limit=10)
        html_card = render_receipt_evidence_index(index)

        if index.get("kind") != "latest_recovery_plan_dashboard_receipt_evidence_index":
            problems.append("bad_index_kind")
        if index.get("non_destructive") is not True:
            problems.append("index_must_be_non_destructive")
        if index.get("receipt_count") != 2:
            problems.append("sample_receipt_count_wrong")
        latest = index.get("latest")
        if not isinstance(latest, dict):
            problems.append("latest_receipt_missing")
        elif latest.get("name") != "latest-recovery-dashboard-receipt-new.json":
            problems.append("latest_receipt_sort_wrong")
        if "receipt evidence index" not in html_card.lower():
            problems.append("html_marker_missing")
        forbidden = ("<form", "delete", "rm -rf", "reset --hard", "git clean")
        for item in forbidden:
            if item in html_card.lower():
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an evidence index for latest recovery dashboard receipt files."
    )
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index()
        if problems:
            print("latest recovery plan dashboard receipt evidence index FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    index = build_receipt_evidence_index(
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(index, indent=2, sort_keys=True))
    elif args.html:
        print(render_receipt_evidence_index(index))
    else:
        print("Latest recovery plan dashboard receipt evidence index")
        print(f"receipt_dir: {index.get('receipt_dir')}")
        print(f"receipt_count: {index.get('receipt_count')}")
        latest = index.get("latest")
        if isinstance(latest, dict):
            print(f"latest: {latest.get('name')}")
            print(f"status: {latest.get('status')}")
            print(f"recommendation: {latest.get('recommendation')}")
        else:
            print("latest: none")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
