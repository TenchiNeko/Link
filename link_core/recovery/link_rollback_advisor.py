
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def format_advice_text(advice: dict[str, Any]) -> str:
    lines = [
        "Link Rollback Advisor",
        f"recommendation: {advice.get('recommendation', 'UNKNOWN')}",
        f"reason: {advice.get('reason', '')}",
        f"current_head: {advice.get('current_head', '-')}",
        f"rollback_candidate: {advice.get('rollback_candidate', '-')}",
        f"latest_evidence: {advice.get('latest_archive', '-')} [{advice.get('latest_status', 'UNKNOWN')}]",
    ]

    actions = advice.get("safe_actions") or []
    if actions:
        lines.append("safe_actions:")
        for action in actions:
            lines.append(f"  - {action}")

    return "\n".join(lines)


def get_advice(root: str | Path | None = None) -> dict[str, Any]:
    from evidence_rollback_advisor import advise_from_archive

    return advise_from_archive(root)


def print_advice(root: str | Path | None = None, as_json: bool = False) -> int:
    advice = get_advice(root)
    if as_json:
        print(json.dumps(advice, indent=2, sort_keys=True))
    else:
        print(format_advice_text(advice))
    return 0


def print_dashboard(root: str | Path | None = None, as_json: bool = False) -> int:
    from rollback_advisor_dashboard import dashboard_payload, render_live_panel

    if as_json:
        print(json.dumps(dashboard_payload(root), indent=2, sort_keys=True))
    else:
        print(render_live_panel(root))
    return 0


def self_test() -> list[str]:
    problems = []

    sample = {
        "recommendation": "ADVISE_ROLLBACK_TO_LAST_PASS",
        "reason": "Most recent evidence failed; a prior passing healthcheck archive exists.",
        "current_head": "bad222",
        "rollback_candidate": "good111",
        "latest_archive": "20260102-fail",
        "latest_status": "FAIL",
        "safe_actions": ["Inspect diff", "Create review branch"],
    }

    text = format_advice_text(sample)
    if "Link Rollback Advisor" not in text:
        problems.append("cli_text_missing_title")
    if "ADVISE_ROLLBACK_TO_LAST_PASS" not in text:
        problems.append("cli_text_missing_recommendation")
    if "good111" not in text:
        problems.append("cli_text_missing_candidate")
    if "Inspect diff" not in text:
        problems.append("cli_text_missing_safe_action")

    try:
        import evidence_rollback_advisor  # noqa: F401
    except Exception as exc:
        problems.append(f"cannot_import_evidence_rollback_advisor::{exc}")

    try:
        import rollback_advisor_dashboard  # noqa: F401
    except Exception as exc:
        problems.append(f"cannot_import_rollback_advisor_dashboard::{exc}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Link rollback advisor CLI.")
    sub = parser.add_subparsers(dest="command")

    advise = sub.add_parser("advise", help="Print rollback advice.")
    advise.add_argument("--root", default=None, help="Healthcheck evidence archive root.")
    advise.add_argument("--json", action="store_true", help="Print JSON advice.")

    dashboard = sub.add_parser("dashboard", help="Print rollback advisor dashboard panel.")
    dashboard.add_argument("--root", default=None, help="Healthcheck evidence archive root.")
    dashboard.add_argument("--json", action="store_true", help="Print JSON dashboard payload.")

    sub.add_parser("self-test", help="Run CLI contract self-test.")

    args = parser.parse_args()

    if args.command in (None, "advise"):
        return print_advice(getattr(args, "root", None), getattr(args, "json", False))

    if args.command == "dashboard":
        return print_dashboard(args.root, args.json)

    if args.command == "self-test":
        problems = self_test()
        if problems:
            print("rollback advisor CLI FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("rollback advisor CLI OK")
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
