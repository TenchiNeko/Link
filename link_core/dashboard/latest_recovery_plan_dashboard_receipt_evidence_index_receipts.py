#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_RECEIPT_DIR = ROOT / ".link_execution_receipts"
MARKER = "latest recovery plan dashboard receipt evidence index execution receipt OK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    configured = os.environ.get("LINK_LATEST_RECOVERY_RECEIPT_EVIDENCE_INDEX_RECEIPT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR.resolve()


def build_latest_recovery_receipt_evidence_index_execution_receipt(
    receipt_source_dir: Path | None = None,
    *,
    receipt_dir: Path | None = None,
    write: bool = False,
    limit: int = 25,
) -> dict[str, Any]:
    from latest_recovery_plan_dashboard_receipt_evidence_index import (
        build_receipt_evidence_index,
        render_receipt_evidence_index,
    )

    source_dir = Path(receipt_source_dir).expanduser().resolve() if receipt_source_dir else None
    index = build_receipt_evidence_index(source_dir, limit=limit)
    html_card = render_receipt_evidence_index(index)

    problems: list[str] = []
    if index.get("kind") != "latest_recovery_plan_dashboard_receipt_evidence_index":
        problems.append("bad_evidence_index_kind")
    if index.get("non_destructive") is not True:
        problems.append("evidence_index_must_be_non_destructive")
    if "receipt evidence index" not in html_card.lower():
        problems.append("evidence_index_html_marker_missing")

    receipt = {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt",
        "schema_version": 1,
        "created_at": utc_now(),
        "status": "ok" if not problems else "failed",
        "ok": not problems,
        "non_destructive": True,
        "command": "latest_recovery_plan_dashboard_receipt_evidence_index.py",
        "source_receipt_dir": str(source_dir or index.get("receipt_dir", "")),
        "summary": {
            "receipt_count": index.get("receipt_count", 0),
            "shown_count": index.get("shown_count", 0),
            "latest": index.get("latest"),
        },
        "evidence_index": index,
        "has_html": bool(html_card),
        "problems": problems,
    }

    if write:
        target_dir = Path(receipt_dir or default_receipt_dir()).expanduser().resolve()
        target_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        target = target_dir / f"latest-recovery-receipt-evidence-index-execution-{stamp}.json"
        receipt["receipt_path"] = str(target)
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        receipt["receipt_path"] = ""

    return receipt


def validate_latest_recovery_receipt_evidence_index_execution_receipt() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        out = root / "out"

        from latest_recovery_plan_dashboard_receipt_evidence_index import write_sample_receipts

        write_sample_receipts(source)

        receipt = build_latest_recovery_receipt_evidence_index_execution_receipt(
            source,
            receipt_dir=out,
            write=True,
            limit=10,
        )

        if receipt.get("kind") != "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt":
            problems.append("bad_receipt_kind")
        if receipt.get("status") != "ok":
            problems.append("receipt_status_not_ok")
        if receipt.get("ok") is not True:
            problems.append("receipt_ok_not_true")
        if receipt.get("non_destructive") is not True:
            problems.append("receipt_must_be_non_destructive")

        summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
        if summary.get("receipt_count") != 2:
            problems.append("summary_receipt_count_wrong")

        receipt_path = receipt.get("receipt_path")
        if not receipt_path:
            problems.append("receipt_path_missing")
        elif not Path(str(receipt_path)).exists():
            problems.append("receipt_file_missing")

        index = receipt.get("evidence_index") if isinstance(receipt.get("evidence_index"), dict) else {}
        latest = index.get("latest") if isinstance(index.get("latest"), dict) else {}
        if latest.get("name") != "latest-recovery-dashboard-receipt-new.json":
            problems.append("latest_sort_not_preserved")

        forbidden = ("delete", "rm -rf", "reset --hard", "git clean", "<form")
        blob = json.dumps(receipt, sort_keys=True).lower()
        for item in forbidden:
            if item in blob:
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build an execution receipt for the latest recovery dashboard receipt evidence index."
    )
    parser.add_argument("--receipt-source-dir")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_receipt_evidence_index_execution_receipt()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt = build_latest_recovery_receipt_evidence_index_execution_receipt(
        Path(args.receipt_source_dir) if args.receipt_source_dir else None,
        receipt_dir=Path(args.receipt_dir) if args.receipt_dir else None,
        write=args.write,
        limit=args.limit,
    )

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print("Latest recovery plan dashboard receipt evidence index execution receipt")
        print(f"status: {receipt.get('status')}")
        print(f"ok: {receipt.get('ok')}")
        summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
        print(f"receipt_count: {summary.get('receipt_count')}")
        if receipt.get("receipt_path"):
            print(f"receipt_path: {receipt.get('receipt_path')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
