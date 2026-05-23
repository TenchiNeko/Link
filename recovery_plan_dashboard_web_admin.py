
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


def recovery_plan_dashboard_web_admin_command(prompt: str) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    if not any(trigger in text for trigger in RECOVERY_DASHBOARD_TRIGGERS):
        return None

    command = ["python3", "recovery_plan_dashboard_card.py", "--sample"]

    if "--json" in text or " as json" in f" {text} ":
        command.append("--json")

    return command


def build_recovery_plan_dashboard_web_response(plan: dict[str, Any] | None = None) -> dict[str, Any]:
    from recovery_plan_dashboard_card import (
        recovery_plan_dashboard_payload,
        render_recovery_plan_dashboard_card,
        sample_plan,
    )

    selected_plan = plan if isinstance(plan, dict) else sample_plan()
    payload = recovery_plan_dashboard_payload(selected_plan)
    html = render_recovery_plan_dashboard_card(selected_plan)

    return {
        "kind": "recovery_plan_dashboard_card",
        "safe": True,
        "destructive": False,
        "payload": payload,
        "html": html,
        "summary": f"Recovery plan dashboard card ready: {payload.get('recommendation', 'UNKNOWN')}",
    }


def render_recovery_plan_dashboard_web_response(plan: dict[str, Any] | None = None) -> str:
    response = build_recovery_plan_dashboard_web_response(plan)
    return str(response["html"])


def self_test() -> list[str]:
    problems = []

    command = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard")
    if command != ["python3", "recovery_plan_dashboard_card.py", "--sample"]:
        problems.append("dashboard_command_failed")

    command_json = recovery_plan_dashboard_web_admin_command("show recovery plan dashboard --json")
    if command_json != ["python3", "recovery_plan_dashboard_card.py", "--sample", "--json"]:
        problems.append("dashboard_json_command_failed")

    unrelated = recovery_plan_dashboard_web_admin_command("show normal status")
    if unrelated is not None:
        problems.append("unrelated_prompt_should_not_route")

    response = build_recovery_plan_dashboard_web_response()
    if not response.get("safe"):
        problems.append("response_not_marked_safe")
    if response.get("destructive"):
        problems.append("response_marked_destructive")
    if response.get("kind") != "recovery_plan_dashboard_card":
        problems.append("response_kind_failed")
    if 'data-link-card="recovery-plan"' not in str(response.get("html", "")):
        problems.append("card_marker_missing")
    if "<form" in str(response.get("html", "")).lower():
        problems.append("dashboard_response_must_not_expose_form")
    if "git reset --hard" in str(response.get("html", "")):
        problems.append("dashboard_response_must_not_suggest_destructive_reset")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Recovery plan dashboard web admin integration.")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--prompt", default="")
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
        if args.json:
            print(json.dumps({"command": command}, indent=2, sort_keys=True))
        else:
            print(" ".join(command) if command else "no route")
        return 0

    response = build_recovery_plan_dashboard_web_response()
    if args.json:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response["html"])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
