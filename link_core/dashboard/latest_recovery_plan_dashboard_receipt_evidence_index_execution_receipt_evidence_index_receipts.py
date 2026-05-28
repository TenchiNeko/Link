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
MARKER = "latest recovery plan dashboard receipt evidence index execution receipt evidence index execution receipt OK"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    configured = os.environ.get(
        "LINK_LATEST_RECOVERY_RECEIPT_EVIDENCE_INDEX_EXECUTION_RECEIPT_EVIDENCE_INDEX_RECEIPT_DIR"
    )
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR.resolve()


def timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _load_index_module():
    import latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index as module

    return module


def _call_build_index(module: Any, receipt_dir: Path | None, limit: int) -> dict[str, Any]:
    build = getattr(module, "build_execution_receipt_evidence_index", None)
    if build is None:
        build = getattr(
            module,
            "build_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index",
            None,
        )
    if build is None:
        raise RuntimeError("could not find LU32 build function")

    return build(receipt_dir, limit=limit)


def _call_render_index(module: Any, index: dict[str, Any]) -> str:
    render = getattr(module, "render_execution_receipt_evidence_index", None)
    if render is None:
        render = getattr(
            module,
            "render_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index",
            None,
        )
    if render is None:
        raise RuntimeError("could not find LU32 render function")

    return str(render(index))


def build_execution_receipt_evidence_index_execution_receipt(
    receipt_source_dir: Path | None = None,
    receipt_dir: Path | None = None,
    *,
    limit: int = 25,
    write: bool = False,
) -> dict[str, Any]:
    module = _load_index_module()
    index = _call_build_index(module, receipt_source_dir, limit)
    html_card = _call_render_index(module, index)

    problems: list[str] = []
    if not isinstance(index, dict):
        problems.append("index_missing")
        index = {}
    if index.get("non_destructive") is not True:
        problems.append("index_must_be_non_destructive")
    if not html_card:
        problems.append("html_card_missing")

    latest = index.get("latest") if isinstance(index.get("latest"), dict) else None
    receipt = {
        "kind": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt",
        "schema_version": 1,
        "created_at": utc_now(),
        "status": "ok" if not problems else "failed",
        "ok": not problems,
        "non_destructive": True,
        "command": "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index.py",
        "source_receipt_dir": str(index.get("receipt_dir", "")),
        "has_html": bool(html_card),
        "evidence_index": index,
        "problems": problems,
        "summary": {
            "receipt_count": int(index.get("receipt_count", 0) or 0),
            "shown_count": int(index.get("shown_count", 0) or 0),
            "latest": latest.get("name", "") if latest else None,
            "latest_status": latest.get("status", "") if latest else "",
        },
        "receipt_path": "",
    }

    if write:
        out_dir = Path(receipt_dir or default_receipt_dir()).expanduser().resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"latest-recovery-receipt-evidence-index-execution-receipt-evidence-index-execution-{timestamp_slug()}.json"
        receipt["receipt_path"] = str(out_path)
        out_path.write_text(json.dumps(receipt, indent=2, sort_keys=True))

    return receipt


def validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source_dir = root / "source"
        receipt_dir = root / "receipts"
        source_dir.mkdir(parents=True, exist_ok=True)

        module = _load_index_module()
        sample_writer = getattr(module, "write_sample_execution_receipts", None)
        if sample_writer is None:
            problems.append("sample_writer_missing")
            return problems

        sample_writer(source_dir)

        receipt = build_execution_receipt_evidence_index_execution_receipt(
            source_dir,
            receipt_dir,
            limit=10,
            write=True,
        )

        if receipt.get("kind") != "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt":
            problems.append("bad_receipt_kind")
        if receipt.get("non_destructive") is not True:
            problems.append("receipt_must_be_non_destructive")
        if receipt.get("ok") is not True:
            problems.append("receipt_not_ok")
        if receipt.get("has_html") is not True:
            problems.append("receipt_missing_html")

        summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
        if summary.get("receipt_count") != 2:
            problems.append("summary_receipt_count_wrong")

        receipt_path = Path(str(receipt.get("receipt_path", "")))
        if not receipt_path.exists():
            problems.append("receipt_file_not_written")
        else:
            loaded = json.loads(receipt_path.read_text())
            if loaded.get("kind") != receipt.get("kind"):
                problems.append("written_receipt_kind_mismatch")

        index = receipt.get("evidence_index")
        if not isinstance(index, dict):
            problems.append("embedded_index_missing")
        elif index.get("receipt_count") != 2:
            problems.append("embedded_index_receipt_count_wrong")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write an execution receipt for the latest recovery receipt evidence-index execution-receipt evidence index."
    )
    parser.add_argument("--receipt-source-dir")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_execution_receipt()
        if problems:
            print("latest recovery plan dashboard receipt evidence index execution receipt evidence index execution receipt FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    receipt = build_execution_receipt_evidence_index_execution_receipt(
        Path(args.receipt_source_dir) if args.receipt_source_dir else None,
        Path(args.receipt_dir) if args.receipt_dir else None,
        limit=args.limit,
        write=args.write,
    )

    if args.json:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print("Latest recovery plan dashboard receipt evidence index execution receipt evidence index execution receipt")
        print(f"status: {receipt.get('status')}")
        print(f"ok: {receipt.get('ok')}")
        print(f"receipt_path: {receipt.get('receipt_path') or 'not written'}")
        summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}
        print(f"indexed_receipts: {summary.get('receipt_count', 0)}")
        print(f"shown_receipts: {summary.get('shown_count', 0)}")
        print(f"latest: {summary.get('latest') or 'none'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
