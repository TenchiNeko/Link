
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def default_recovery_plan_dir() -> Path:
    configured = os.environ.get("LINK_ROLLBACK_RECOVERY_PLAN_DIR")
    if configured:
        return Path(configured)
    return ROOT / ".link_evidence" / "rollback_recovery_plans"


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _load_advice_from_advisor() -> dict[str, Any]:
    try:
        from evidence_rollback_advisor import build_rollback_advice
    except Exception as exc:
        return {
            "recommendation": "UNKNOWN",
            "reason": f"rollback advisor unavailable: {exc}",
            "current_head": "",
            "rollback_candidate": "",
            "latest_archive": "",
            "latest_status": "",
        }

    try:
        advice = build_rollback_advice()
        if isinstance(advice, dict):
            return advice
    except Exception as exc:
        return {
            "recommendation": "UNKNOWN",
            "reason": f"rollback advisor failed: {exc}",
            "current_head": "",
            "rollback_candidate": "",
            "latest_archive": "",
            "latest_status": "",
        }

    return {
        "recommendation": "UNKNOWN",
        "reason": "rollback advisor returned non-dict advice",
        "current_head": "",
        "rollback_candidate": "",
        "latest_archive": "",
        "latest_status": "",
    }


def build_guarded_recovery_plan(advice: dict[str, Any] | None = None) -> dict[str, Any]:
    advice = dict(advice or _load_advice_from_advisor())

    recommendation = _safe_text(advice.get("recommendation")) or "UNKNOWN"
    current_head = _safe_text(advice.get("current_head"))
    rollback_candidate = _safe_text(advice.get("rollback_candidate"))
    latest_archive = _safe_text(advice.get("latest_archive"))
    latest_status = _safe_text(advice.get("latest_status"))
    reason = _safe_text(advice.get("reason"))

    can_offer_reset = recommendation == "ADVISE_ROLLBACK_TO_LAST_PASS" and bool(rollback_candidate)

    guardrails = [
        "Do not run destructive git commands automatically.",
        "Inspect repo status before any recovery action.",
        "Preserve current HEAD and evidence references in this plan.",
        "Prefer a new branch or manual review before hard reset.",
        "Only run destructive commands after a human explicitly accepts the plan.",
    ]

    inspection_commands = [
        "git status --short",
        "git log --oneline -10",
        "python3 link_upgrade_registry.py",
        "python3 link_healthcheck.py",
    ]

    suggested_commands = [
        "git status --short",
        f"git branch backup-before-rollback-{current_head or 'HEAD'}",
    ]

    if can_offer_reset:
        suggested_commands.extend([
            f"git diff --stat {rollback_candidate}..HEAD",
            f"git log --oneline {rollback_candidate}..HEAD",
            f"# REVIEW ONLY: git reset --hard {rollback_candidate}",
        ])
    else:
        suggested_commands.append("# No rollback reset command suggested by current evidence.")

    plan = {
        "plan_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source": "rollback_recovery_plan",
        "status": "guarded",
        "recommendation": recommendation,
        "reason": reason,
        "current_head": current_head,
        "rollback_candidate": rollback_candidate,
        "latest_archive": latest_archive,
        "latest_status": latest_status,
        "guardrails": guardrails,
        "inspection_commands": inspection_commands,
        "suggested_commands": suggested_commands,
        "destructive_commands_are_commented": True,
        "requires_manual_acceptance": True,
    }

    return plan


def render_recovery_plan_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Link Rollback Recovery Plan",
        "",
        f"- Recommendation: `{plan.get('recommendation', 'UNKNOWN')}`",
        f"- Reason: {plan.get('reason', '')}",
        f"- Current HEAD: `{plan.get('current_head', '-') or '-'}`",
        f"- Rollback candidate: `{plan.get('rollback_candidate', '-') or '-'}`",
        f"- Latest evidence: `{plan.get('latest_archive', '-') or '-'}`",
        f"- Latest evidence status: `{plan.get('latest_status', '-') or '-'}`",
        f"- Requires manual acceptance: `{plan.get('requires_manual_acceptance', True)}`",
        "",
        "## Guardrails",
        "",
    ]

    for item in plan.get("guardrails", []):
        lines.append(f"- {item}")

    lines.extend(["", "## Inspection commands", "", "```bash"])
    lines.extend(plan.get("inspection_commands", []))
    lines.extend(["```", "", "## Suggested recovery commands", "", "```bash"])
    lines.extend(plan.get("suggested_commands", []))
    lines.extend(["```", ""])

    return "\n".join(lines)


