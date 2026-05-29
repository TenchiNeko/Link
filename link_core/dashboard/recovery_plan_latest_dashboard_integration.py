#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


LATEST_RECOVERY_DASHBOARD_TRIGGERS = (
    "latest recovery plan dashboard",
    "latest rollback plan dashboard",
    "latest rollback recovery dashboard",
    "show latest recovery plan",
    "show latest rollback plan",
    "show latest recovery dashboard",
    "show latest rollback dashboard",
    "latest recovery plan card",
    "latest rollback plan card",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def latest_recovery_plan_dashboard_web_admin_command(prompt: str) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    if any(trigger in text for trigger in LATEST_RECOVERY_DASHBOARD_TRIGGERS):
        cmd = ["python3", "recovery_plan_latest_dashboard_integration.py"]
        cmd.append("--json" if wants_json(text) else "--html")
        return cmd

    return None


def _load_latest_summary(root: Path | None = None) -> dict[str, Any]:
    from latest_recovery_plan_loader import summarize_latest_recovery_plan

    try:
        return summarize_latest_recovery_plan(root)
    except Exception as exc:
        return {
            "found": False,
            "status": "ERROR",
            "recommendation": "UNAVAILABLE",
            "reason": f"Could not load latest recovery plan: {exc}",
            "error": str(exc),
        }


def _render_latest_card(summary: dict[str, Any]) -> str:
    from latest_recovery_plan_loader import render_latest_recovery_plan_card

    try:
        inner = render_latest_recovery_plan_card(summary)
    except Exception as exc:
        inner = (
            '<section class="dashboard-card latest-recovery-plan-card error">'
            "<h2>Latest Recovery Plan</h2>"
            f"<p>Could not render latest recovery plan: {str(exc)}</p>"
            "</section>"
        )

    return (
        '<section class="dashboard-card recovery-plan-latest-dashboard" '
        'data-link-card="recovery-plan-latest-dashboard" '
        'data-link-destructive="false">'
        "<h2>Latest Recovery Plan Dashboard</h2>"
        f"{inner}"
        "</section>"
    )


def build_latest_recovery_plan_dashboard_response(root: Path | None = None) -> dict[str, Any]:
    summary = _load_latest_summary(root)
    html = _render_latest_card(summary)

    return {
        "ok": summary.get("status") != "ERROR",
        "kind": "latest_recovery_plan_dashboard",
        "non_destructive": True,
        "data_link_card": "recovery-plan-latest-dashboard",
        "summary": summary,
        "html": html,
    }


def render_latest_recovery_plan_dashboard_response(root: Path | None = None) -> str:
    return str(build_latest_recovery_plan_dashboard_response(root).get("html", ""))


def sample_recovery_plan() -> dict[str, Any]:
    return {
        "created_at": "2026-05-23T10:00:00Z",
        "status": "READY",
        "recommendation": "NO_ROLLBACK_NEEDED",
        "reason": "LU23 self-test fixture",
        "current_head": "abcdef1",
        "rollback_candidate": "1234567",
        "latest_archive": "healthcheck-evidence-self-test.json",
        "latest_status": "PASS",
        "guarded_commands": [
            "git status --short",
            "python3 link_healthcheck.py",
        ],
        "notes": [
            "Self-test plan is non-destructive.",
            "Dashboard rendering must not expose destructive actions.",
        ],
    }


def self_test() -> list[str]:
    problems: list[str] = []

    cmd = latest_recovery_plan_dashboard_web_admin_command(
        "show latest recovery plan dashboard"
    )
    if not cmd or "recovery_plan_latest_dashboard_integration.py" not in " ".join(cmd):
        problems.append("latest recovery plan dashboard command did not route to LU23 module")

    json_cmd = latest_recovery_plan_dashboard_web_admin_command(
        "show latest recovery plan dashboard as json"
    )
    if not json_cmd or "--json" not in json_cmd:
        problems.append("latest recovery plan dashboard json command did not request JSON")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        fixture = root / "rollback_recovery_plan_self_test.json"
        fixture.write_text(json.dumps(sample_recovery_plan(), indent=2), encoding="utf-8")

        response = build_latest_recovery_plan_dashboard_response(root)
        html = str(response.get("html", ""))

        if not response.get("non_destructive"):
            problems.append("latest dashboard response must be marked non-destructive")

        if 'data-link-card="recovery-plan-latest-dashboard"' not in html:
            problems.append("latest dashboard card marker missing")

        lowered = html.lower()
        forbidden = ("git reset --hard", "git clean -fdx", "push --force", "<form")
        for item in forbidden:
            if item in lowered:
                problems.append(f"latest dashboard rendered forbidden/destructive content: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render the latest recovery plan dashboard integration."
    )
    parser.add_argument("--root")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--html", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("latest recovery plan dashboard integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("recovery plan dashboard latest-plan integration OK")
        return 0

    root = Path(args.root).expanduser().resolve() if args.root else None
    response = build_latest_recovery_plan_dashboard_response(root)

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
