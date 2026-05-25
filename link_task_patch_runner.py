#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
from pathlib import Path
from typing import Any


RECEIPT_VERSION = "LU90-task-to-patch-plan-v1"
EXECUTOR_RECEIPT_VERSION = "LU91-task-to-patch-exec-v1"


def run(cmd: list[str], root: Path, timeout: int = 90) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else ""
        return 124, (out + f"\nTIMEOUT after {timeout}s").strip()
    except Exception as e:
        return 999, f"ERROR: {e}"


def letter(score: int) -> str:
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 63:
        return "D"
    if score >= 60:
        return "D-"
    return "F"


def extract_grade_context(root: Path) -> dict[str, Any]:
    path = root / "LINK_MINING_TEAM_GRADE_CONTEXT.md"
    text = path.read_text(encoding="utf-8", errors="ignore") if path.exists() else ""

    branch = re.search(r"Branch Readiness Grade\s+\*\*([^*]+)\*\*", text, re.S)
    market = re.search(r"Market-Relative Grade\s+\*\*([^*]+)\*\*", text, re.S)

    return {
        "exists": path.exists(),
        "branch_readiness_grade": branch.group(1).strip() if branch else None,
        "market_relative_grade": market.group(1).strip() if market else None,
        "mentions_task_to_patch": "task-to-patch" in text.lower(),
        "mentions_model_routing": "model routing" in text.lower(),
        "mentions_dashboard": "dashboard" in text.lower(),
    }


def classify_goal(goal: str) -> dict[str, Any]:
    g = goal.lower()

    categories: list[str] = []
    if any(x in g for x in ["doc", "readme", "agent", "context", "report", "grade"]):
        categories.append("documentation/context")
    if any(x in g for x in ["healthcheck", "registry", "lu", "smoke", "test"]):
        categories.append("verification/healthcheck")
    if any(x in g for x in ["cli", "command", "ux", "status", "dashboard"]):
        categories.append("developer UX")
    if any(x in g for x in ["patch", "runner", "execute", "task", "ticket", "diff"]):
        categories.append("task-to-patch execution")
    if any(x in g for x in ["model", "router", "openrouter", "ollama", "local"]):
        categories.append("model routing")
    if any(x in g for x in ["delete", "clean", "reset", "force", "rm -rf", "chmod"]):
        categories.append("destructive-risk")

    if not categories:
        categories.append("general maintenance")

    risk = "low"
    if "destructive-risk" in categories:
        risk = "high"
    elif any(x in categories for x in ["verification/healthcheck", "task-to-patch execution", "model routing"]):
        risk = "medium"

    worker_profile = "read_only_auditor"
    if risk == "low" and "documentation/context" in categories:
        worker_profile = "patch_worker"
    elif risk == "medium":
        worker_profile = "patch_worker"
    elif risk == "high":
        worker_profile = "qa_worker"

    return {
        "categories": categories,
        "risk_level": risk,
        "suggested_worker_profile": worker_profile,
    }


def recommended_tests(goal_info: dict[str, Any]) -> list[str]:
    tests = [
        "python3 -m py_compile link_task_patch_runner.py",
        "python3 link_task_patch_runner.py --goal \"smoke test\" --format json",
        "python3 link_healthcheck.py",
    ]

    categories = set(goal_info["categories"])

    if "verification/healthcheck" in categories:
        tests.insert(0, "python3 -m py_compile link_healthcheck.py link_upgrade_registry.py")
    if "developer UX" in categories:
        tests.append("python3 link_grade.py --format json")
    if "task-to-patch execution" in categories:
        tests.append("git diff --check")

    return tests


def required_gates(goal_info: dict[str, Any]) -> list[str]:
    gates = [
        "confirm clean working tree",
        "create or identify rollback point",
        "classify command/file/git safety before mutation",
        "human approval before file writes or git commits",
        "run targeted compile/smoke checks",
        "run full Link healthcheck",
        "produce concise diff/receipt for review",
    ]

    if goal_info["risk_level"] == "high":
        gates.insert(0, "stop for explicit Brandon approval because risk is high")
        gates.append("do not run destructive commands")

    return gates


