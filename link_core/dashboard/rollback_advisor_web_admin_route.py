
#!/usr/bin/env python3
from __future__ import annotations

from typing import Any


def _wants_json(prompt: str) -> bool:
    text = (prompt or "").lower()
    return " json" in f" {text} " or "--json" in text or "as json" in text


def rollback_advisor_web_admin_command(prompt: str) -> list[str] | None:
    text = (prompt or "").strip().lower()
    if not text:
        return None

    mentions_rollback = "rollback" in text or "roll back" in text
    mentions_advisor = (
        "advisor" in text
        or "advice" in text
        or "recommendation" in text
        or "recommend" in text
        or "evidence" in text
    )

    if not mentions_rollback:
        return None

    if "dashboard" in text or "panel" in text:
        cmd = ["python3", "link_rollback_advisor.py", "dashboard"]
    elif mentions_advisor or "should i" in text or "status" in text:
        cmd = ["python3", "link_rollback_advisor.py", "advise"]
    else:
        return None

    if _wants_json(prompt):
        cmd.append("--json")

    return cmd


def rollback_advisor_web_admin_plan(prompt: str) -> dict[str, Any] | None:
    cmd = rollback_advisor_web_admin_command(prompt)
    if cmd is None:
        return None

    return {
        "cmd": cmd,
        "argv": cmd,
        "action": "run_command",
        "source": "rollback_advisor_web_admin_route",
        "reason": "rollback advisor web admin command route",
    }


def self_test() -> list[str]:
    problems = []

    advise = rollback_advisor_web_admin_command("show rollback advisor")
    if advise != ["python3", "link_rollback_advisor.py", "advise"]:
        problems.append(f"advise_route_wrong::{advise!r}")

    dash = rollback_advisor_web_admin_command("show rollback advisor dashboard json")
    if dash != ["python3", "link_rollback_advisor.py", "dashboard", "--json"]:
        problems.append(f"dashboard_route_wrong::{dash!r}")

    none = rollback_advisor_web_admin_command("run normal healthcheck")
    if none is not None:
        problems.append(f"non_rollback_prompt_routed::{none!r}")

    plan = rollback_advisor_web_admin_plan("rollback recommendation")
    if not plan or plan.get("cmd") != ["python3", "link_rollback_advisor.py", "advise"]:
        problems.append("plan_missing_cmd")

    return problems


def main() -> int:
    problems = self_test()
    if problems:
        print("rollback advisor web admin route FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("rollback advisor web admin route OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
