#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
import tempfile
from pathlib import Path
from typing import Any


RECEIPT_WEB_ADMIN_TRIGGERS = (
    "latest recovery plan dashboard receipt",
    "latest rollback plan dashboard receipt",
    "latest recovery dashboard receipt",
    "latest rollback dashboard receipt",
    "show latest recovery plan dashboard receipt",
    "show latest rollback plan dashboard receipt",
    "latest recovery plan receipt",
    "latest rollback plan receipt",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def latest_recovery_plan_dashboard_receipt_web_admin_command(prompt: str) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    if any(trigger in text for trigger in RECEIPT_WEB_ADMIN_TRIGGERS):
        command = ["python3", "latest_recovery_plan_dashboard_receipts.py", "--write"]
        if wants_json(prompt):
            command.append("--json")
        return command

    return None


def _receipt_builder():
    import latest_recovery_plan_dashboard_receipts as receipts

    for name in (
        "build_latest_recovery_dashboard_execution_receipt",
        "build_latest_recovery_plan_dashboard_execution_receipt",
    ):
        fn = getattr(receipts, name, None)
        if fn is not None:
            return fn

    raise RuntimeError("missing LU24 receipt builder")


def _build_receipt(*, root: Path | None = None, receipt_dir: Path | None = None, write: bool = True) -> dict[str, Any]:
    builder = _receipt_builder()

    attempts = (
        {"root": root, "receipt_dir": receipt_dir, "write": write},
        {"root": root, "write": write},
        {"receipt_dir": receipt_dir, "write": write},
        {"write": write},
        {},
    )

    last_error: Exception | None = None
    for kwargs in attempts:
        clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
        try:
            receipt = builder(**clean_kwargs)
            if isinstance(receipt, dict):
                return receipt
            return {"status": "error", "ok": False, "error": "receipt_builder_returned_non_dict"}
        except TypeError as exc:
            last_error = exc
            continue

    return {
        "status": "error",
        "ok": False,
        "error": f"receipt_builder_signature_failed:{last_error}",
    }


def build_latest_recovery_plan_dashboard_receipt_web_response(
    *,
    root: Path | None = None,
    receipt_dir: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    receipt = _build_receipt(root=root, receipt_dir=receipt_dir, write=write)

    return {
        "status": "ok" if receipt.get("ok") or receipt.get("status") == "ok" else "error",
        "ok": bool(receipt.get("ok") or receipt.get("status") == "ok"),
        "kind": "latest_recovery_plan_dashboard_receipt_web_admin",
        "schema_version": 1,
        "non_destructive": True,
        "command": ["python3", "latest_recovery_plan_dashboard_receipts.py", "--write"],
        "receipt": receipt,
    }


def render_latest_recovery_plan_dashboard_receipt_web_response(response: dict[str, Any] | None = None) -> str:
    if response is None:
        response = build_latest_recovery_plan_dashboard_receipt_web_response()

    receipt = response.get("receipt") if isinstance(response.get("receipt"), dict) else {}
    summary = receipt.get("summary") if isinstance(receipt.get("summary"), dict) else {}

    status = html.escape(str(response.get("status", "")))
    ok = html.escape(str(response.get("ok", "")))
    receipt_path = html.escape(str(receipt.get("receipt_path", "")))
    recommendation = html.escape(str(summary.get("recommendation", receipt.get("recommendation", ""))))
    created_at = html.escape(str(receipt.get("created_at", summary.get("created_at", ""))))
    receipt_status = html.escape(str(receipt.get("status", "")))

    return f"""<section class="card latest-recovery-dashboard-receipt" data-link-card="latest-recovery-dashboard-receipt">
  <h2>Latest Recovery Plan Dashboard Receipt</h2>
  <p>Status: <strong>{status}</strong></p>
  <ul>
    <li>Route OK: {ok}</li>
    <li>Receipt status: {receipt_status}</li>
    <li>Recommendation: {recommendation}</li>
    <li>Created at: {created_at}</li>
    <li>Receipt path: <code>{receipt_path}</code></li>
  </ul>
</section>"""


def _write_sample_plan(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    sample = {
        "created_at": "2026-01-01T00:00:00+00:00",
        "recommendation": "safe",
        "reason": "sample receipt web admin route validation",
        "current_head": "sample-head",
        "rollback_candidate": "sample-rollback-candidate",
        "guarded_steps": ["git status --short", "python3 link_healthcheck.py"],
        "checks": ["python3 link_healthcheck.py"],
    }
    (root / "rollback_recovery_plan_sample.json").write_text(json.dumps(sample, indent=2), encoding="utf-8")


def self_test() -> list[str]:
    problems: list[str] = []

    command = latest_recovery_plan_dashboard_receipt_web_admin_command(
        "show latest recovery plan dashboard receipt"
    )
    if not command:
        problems.append("receipt_web_admin_command_missing")

    json_command = latest_recovery_plan_dashboard_receipt_web_admin_command(
        "show latest recovery plan dashboard receipt as json"
    )
    if not json_command or "--json" not in json_command:
        problems.append("receipt_web_admin_json_command_missing")

    with tempfile.TemporaryDirectory() as td:
        base = Path(td)
        root = base / "plans"
        receipt_dir = base / "receipts"
        _write_sample_plan(root)

        response = build_latest_recovery_plan_dashboard_receipt_web_response(
            root=root,
            receipt_dir=receipt_dir,
            write=True,
        )
        rendered = render_latest_recovery_plan_dashboard_receipt_web_response(response)

        if response.get("kind") != "latest_recovery_plan_dashboard_receipt_web_admin":
            problems.append("bad_response_kind")
        if response.get("non_destructive") is not True:
            problems.append("response_must_be_non_destructive")
        if response.get("status") != "ok":
            problems.append(f"response_status_not_ok:{response.get('status')}")

        receipt = response.get("receipt", {})
        if not isinstance(receipt, dict):
            problems.append("receipt_missing")
        else:
            receipt_path = receipt.get("receipt_path")
            if receipt_path and not Path(str(receipt_path)).exists():
                problems.append("receipt_path_missing")
            if receipt.get("status") != "ok" and not receipt.get("ok"):
                problems.append(f"receipt_status_not_ok:{receipt.get('status')}")

        if "latest-recovery-dashboard-receipt" not in rendered:
            problems.append("rendered_card_marker_missing")

        forbidden = ("<form", "method=\"post\"", "rm -rf", "git reset --hard", "git clean -fdx")
        low = rendered.lower()
        for item in forbidden:
            if item in low:
                problems.append(f"forbidden_text_present:{item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Latest recovery plan dashboard receipt web admin route.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--prompt", default="show latest recovery plan dashboard receipt")
    parser.add_argument("--root")
    parser.add_argument("--receipt-dir")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("latest recovery plan dashboard receipt web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("latest recovery plan dashboard receipt web admin route OK")
        return 0

    root = Path(args.root) if args.root else None
    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None
    response = build_latest_recovery_plan_dashboard_receipt_web_response(
        root=root,
        receipt_dir=receipt_dir,
        write=args.write,
    )

    if args.json or wants_json(args.prompt):
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(render_latest_recovery_plan_dashboard_receipt_web_response(response))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
