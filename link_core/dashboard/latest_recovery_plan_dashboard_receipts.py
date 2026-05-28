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


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir():
    configured = os.environ.get("LINK_LATEST_RECOVERY_DASHBOARD_RECEIPT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR.resolve()


def build_latest_recovery_dashboard_execution_receipt(root=None, receipt_dir=None, write=False):
    from latest_recovery_plan_loader import summarize_latest_recovery_plan
    import recovery_plan_latest_dashboard_integration as latest_dashboard

    build_response = getattr(
        latest_dashboard,
        "build_latest_recovery_dashboard_web_response",
        None,
    ) or getattr(
        latest_dashboard,
        "build_latest_recovery_plan_dashboard_response",
    )

    render_response = getattr(
        latest_dashboard,
        "render_latest_recovery_dashboard_web_response",
        None,
    ) or getattr(
        latest_dashboard,
        "render_latest_recovery_plan_dashboard_response",
    )

    problems = []
    status = "ok"

    try:
        summary = summarize_latest_recovery_plan(root)
    except Exception as exc:
        summary = {
            "exists": False,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        status = "error"
        problems.append("latest_recovery_plan_summary_failed")

    try:
        response = build_response(root)
        html = render_response(root)
    except Exception as exc:
        response = {
            "ok": False,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
        }
        html = ""
        status = "error"
        problems.append("latest_recovery_dashboard_render_failed")

    if response.get("status") == "missing":
        status = "missing"

    receipt = {
        "kind": "latest_recovery_plan_dashboard_execution_receipt",
        "schema_version": 1,
        "created_at": utc_now(),
        "status": status,
        "ok": status in {"ok", "missing"},
        "non_destructive": True,
        "command": "latest recovery plan dashboard",
        "root": str(Path(root).expanduser().resolve()) if root else None,
        "summary": summary,
        "dashboard_response": {
            "ok": bool(response.get("ok")),
            "status": str(response.get("status", "")),
            "mode": str(response.get("mode", "")),
            "has_html": bool(response.get("html") or html),
        },
        "html_length": len(html),
        "problems": problems,
    }

    if write:
        target_dir = receipt_dir or default_receipt_dir()
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "latest_recovery_plan_dashboard_receipt.json"
        target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        receipt["receipt_path"] = str(target)

    return receipt


def validate_latest_recovery_dashboard_receipts():
    problems = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "plans"
        root.mkdir(parents=True)

        sample = {
            "created_at": "2026-01-01T00:00:00+00:00",
            "recommendation": "KEEP",
            "reason": "self-test sample",
            "current_head": "abc123",
            "rollback_candidate": "def456",
            "guarded_steps": ["inspect healthcheck", "review rollback candidate"],
            "checks": ["registry", "healthcheck"],
        }
        (root / "sample_recovery_plan.json").write_text(json.dumps(sample) + "\n")

        receipt_dir = Path(tmp) / "receipts"
        receipt = build_latest_recovery_dashboard_execution_receipt(
            root=root,
            receipt_dir=receipt_dir,
            write=True,
        )

        if receipt.get("kind") != "latest_recovery_plan_dashboard_execution_receipt":
            problems.append("bad_receipt_kind")

        if receipt.get("non_destructive") is not True:
            problems.append("receipt_must_be_non_destructive")

        if receipt.get("status") != "ok":
            problems.append("receipt_status_not_ok")

        if not receipt.get("receipt_path"):
            problems.append("receipt_path_missing")

        if receipt.get("receipt_path") and not Path(receipt["receipt_path"]).exists():
            problems.append("receipt_file_missing")

        summary = receipt.get("summary") or {}
        if summary.get("recommendation") != "KEEP":
            problems.append("summary_not_loaded")

        dashboard_response = receipt.get("dashboard_response") or {}
        if dashboard_response.get("has_html") is not True:
            problems.append("dashboard_html_missing")

        text = json.dumps(receipt).lower()
        forbidden = ["rm -rf", "git reset --hard", "git clean -fdx", "push --force"]
        for item in forbidden:
            if item in text:
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main():
    parser = argparse.ArgumentParser(
        description="Create execution receipts for the latest recovery plan dashboard."
    )
    parser.add_argument("--root")
    parser.add_argument("--receipt-dir")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_dashboard_receipts()
        if problems:
            print("latest recovery plan dashboard execution receipts FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("latest recovery plan dashboard execution receipts OK")
        return 0

    root = Path(args.root).expanduser().resolve() if args.root else None
    receipt_dir = Path(args.receipt_dir).expanduser().resolve() if args.receipt_dir else None

    receipt = build_latest_recovery_dashboard_execution_receipt(
        root=root,
        receipt_dir=receipt_dir,
        write=args.write,
    )

    if args.json or args.write:
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print("Latest recovery plan dashboard execution receipt")
        print(f"status: {receipt.get('status')}")
        print(f"ok: {receipt.get('ok')}")
        if receipt.get("receipt_path"):
            print(f"receipt_path: {receipt.get('receipt_path')}")

    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
