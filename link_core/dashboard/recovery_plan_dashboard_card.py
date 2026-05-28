
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from html import escape
from pathlib import Path
from typing import Any


def _first(data: dict[str, Any], keys: tuple[str, ...], default: Any = "") -> Any:
    for key in keys:
        value = data.get(key)
        if value not in (None, ""):
            return value
    return default


def _class_for_recommendation(recommendation: str) -> str:
    rec = (recommendation or "").upper()
    if rec in {"NO_ROLLBACK_NEEDED", "PLAN_ONLY", "SAFE_PLAN_READY"}:
        return "ok"
    if rec in {"ADVISE_ROLLBACK_TO_LAST_PASS", "ROLLBACK_AVAILABLE", "RECOVERY_RECOMMENDED"}:
        return "warn"
    if rec in {"NO_SAFE_ROLLBACK_TARGET", "BLOCKED", "UNKNOWN"}:
        return "danger"
    return "neutral"


def recovery_plan_dashboard_payload(plan: dict[str, Any]) -> dict[str, Any]:
    advice = plan.get("advice") if isinstance(plan.get("advice"), dict) else {}

    recommendation = (
        _first(plan, ("recommendation", "status", "action"))
        or _first(advice, ("recommendation", "status", "action"))
        or "UNKNOWN"
    )

    commands = plan.get("commands")
    if not isinstance(commands, list):
        commands = plan.get("manual_commands")
    if not isinstance(commands, list):
        commands = []

    warnings = plan.get("warnings")
    if not isinstance(warnings, list):
        warnings = plan.get("guards")
    if not isinstance(warnings, list):
        warnings = []

    return {
        "title": _first(plan, ("title",), "Rollback Recovery Plan"),
        "recommendation": str(recommendation),
        "status_class": _class_for_recommendation(str(recommendation)),
        "created_at": str(_first(plan, ("created_at", "timestamp", "generated_at"), "-")),
        "current_head": str(
            _first(plan, ("current_head", "head", "current_commit"))
            or _first(advice, ("current_head", "head", "current_commit"), "-")
        ),
        "rollback_candidate": str(
            _first(plan, ("rollback_candidate", "target_commit", "last_pass_commit"))
            or _first(advice, ("rollback_candidate", "target_commit", "last_pass_commit"), "-")
        ),
        "latest_evidence": str(
            _first(plan, ("latest_evidence", "latest_archive", "evidence_archive"))
            or _first(advice, ("latest_evidence", "latest_archive", "evidence_archive"), "-")
        ),
        "guarded": bool(plan.get("guarded", True)),
        "destructive": bool(plan.get("destructive", False)),
        "commands": [str(command) for command in commands],
        "warnings": [str(warning) for warning in warnings],
    }


def render_recovery_plan_dashboard_card(plan: dict[str, Any]) -> str:
    payload = recovery_plan_dashboard_payload(plan)
    status_class = escape(payload["status_class"])

    command_items = "".join(
        f"<li><code>{escape(command)}</code></li>"
        for command in payload["commands"][:8]
    ) or "<li><em>No manual commands recorded.</em></li>"

    warning_items = "".join(
        f"<li>{escape(warning)}</li>"
        for warning in payload["warnings"][:8]
    ) or "<li>Plan is guarded and does not execute destructive commands automatically.</li>"

    guarded_label = "guarded" if payload["guarded"] else "unguarded"
    destructive_label = "destructive" if payload["destructive"] else "non-destructive"

    lines = []
    lines.append(f'<section class="dashboard-card recovery-plan-card {status_class}" data-link-card="recovery-plan">')
    lines.append("  <header>")
    lines.append(f'    <h2>{escape(payload["title"])}</h2>')
    lines.append(f'    <span class="badge {status_class}">{escape(payload["recommendation"])}</span>')
    lines.append("  </header>")
    lines.append("  <dl>")
    lines.append(f'    <dt>Created</dt><dd>{escape(payload["created_at"])}</dd>')
    lines.append(f'    <dt>Current HEAD</dt><dd><code>{escape(payload["current_head"])}</code></dd>')
    lines.append(f'    <dt>Rollback candidate</dt><dd><code>{escape(payload["rollback_candidate"])}</code></dd>')
    lines.append(f'    <dt>Latest evidence</dt><dd><code>{escape(payload["latest_evidence"])}</code></dd>')
    lines.append(f'    <dt>Safety</dt><dd>{escape(guarded_label)} / {escape(destructive_label)}</dd>')
    lines.append("  </dl>")
    lines.append("  <h3>Manual recovery steps</h3>")
    lines.append(f"  <ol>{command_items}</ol>")
    lines.append("  <h3>Guards</h3>")
    lines.append(f"  <ul>{warning_items}</ul>")
    lines.append("</section>")
    return "\n".join(lines)


def sample_plan() -> dict[str, Any]:
    return {
        "title": "Rollback Recovery Plan",
        "recommendation": "PLAN_ONLY",
        "created_at": "2026-05-22T20:00:00Z",
        "current_head": "abc1234",
        "rollback_candidate": "def5678",
        "latest_evidence": "healthcheck_pass_archive",
        "guarded": True,
        "destructive": False,
        "commands": [
            "git status --short",
            "git log --oneline -5",
            "git checkout -b recovery/review def5678",
        ],
        "warnings": [
            "Review the plan before running any command.",
            "No destructive command is executed by this dashboard card.",
        ],
    }


def self_test() -> list[str]:
    problems = []

    fixture = sample_plan()
    fixture["commands"].append("<script>danger</script>")

    payload = recovery_plan_dashboard_payload(fixture)
    if payload["recommendation"] != "PLAN_ONLY":
        problems.append("payload_recommendation_failed")
    if payload["guarded"] is not True:
        problems.append("payload_guarded_failed")
    if payload["destructive"] is not False:
        problems.append("payload_destructive_failed")

    html = render_recovery_plan_dashboard_card(fixture)
    if 'data-link-card="recovery-plan"' not in html:
        problems.append("card_marker_missing")
    if "PLAN_ONLY" not in html:
        problems.append("recommendation_missing")
    if "<script>" in html or "</script>" in html:
        problems.append("html_not_escaped")
    if "<form" in html.lower():
        problems.append("card_should_not_render_forms")
    if "git reset --hard" in html:
        problems.append("card_should_not_suggest_destructive_reset")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a guarded rollback recovery plan dashboard card.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sample", action="store_true")
    parser.add_argument("plan_file", nargs="?")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("recovery plan dashboard card FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("recovery plan dashboard card OK")
        return 0

    if args.sample or not args.plan_file:
        plan = sample_plan()
    else:
        plan = json.loads(Path(args.plan_file).read_text())

    if args.json:
        print(json.dumps(recovery_plan_dashboard_payload(plan), indent=2, sort_keys=True))
    else:
        print(render_recovery_plan_dashboard_card(plan))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
