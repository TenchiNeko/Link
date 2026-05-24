#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


RECOVERY_DASHBOARD_TRIGGERS = (
    "recovery plan dashboard",
    "rollback recovery dashboard",
    "show recovery plan card",
    "show rollback plan card",
    "recovery dashboard card",
    "rollback dashboard card",
)

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


def _wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def recovery_plan_dashboard_web_admin_command(prompt: str) -> list[str] | None:
    # LU47 workflow step receipt index execution receipt priority route BEGIN
    try:
        from link_workflow_step_receipt_index_receipts_web_admin import (
            command_for_workflow_step_receipt_index_execution_receipt,
        )

        workflow_step_receipt_index_execution_receipt_command = (
            command_for_workflow_step_receipt_index_execution_receipt(prompt)
        )
        if workflow_step_receipt_index_execution_receipt_command is not None:
            return workflow_step_receipt_index_execution_receipt_command
    except Exception:
        pass
    # LU47 workflow step receipt index execution receipt priority route END

    from link_workflow_step_receipt_index_web_admin import route_workflow_step_receipt_index_prompt

    workflow_step_receipt_index_response = route_workflow_step_receipt_index_prompt(prompt)
    if workflow_step_receipt_index_response is not None:
        return workflow_step_receipt_index_response

    try:
        from link_workflow_preflight_receipt_index_web_admin import (
            workflow_preflight_receipt_index_web_admin_command,
        )

        workflow_preflight_receipt_index_command = workflow_preflight_receipt_index_web_admin_command(prompt)
        if workflow_preflight_receipt_index_command:
            return workflow_preflight_receipt_index_command
    except Exception:
        pass


    from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin import (
        latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index_web_admin_command as _lu33_execution_receipt_evidence_index_command,
    )

    lu33_execution_receipt_evidence_index_command = _lu33_execution_receipt_evidence_index_command(prompt)
    if lu33_execution_receipt_evidence_index_command:
        return lu33_execution_receipt_evidence_index_command


    try:
        from latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_web_admin import (
            build_execution_receipt_command as _build_execution_receipt_command,
        )

        _execution_receipt_command = _build_execution_receipt_command(prompt)
        if _execution_receipt_command:
            return _execution_receipt_command
    except Exception:
        pass

    try:
        from latest_recovery_plan_dashboard_receipt_evidence_index_web_admin import (
            latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command,
        )

        evidence_index_command = (
            latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_command(prompt)
        )
        if evidence_index_command is not None:
            return evidence_index_command
    except Exception:
        pass

    text = (prompt or "").strip().lower()
    if not text:
        return None

    if any(trigger in text for trigger in LATEST_RECOVERY_DASHBOARD_TRIGGERS):
        cmd = ["python3", "recovery_plan_latest_dashboard_integration.py"]
        cmd.append("--json" if _wants_json(text) else "--html")
        return cmd

    if any(trigger in text for trigger in RECOVERY_DASHBOARD_TRIGGERS):
        cmd = ["python3", "recovery_plan_dashboard_web_admin.py"]
        cmd.append("--json" if _wants_json(text) else "--sample")
        return cmd

    return None


def build_recovery_plan_dashboard_web_response(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    from recovery_plan_dashboard_card import (
        recovery_plan_dashboard_payload,
        render_recovery_plan_dashboard_card,
        sample_plan,
    )

    selected_plan = plan or sample_plan()
    payload = recovery_plan_dashboard_payload(selected_plan)
    card_html = render_recovery_plan_dashboard_card(selected_plan)

    html = (
        '<section class="dashboard-card recovery-plan-dashboard-web-admin" '
        'data-link-card="recovery-plan-dashboard" '
        'data-link-destructive="false">'
        "<h2>Recovery Plan Dashboard</h2>"
        f"{card_html}"
        "</section>"
    )

    return {
        "ok": True,
        "kind": "recovery_plan_dashboard_web_admin",
        "non_destructive": True,
        "data_link_card": "recovery-plan-dashboard",
        "payload": payload,
        "html": html,
    }


def render_recovery_plan_dashboard_web_response(plan: dict[str, Any] | None = None) -> str:
    return str(build_recovery_plan_dashboard_web_response(plan).get("html", ""))


def self_test() -> list[str]:
    problems: list[str] = []

    command = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard")
    if not command or "recovery_plan_dashboard_web_admin.py" not in " ".join(command):
        problems.append("dashboard_command_failed")

    json_command = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard as json")
    if not json_command or "--json" not in json_command:
        problems.append("dashboard_json_command_failed")

    latest_command = recovery_plan_dashboard_web_admin_command("show latest recovery plan dashboard")
    if not latest_command or "recovery_plan_latest_dashboard_integration.py" not in " ".join(latest_command):
        problems.append("latest_dashboard_command_failed")

    latest_json_command = recovery_plan_dashboard_web_admin_command(
        "show latest recovery plan dashboard as json"
    )
    if not latest_json_command or "--json" not in latest_json_command:
        problems.append("latest_dashboard_json_command_failed")

    response = build_recovery_plan_dashboard_web_response()
    html = str(response.get("html", ""))

    if not response.get("non_destructive"):
        problems.append("dashboard_response_not_non_destructive")

    if 'data-link-card="recovery-plan-dashboard"' not in html:
        problems.append("dashboard_card_marker_missing")

    lowered = html.lower()
    for forbidden in ("<form", "git reset --hard", "git clean -fdx", "push --force"):
        if forbidden in lowered:
            problems.append(f"dashboard_contains_forbidden_content:{forbidden}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Recovery plan dashboard web admin integration."
    )
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt")
    parser.add_argument("--sample", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("recovery plan dashboard web admin integration FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("recovery plan dashboard web admin integration OK")
        return 0

    if args.prompt:
        command = recovery_plan_dashboard_web_admin_command(args.prompt)
        print(json.dumps({"command": command}, indent=2, sort_keys=True))
        return 0

    response = build_recovery_plan_dashboard_web_response()

    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
