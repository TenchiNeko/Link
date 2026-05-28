#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def default_recovery_plan_root() -> Path:
    configured = os.environ.get("LINK_ROLLBACK_RECOVERY_PLAN_DIR")
    if configured:
        return Path(configured).expanduser().resolve()

    try:
        from rollback_recovery_plan import default_recovery_plan_dir

        return Path(default_recovery_plan_dir()).expanduser().resolve()
    except Exception:
        return (ROOT / ".link_recovery_plans").resolve()


def parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def load_json_file(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text())
    except Exception:
        return None

    if isinstance(data, dict):
        return data
    return None


def plan_created_at(data: dict[str, Any], path: Path) -> datetime:
    for key in (
        "created_at",
        "generated_at",
        "timestamp",
        "archived_at",
        "updated_at",
    ):
        parsed = parse_datetime(data.get(key))
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)

    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


def iter_recovery_plan_files(root: Path | None = None) -> list[Path]:
    base = Path(root) if root is not None else default_recovery_plan_root()
    if not base.exists():
        return []

    candidates: list[Path] = []
    for path in base.rglob("*.json"):
        lowered = path.name.lower()
        if "plan" in lowered or "recovery" in lowered or "rollback" in lowered:
            candidates.append(path)

    return sorted(candidates)


def find_latest_recovery_plan(root: Path | None = None) -> dict[str, Any]:
    latest_path: Path | None = None
    latest_data: dict[str, Any] | None = None
    latest_time: datetime | None = None

    for path in iter_recovery_plan_files(root):
        data = load_json_file(path)
        if data is None:
            continue

        created = plan_created_at(data, path)
        if latest_time is None or created > latest_time:
            latest_path = path
            latest_data = data
            latest_time = created

    if latest_path is None or latest_data is None or latest_time is None:
        return {
            "found": False,
            "path": "",
            "created_at": "",
            "plan": {},
        }

    return {
        "found": True,
        "path": str(latest_path),
        "created_at": latest_time.isoformat(),
        "plan": latest_data,
    }


def first_value(data: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def list_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, dict):
        return len(value)
    return 0


def summarize_latest_recovery_plan(root: Path | None = None) -> dict[str, Any]:
    latest = find_latest_recovery_plan(root)
    plan = latest.get("plan") if isinstance(latest.get("plan"), dict) else {}

    if not latest.get("found"):
        return {
            "found": False,
            "status": "missing",
            "message": "No rollback recovery plan was found.",
            "path": "",
            "created_at": "",
            "rollback_candidate": "",
            "current_head": "",
            "recommendation": "NO_PLAN_FOUND",
            "guardrail_count": 0,
            "command_count": 0,
        }

    rollback_candidate = first_value(
        plan,
        (
            "rollback_candidate",
            "target_commit",
            "safe_commit",
            "candidate",
        ),
        "",
    )
    current_head = first_value(
        plan,
        (
            "current_head",
            "head",
            "current_commit",
        ),
        "",
    )
    recommendation = first_value(
        plan,
        (
            "recommendation",
            "action",
            "status",
        ),
        "REVIEW_PLAN",
    )

    command_count = list_count(plan.get("commands"))
    if command_count == 0:
        command_count = list_count(plan.get("recovery_commands"))

    guardrail_count = list_count(plan.get("guardrails"))
    if guardrail_count == 0:
        guardrail_count = list_count(plan.get("checks"))

    return {
        "found": True,
        "status": "ready",
        "message": "Latest rollback recovery plan loaded.",
        "path": latest.get("path", ""),
        "created_at": latest.get("created_at", ""),
        "rollback_candidate": rollback_candidate,
        "current_head": current_head,
        "recommendation": recommendation,
        "guardrail_count": guardrail_count,
        "command_count": command_count,
    }


def render_latest_recovery_plan_card(summary: dict[str, Any]) -> str:
    status = escape(str(summary.get("status", "unknown")))
    message = escape(str(summary.get("message", "")))
    path = escape(str(summary.get("path", "")))
    created_at = escape(str(summary.get("created_at", "")))
    recommendation = escape(str(summary.get("recommendation", "")))
    rollback_candidate = escape(str(summary.get("rollback_candidate", "")))
    current_head = escape(str(summary.get("current_head", "")))
    guardrail_count = escape(str(summary.get("guardrail_count", 0)))
    command_count = escape(str(summary.get("command_count", 0)))

    return "\n".join(
        [
            '<section class="dashboard-card latest-recovery-plan-card" data-link-card="latest-recovery-plan">',
            "  <h2>Latest Recovery Plan</h2>",
            f'  <p class="status">{status}</p>',
            f'  <p class="message">{message}</p>',
            "  <dl>",
            f"    <dt>Recommendation</dt><dd>{recommendation}</dd>",
            f"    <dt>Current head</dt><dd>{current_head}</dd>",
            f"    <dt>Rollback candidate</dt><dd>{rollback_candidate}</dd>",
            f"    <dt>Created</dt><dd>{created_at}</dd>",
            f"    <dt>Commands</dt><dd>{command_count}</dd>",
            f"    <dt>Guardrails</dt><dd>{guardrail_count}</dd>",
            f"    <dt>Path</dt><dd>{path}</dd>",
            "  </dl>",
            "</section>",
        ]
    )


def validate_latest_recovery_plan_loader() -> list[str]:
    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        older = root / "older_recovery_plan.json"
        newer = root / "newer_recovery_plan.json"

        older.write_text(
            json.dumps(
                {
                    "created_at": "2026-01-01T00:00:00+00:00",
                    "recommendation": "OLD",
                    "rollback_candidate": "old123",
                    "commands": ["echo old"],
                }
            )
        )
        newer.write_text(
            json.dumps(
                {
                    "created_at": "2026-01-02T00:00:00+00:00",
                    "recommendation": "REVIEW_PLAN",
                    "rollback_candidate": "new456",
                    "current_head": "head789",
                    "commands": ["echo one", "echo two"],
                    "guardrails": ["healthcheck"],
                }
            )
        )

        summary = summarize_latest_recovery_plan(root)
        if not summary.get("found"):
            problems.append("expected latest recovery plan to be found")
        if summary.get("rollback_candidate") != "new456":
            problems.append("latest recovery plan selection failed")
        if summary.get("command_count") != 2:
            problems.append("command count mismatch")
        if summary.get("guardrail_count") != 1:
            problems.append("guardrail count mismatch")

        card = render_latest_recovery_plan_card(summary)
        if 'data-link-card="latest-recovery-plan"' not in card:
            problems.append("dashboard card marker missing")
        if "new456" not in card:
            problems.append("dashboard card missing rollback candidate")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Load and render the latest rollback recovery plan."
    )
    parser.add_argument("--root", default="")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_latest_recovery_plan_loader()
        if problems:
            print("latest recovery plan loader FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("latest recovery plan loader OK")
        return 0

    root = Path(args.root).expanduser().resolve() if args.root else None
    summary = summarize_latest_recovery_plan(root)

    if args.html:
        print(render_latest_recovery_plan_card(summary))
        return 0

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0

    print(f"status: {summary.get('status')}")
    print(f"message: {summary.get('message')}")
    print(f"recommendation: {summary.get('recommendation')}")
    print(f"rollback_candidate: {summary.get('rollback_candidate')}")
    print(f"current_head: {summary.get('current_head')}")
    print(f"path: {summary.get('path')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