def build_plan(root: Path, goal: str) -> dict[str, Any]:
    branch_code, branch = run(["git", "branch", "--show-current"], root)
    status_code, status = run(["git", "status", "--short"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    upstream_code, upstream = run(["git", "status", "-sb"], root)

    grade_context = extract_grade_context(root)
    goal_info = classify_goal(goal)

    clean = status_code == 0 and status.strip() == ""

    blockers: list[str] = []
    if not clean:
        blockers.append("working tree is not clean")
    if branch_code != 0:
        blockers.append("could not read current git branch")
    if head_code != 0:
        blockers.append("could not read HEAD commit")

    readiness_score = 82
    if clean:
        readiness_score += 6
    if grade_context["exists"]:
        readiness_score += 4
    if goal_info["risk_level"] == "low":
        readiness_score += 4
    elif goal_info["risk_level"] == "high":
        readiness_score -= 10
    if blockers:
        readiness_score -= min(20, len(blockers) * 8)

    readiness_score = max(0, min(100, readiness_score))

    return {
        "receipt_version": RECEIPT_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "goal": goal,
        "branch": branch if branch_code == 0 else "",
        "head": head if head_code == 0 else "",
        "upstream_state": upstream.splitlines()[0] if upstream_code == 0 and upstream else "",
        "working_tree_clean": clean,
        "blockers": blockers,
        "goal_classification": goal_info,
        "grade_context": grade_context,
        "required_gates": required_gates(goal_info),
        "recommended_tests": recommended_tests(goal_info),
        "readiness_score": readiness_score,
        "readiness_grade": letter(readiness_score),
        "next_steps": [
            "Review this plan before patching.",
            "Apply the smallest useful change only.",
            "Run the recommended tests.",
            "Commit only after healthcheck passes.",
            "Push only after confirming the final branch state.",
        ],
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Link Task-to-Patch Plan")
    lines.append("")
    lines.append(f"Generated: {plan['generated']}")
    lines.append(f"Receipt version: `{plan['receipt_version']}`")
    lines.append(f"Repository: `{plan['repo']}`")
    lines.append(f"Branch: `{plan['branch']}`")
    lines.append(f"HEAD: `{plan['head']}`")
    lines.append(f"Working tree clean: **{'yes' if plan['working_tree_clean'] else 'no'}**")
    lines.append("")
    lines.append(f"## Goal")
    lines.append("")
    lines.append(plan["goal"])
    lines.append("")
    lines.append(f"## Readiness")
    lines.append("")
    lines.append(f"Grade: **{plan['readiness_grade']} / {plan['readiness_score']}**")
    lines.append("")
    lines.append("## Classification")
    lines.append("")
    lines.append(f"- Risk level: **{plan['goal_classification']['risk_level']}**")
    lines.append(f"- Suggested worker profile: `{plan['goal_classification']['suggested_worker_profile']}`")
    lines.append("- Categories: " + ", ".join(f"`{x}`" for x in plan["goal_classification"]["categories"]))
    lines.append("")
    lines.append("## Grade Context")
    lines.append("")
    gc = plan["grade_context"]
    lines.append(f"- Grade context file found: **{'yes' if gc['exists'] else 'no'}**")
    lines.append(f"- Branch readiness grade: `{gc['branch_readiness_grade']}`")
    lines.append(f"- Market-relative grade: `{gc['market_relative_grade']}`")
    lines.append("")
    lines.append("## Required Gates")
    lines.append("")
    for gate in plan["required_gates"]:
        lines.append(f"- {gate}")
    lines.append("")
    lines.append("## Recommended Tests")
    lines.append("")
    for test in plan["recommended_tests"]:
        lines.append(f"- `{test}`")
    lines.append("")
    if plan["blockers"]:
        lines.append("## Blockers")
        lines.append("")
        for blocker in plan["blockers"]:
            lines.append(f"- {blocker}")
        lines.append("")
    lines.append("## Next Steps")
    lines.append("")
    for step in plan["next_steps"]:
        lines.append(f"- {step}")
    lines.append("")
    return "\n".join(lines)



def split_execution_command(command: str) -> list[str]:
    import shlex

    return shlex.split(command)


def is_allowed_execution_command(command: str) -> tuple[bool, str]:
    try:
        tokens = split_execution_command(command)
    except ValueError as exc:
        return False, f"could not parse command: {exc}"

    if not tokens:
        return False, "empty command"

    if any(part in command for part in [";", "&&", "||", "`", "$(", ">", "<", "|"]):
        return False, "shell chaining/redirection is not allowed"

    if tokens[:3] == ["python3", "-m", "py_compile"]:
        allowed_files = {
            "link_task_patch_runner.py",
            "link_healthcheck.py",
            "link_upgrade_registry.py",
            "link_grade.py",
            "link_research_source_inventory.py",
        }
        files = tokens[3:]
        if files and all(item in allowed_files for item in files):
            return True, "allowlisted Python compile check"
        return False, "py_compile target is not allowlisted"

    if tokens == ["python3", "link_healthcheck.py"]:
        return True, "allowlisted Link healthcheck"

    if tokens == ["python3", "link_grade.py", "--format", "json"]:
        return True, "allowlisted Link grade JSON smoke check"

    if (
        len(tokens) >= 5
        and tokens[0] == "python3"
        and tokens[1] == "link_task_patch_runner.py"
        and "--execute" not in tokens
        and "--format" in tokens
        and "json" in tokens
    ):
        return True, "allowlisted task-to-patch planner smoke check"

    if tokens == ["git", "diff", "--check"]:
        return True, "allowlisted whitespace diff check"

    if tokens == ["git", "status", "--short"]:
        return True, "allowlisted read-only git status"

    return False, "command is not in the task-to-patch executor allowlist"


def command_success(command: str, exit_code: int, output: str) -> bool:
    if exit_code == 0:
        return True

    # The planner intentionally returns 2 when the working tree is dirty.
    # During an in-progress guarded patch, that can still be a valid smoke result.
    if command.startswith("python3 link_task_patch_runner.py") and exit_code == 2:
        try:
            parsed = json.loads(output)
            return parsed.get("receipt_version") == RECEIPT_VERSION
        except Exception:
            return False

    return False


def execute_plan(
    root: Path,
    goal: str,
    approved: bool = False,
    include_full_healthcheck: bool = True,
) -> dict[str, Any]:
    plan = build_plan(root, goal)
    commands = list(plan.get("recommended_tests", []))

    if not include_full_healthcheck:
        commands = [cmd for cmd in commands if cmd != "python3 link_healthcheck.py"]

    receipt: dict[str, Any] = {
        "receipt_version": EXECUTOR_RECEIPT_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "goal": goal,
        "approved": approved,
        "plan_receipt_version": plan.get("receipt_version"),
        "working_tree_clean_at_start": plan.get("working_tree_clean"),
        "branch": plan.get("branch"),
        "head": plan.get("head"),
        "status": "blocked",
        "blockers": [],
        "commands": [],
    }

    if not approved:
        receipt["blockers"].append("executor requires --approved")
        return receipt

    all_ok = True

    for command in commands:
        allowed, reason = is_allowed_execution_command(command)
        item: dict[str, Any] = {
            "command": command,
            "decision": "allow" if allowed else "deny",
            "reason": reason,
        }

        if not allowed:
            item["exit_code"] = None
            item["output_tail"] = ""
            all_ok = False
            receipt["commands"].append(item)
            continue

        tokens = split_execution_command(command)
        exit_code, output = run(tokens, root, timeout=240)
        ok = command_success(command, exit_code, output)

        item["exit_code"] = exit_code
        item["ok"] = ok
        item["output_tail"] = "\n".join(output.splitlines()[-20:])

        if not ok:
            all_ok = False

        receipt["commands"].append(item)

    receipt["status"] = "success" if all_ok else "failed"
    return receipt


def render_execution_markdown(receipt: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Link Task-to-Patch Execution Receipt")
    lines.append("")
    lines.append(f"Generated: {receipt['generated']}")
    lines.append(f"Receipt version: `{receipt['receipt_version']}`")
    lines.append(f"Repository: `{receipt['repo']}`")
    lines.append(f"Branch: `{receipt.get('branch', '')}`")
    lines.append(f"HEAD: `{receipt.get('head', '')}`")
    lines.append(f"Approved: **{'yes' if receipt.get('approved') else 'no'}**")
    lines.append(f"Status: **{receipt.get('status')}**")
    lines.append("")
    lines.append("## Goal")
    lines.append("")
    lines.append(receipt["goal"])
    lines.append("")

    if receipt.get("blockers"):
        lines.append("## Blockers")
        lines.append("")
        for blocker in receipt["blockers"]:
            lines.append(f"- {blocker}")
        lines.append("")

    lines.append("## Commands")
    lines.append("")
    lines.append("| Command | Decision | Exit | OK |")
    lines.append("|---|---:|---:|---:|")

    for item in receipt.get("commands", []):
        exit_code = item.get("exit_code")
        exit_text = "" if exit_code is None else str(exit_code)
        ok_text = "yes" if item.get("ok") else "no"
        lines.append(
            f"| `{item['command']}` | {item['decision']} | {exit_text} | {ok_text} |"
        )

    lines.append("")
    lines.append("## Output Tails")
    lines.append("")

    for item in receipt.get("commands", []):
        lines.append(f"### `{item['command']}`")
        lines.append("")
        lines.append("```")
        lines.append(item.get("output_tail", ""))
        lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create or execute a guarded Link task-to-patch plan.")
    parser.add_argument("--goal", required=True)
    parser.add_argument("--root", default=".", help="repository root, default current directory")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--execute", action="store_true", help="execute allowlisted recommended checks")
    parser.add_argument("--approved", action="store_true", help="confirm human approval for guarded execution")
    parser.add_argument("--output", "--receipt-out", dest="receipt_out", help="optional path to write receipt")
    args = parser.parse_args()

    root = Path(args.root).resolve()

    if args.execute:
        receipt = execute_plan(root, args.goal, approved=args.approved, include_full_healthcheck=True)
        text = json.dumps(receipt, indent=2, sort_keys=True) if args.format == "json" else render_execution_markdown(receipt)

        if args.receipt_out:
            out = Path(args.receipt_out)
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text, encoding="utf-8")

        print(text)
        return 0 if receipt.get("status") == "success" else 2

    plan = build_plan(root, args.goal)
    text = json.dumps(plan, indent=2, sort_keys=True) if args.format == "json" else render_markdown(plan)

    if args.receipt_out:
        out = Path(args.receipt_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")

    print(text)
    return 0 if plan.get("working_tree_clean") else 2


if __name__ == "__main__":
    raise SystemExit(main())
