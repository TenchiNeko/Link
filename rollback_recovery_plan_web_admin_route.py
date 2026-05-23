
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any


RECOVERY_PLAN_TRIGGERS = (
    "rollback recovery plan",
    "recovery plan",
    "export rollback plan",
    "export recovery plan",
    "guarded recovery plan",
    "rollback plan",
)


def _wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return " json " in text or "--json" in text or " as json " in text


def rollback_recovery_plan_web_admin_command(prompt: str) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    if not any(trigger in text for trigger in RECOVERY_PLAN_TRIGGERS):
        return None

    command = ["python3", "rollback_recovery_plan.py"]

    if _wants_json(prompt):
        command.append("--json")

    return command


def build_route_result(prompt: str) -> dict[str, Any]:
    command = rollback_recovery_plan_web_admin_command(prompt)
    routed = command is not None

    return {
        "route": "rollback_recovery_plan" if routed else None,
        "routed": routed,
        "command": command,
        "prompt": prompt,
        "guarded": True,
        "destructive": False,
        "requires_manual_acceptance": False,
        "description": (
            "Exports a guarded rollback recovery plan without executing destructive git commands."
            if routed
            else "Prompt did not match rollback recovery plan routing."
        ),
    }


def self_test() -> list[str]:
    problems = []

    command = rollback_recovery_plan_web_admin_command("export rollback recovery plan")
    if command != ["python3", "rollback_recovery_plan.py"]:
        problems.append("basic_recovery_plan_route_failed")

    json_command = rollback_recovery_plan_web_admin_command("export rollback recovery plan as json")
    if json_command != ["python3", "rollback_recovery_plan.py", "--json"]:
        problems.append("json_recovery_plan_route_failed")

    ignored = rollback_recovery_plan_web_admin_command("show status")
    if ignored is not None:
        problems.append("unrelated_prompt_was_routed")

    result = build_route_result("guarded recovery plan")
    if not result.get("routed"):
        problems.append("route_result_not_routed")
    if result.get("destructive"):
        problems.append("route_result_marked_destructive")
    if result.get("guarded") is not True:
        problems.append("route_result_not_guarded")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Route web-admin rollback recovery plan prompts.")
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("rollback recovery plan web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("rollback recovery plan web admin route OK")
        return 0

    prompt = " ".join(args.prompt)
    result = build_route_result(prompt)

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        command = result.get("command")
        if command:
            print(" ".join(command))
        else:
            print("no rollback recovery plan route")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