def validate_recovery_plan(plan: dict[str, Any]) -> list[str]:
    problems = []

    if plan.get("plan_version") != "1.0":
        problems.append("missing_plan_version")

    if plan.get("status") != "guarded":
        problems.append("plan_not_guarded")

    if not plan.get("requires_manual_acceptance"):
        problems.append("manual_acceptance_not_required")

    if not plan.get("destructive_commands_are_commented"):
        problems.append("destructive_commands_not_marked_commented")

    commands = "\n".join(plan.get("suggested_commands", []))
    if "git reset --hard" in commands and "# REVIEW ONLY: git reset --hard" not in commands:
        problems.append("unguarded_hard_reset_present")

    if "git clean -fd" in commands:
        problems.append("git_clean_not_allowed_in_recovery_plan")

    if not plan.get("guardrails"):
        problems.append("missing_guardrails")

    return problems


def export_rollback_recovery_plan(
    output_dir: str | Path | None = None,
    advice: dict[str, Any] | None = None,
) -> Path:
    root = Path(output_dir) if output_dir is not None else default_recovery_plan_dir()
    root.mkdir(parents=True, exist_ok=True)

    plan = build_guarded_recovery_plan(advice)
    problems = validate_recovery_plan(plan)
    if problems:
        raise ValueError("rollback recovery plan invalid: " + ", ".join(problems))

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    plan_dir = root / f"rollback_recovery_plan_{stamp}"
    counter = 1
    while plan_dir.exists():
        counter += 1
        plan_dir = root / f"rollback_recovery_plan_{stamp}_{counter}"

    plan_dir.mkdir(parents=True)

    (plan_dir / "rollback_recovery_plan.json").write_text(
        json.dumps(plan, indent=2, sort_keys=True) + "\n"
    )
    (plan_dir / "rollback_recovery_plan.md").write_text(
        render_recovery_plan_markdown(plan)
    )

    return plan_dir


def self_test() -> list[str]:
    problems = []

    sample = {
        "recommendation": "ADVISE_ROLLBACK_TO_LAST_PASS",
        "reason": "sample failed healthcheck",
        "current_head": "HEADSHA",
        "rollback_candidate": "GOODSHA",
        "latest_archive": "sample_archive",
        "latest_status": "failed",
    }

    plan = build_guarded_recovery_plan(sample)
    problems.extend(validate_recovery_plan(plan))

    rendered = render_recovery_plan_markdown(plan)
    if "git reset --hard GOODSHA" not in rendered:
        problems.append("markdown_missing_review_reset")
    if "# REVIEW ONLY: git reset --hard GOODSHA" not in rendered:
        problems.append("markdown_reset_not_commented_for_review")

    no_reset = build_guarded_recovery_plan({
        "recommendation": "NO_ROLLBACK_NEEDED",
        "reason": "sample pass",
        "current_head": "HEADSHA",
        "rollback_candidate": "",
    })
    no_reset_commands = "\n".join(no_reset.get("suggested_commands", []))
    if "git reset --hard" in no_reset_commands:
        problems.append("no_rollback_case_includes_reset")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Export guarded rollback recovery plans.")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("rollback recovery plan exporter FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("rollback recovery plan exporter OK")
        return 0

    path = export_rollback_recovery_plan(args.output_dir)
    if args.json:
        print(json.dumps({"status": "ok", "path": str(path)}, indent=2, sort_keys=True))
    else:
        print(f"rollback recovery plan exported: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
