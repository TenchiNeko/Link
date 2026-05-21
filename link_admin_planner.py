#!/usr/bin/env python3
from __future__ import annotations

"""
Link Admin Planner.

Deterministic no-execute planner for turning a high-level ChatGPT/human request
into a safe Link task plan.

It does not call models.
It does not edit files.
It does not run autonomous.
It only reads repo state and emits a JSON/human plan that Link can later use to
delegate draft/review work to DeepSeek and local Qwen/Gwen while keeping Link as
the only executor.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
DELEGATE_RUNNER = "link_delegate_runner.py"

SAFETY_GATES = [
    "command_guard",
    "file_safety",
    "git_safety",
    "dirty_repo_guard",
    "expected_change_guard",
    "healthcheck",
    "doctor",
    "backup_bundle",
    "delegate_runner",
]

TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv"}
SOURCE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".html", ".css", ".sh"} | TEXT_SUFFIXES

DENY_PARTS = {
    ".git",
    ".agents/reports",
    ".agents/worktrees",
    "node_modules",
    "__pycache__",
}

FILE_RE = re.compile(
    r"`([^`]+\.[A-Za-z0-9]+)`|(?:\b(?:target\s+file|target|file|path)\s*(?::|=|-|is|should be)?\s*`?|(?<![\w./-]))([A-Za-z0-9_./-]+\.[A-Za-z0-9]+)`?",
    re.I,
)


def _run(args: list[str], timeout: int = 12) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            args,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout.strip(), p.stderr.strip()
    except Exception as exc:
        return 99, "", f"{type(exc).__name__}: {exc}"


def _git_status() -> list[str]:
    code, out, _ = _run(["git", "status", "--short", "--untracked-files=all"])
    if code != 0 or not out:
        return []
    return out.splitlines()


def _git_line(args: list[str]) -> str | None:
    code, out, _ = _run(args)
    if code != 0:
        return None
    return out.splitlines()[0] if out else None


def _safe_path(value: str) -> str | None:
    raw = str(value or "").strip().strip("`").strip()
    raw = raw.replace("\\", "/")

    if not raw or raw.startswith("/") or raw.startswith("../") or "/../" in raw:
        return None

    path = Path(raw)
    if path.suffix.lower() not in SOURCE_SUFFIXES:
        return None

    parts = set(path.parts)
    if any(part in parts for part in DENY_PARTS):
        return None
    if raw.startswith(".agents/") or raw.startswith(".git/"):
        return None

    return raw


def _target_files(prompt: str) -> list[str]:
    found: list[str] = []
    for match in FILE_RE.findall(prompt or ""):
        candidate = match[0] or match[1]
        safe = _safe_path(candidate)
        if safe and safe not in found:
            found.append(safe)
    return found


def _has_target_content(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(
        marker in lower
        for marker in [
            "content:",
            "contents:",
            "text:",
            "single line saying",
            "single line containing",
            "replace with",
            "change wording to",
        ]
    )


def _explicit_micro_patch(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(
        marker in lower
        for marker in [
            "micro patch",
            "micro-patch",
            "micro_patch",
            "[micro_patch]",
            "small patch",
            "surgical patch",
        ]
    )


def _read_only_prompt(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(
        marker in lower
        for marker in [
            "audit only",
            "read only",
            "read-only",
            "inspect ",
            "diagnose ",
            "review ",
            "summarize ",
            "status",
            "where does",
            "what happened",
            "no edits",
            "do not edit",
        ]
    )


def _broad_prompt(prompt: str) -> bool:
    lower = " ".join(str(prompt or "").lower().split())
    broad_markers = [
        "let's continue",
        "lets continue",
        "continue on the updates",
        "continue the updates",
        "keep going",
        "what next",
        "next task",
        "continue",
        "fix it",
        "patch it",
    ]
    return lower in broad_markers or any(marker == lower for marker in broad_markers)


def _specific_action(prompt: str) -> bool:
    lower = str(prompt or "").lower()
    return any(
        marker in lower
        for marker in [
            "implement ",
            "patch ",
            "add ",
            "create ",
            "write ",
            "fix ",
            "update ",
            "modify ",
        ]
    )


def _risk_for_targets(targets: list[str], prompt: str) -> str:
    # Explicit safe text targets should not become high-risk merely because
    # their replacement content mentions words like "web" or "engine".
    if targets and all(Path(t).suffix.lower() in TEXT_SUFFIXES for t in targets):
        return "low"

    lower = str(prompt or "").lower()
    risky_words = [
        "engine",
        "web",
        "route",
        "healthcheck",
        "doctor",
        "executor",
        "command guard",
        "git safety",
        "file safety",
        "api",
        "backend",
        "daemon",
    ]
    risky_files = [
        "link_web.py",
        "link_run_engine.py",
        "link_route_intelligence.py",
        "link_healthcheck.py",
        "link_doctor.py",
        "modern_command_guard.py",
        "modern_file_safety.py",
        "modern_git_safety.py",
    ]
    if any(word in lower for word in risky_words):
        return "high"
    if any(t in risky_files for t in targets):
        return "high"
    if any(Path(t).suffix.lower() in {".py", ".js", ".ts", ".tsx", ".sh"} for t in targets):
        return "medium"
    return "low"


def _latest_engine_reports(limit: int = 5) -> list[dict[str, Any]]:
    base = ROOT / ".agents" / "engine_runs"
    if not base.exists():
        return []

    dirs = [p for p in base.iterdir() if p.is_dir()]
    dirs.sort(key=lambda p: p.stat().st_mtime, reverse=True)

    reports: list[dict[str, Any]] = []
    for d in dirs[:limit]:
        report_path = d / "engine_report.json"
        item: dict[str, Any] = {
            "run_id": d.name,
            "path": str(report_path),
            "status": None,
            "phase": None,
            "exit_code": None,
            "failure_type": None,
        }
        if report_path.exists():
            try:
                data = json.loads(report_path.read_text(encoding="utf-8"))
                item.update(
                    {
                        "run_id": data.get("run_id") or d.name,
                        "status": data.get("status"),
                        "phase": data.get("phase"),
                        "exit_code": data.get("exit_code"),
                        "failure_type": data.get("failure_type")
                        or data.get("failure_summary", {}).get("failure_type"),
                    }
                )
            except Exception as exc:
                item["failure_type"] = f"unreadable_report:{type(exc).__name__}"
        reports.append(item)

    return reports


def build_plan(prompt: str) -> dict[str, Any]:
    dirty_files = _git_status()
    targets = _target_files(prompt)
    risk = _risk_for_targets(targets, prompt)

    read_only = _read_only_prompt(prompt)
    broad = _broad_prompt(prompt)
    micro = _explicit_micro_patch(prompt)
    specific = _specific_action(prompt)
    has_content = _has_target_content(prompt)

    if dirty_files:
        task_type = "audit"
        route = "audit_fastpath"
        reason = "repo_dirty_never_execute_or_delegate_patch"
    elif read_only or broad:
        task_type = "audit"
        route = "audit_fastpath"
        reason = "read_only_or_broad_prompt_guard"
    elif micro and len(targets) == 1 and Path(targets[0]).suffix.lower() in TEXT_SUFFIXES and has_content:
        task_type = "micro_patch"
        route = "micro_patch"
        reason = "explicit_micro_patch_with_one_safe_text_target"
    elif specific and targets:
        task_type = "patch_draft"
        route = "delegated_patch_review"
        reason = "specific_patch_request_requires_draft_review_before_execution"
    else:
        task_type = "audit"
        route = "audit_fastpath"
        reason = "insufficient_specificity_default_to_audit"

    if task_type == "audit":
        delegates = ["local_qwen"]
        suggested = "python3 link_audit_fast.py '<specific audit prompt>'"
    elif task_type == "micro_patch":
        delegates = ["link_micro_patch"]
        suggested = "python3 link_micro_patch.py '<prompt_file_with_exact_target_and_content>'"
    else:
        delegates = ["local_qwen", "deepseek"]
        suggested = "generate delegated patch draft, then run Link safety gates before any commit"

    if risk == "high" and "deepseek" not in delegates:
        delegates.append("deepseek")

    required_verification = [
        "python3 -m py_compile link_admin_planner.py",
        "python3 link_healthcheck.py",
        "python3 link_doctor.py",
    ]

    if targets:
        py_targets = [t for t in targets if Path(t).suffix.lower() == ".py"]
        if py_targets:
            required_verification.insert(0, "python3 -m py_compile " + " ".join(py_targets))

    return {
        "schema_version": "link_admin_plan_v1",
        "planner": "link_admin_planner.py",
        "execution_allowed": False,
        "human_confirmation_required": True,
        "prompt": prompt,
        "repo": {
            "root": str(ROOT),
            "head": _git_line(["git", "log", "-1", "--oneline", "--decorate"]),
            "safe_link_latest": _git_line(["git", "rev-parse", "--short", "safe-link-latest"]),
            "dirty": bool(dirty_files),
            "dirty_files": dirty_files,
        },
        "classification": {
            "task_type": task_type,
            "route": route,
            "risk": risk,
            "reason": reason,
            "read_only_detected": read_only,
            "broad_prompt_detected": broad,
            "micro_patch_detected": micro,
            "specific_action_detected": specific,
            "target_content_detected": has_content,
        },
        "target_files": targets,
        "delegate_to": delegates,
        "delegate_policy": {
            "chatgpt": "admin_planner_only",
            "deepseek": "patch_draft_or_second_opinion_review",
            "local_qwen": "cheap_local_audit_patch_draft_review",
            "link": "only_executor_after_safety_gates",
        "delegate_runner": "non_executing_bridge_to_deepseek_and_local_qwen",
        },
        "safety_gates": SAFETY_GATES,
        "required_verification": required_verification,
        "suggested_next_command": suggested,
        "latest_engine_reports": _latest_engine_reports(),
        "subtasks": _subtasks_for(task_type, targets, risk),
    }


def _subtasks_for(task_type: str, targets: list[str], risk: str) -> list[dict[str, Any]]:
    if task_type == "audit":
        return [
            {
                "name": "inspect_current_state",
                "delegate_to": "local_qwen",
                "write_allowed": False,
                "description": "Summarize repo state, latest failures, and one specific next patch target.",
            }
        ]

    if task_type == "micro_patch":
        return [
            {
                "name": "validate_single_text_target",
                "delegate_to": "link_micro_patch",
                "write_allowed": False,
                "target_files": targets,
            },
            {
                "name": "execute_micro_patch_after_validation",
                "delegate_to": "link_micro_patch",
                "write_allowed": True,
                "requires_human_confirmation": True,
            },
        ]

    return [
        {
            "name": "local_patch_draft",
            "delegate_to": "local_qwen",
            "write_allowed": False,
            "target_files": targets,
        },
        {
            "name": "second_opinion_review",
            "delegate_to": "deepseek",
            "write_allowed": False,
            "target_files": targets,
        },
        {
            "name": "link_execute_after_approval",
            "delegate_to": "link",
            "write_allowed": True,
            "requires_human_confirmation": True,
            "risk": risk,
        },
    ]


def print_human(plan: dict[str, Any]) -> None:
    repo = plan["repo"]
    cls = plan["classification"]

    print("LINK ADMIN PLANNER")
    print(f"HEAD: {repo.get('head')}")
    print(f"safe-link-latest: {repo.get('safe_link_latest')}")
    print(f"dirty: {repo.get('dirty')}")
    if repo.get("dirty_files"):
        print("dirty files:")
        for item in repo["dirty_files"]:
            print(f"- {item}")

    print()
    print(f"task type: {cls.get('task_type')}")
    print(f"route: {cls.get('route')}")
    print(f"risk: {cls.get('risk')}")
    print(f"reason: {cls.get('reason')}")
    print(f"execution allowed: {plan.get('execution_allowed')}")
    print(f"human confirmation required: {plan.get('human_confirmation_required')}")

    print()
    print("target files:")
    if plan.get("target_files"):
        for item in plan["target_files"]:
            print(f"- {item}")
    else:
        print("- none detected")

    print()
    print("delegate to:")
    for item in plan.get("delegate_to", []):
        print(f"- {item}")

    print()
    print("required verification:")
    for item in plan.get("required_verification", []):
        print(f"- {item}")

    print()
    print(f"suggested next command: {plan.get('suggested_next_command')}")

    print()
    print("latest engine reports:")
    for report in plan.get("latest_engine_reports", []):
        print(
            f"- {report.get('run_id')} | {report.get('status')} | "
            f"{report.get('phase')} | {report.get('exit_code')} | {report.get('path')}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    plan = build_plan(args.prompt)

    if args.json:
        print(json.dumps(plan, indent=2, sort_keys=True))
    else:
        print_human(plan)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
