#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any

from capability_gate import classify_git_command
from execution_snapshots import create_execution_snapshot
from link_worker_profiles import profile_summary, validate_profiles

ROOT = Path(__file__).resolve().parents[2]
RECEIPT_DIR = ROOT / ".agents" / "self_update_receipts"


def run_git(args: list[str]) -> tuple[int, str]:
    command = ["git", *args]
    decision = classify_git_command(command)
    if decision.denied:
        raise PermissionError(f"git command blocked: {decision.reason}")

    proc = subprocess.run(
        command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return proc.returncode, proc.stdout


def git_text(args: list[str]) -> str:
    code, out = run_git(args)
    if code != 0:
        joined = " ".join(args)
        raise RuntimeError(f"git command failed: git {joined}\n{out}")
    return out.strip()


def write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    return path


def create_preflight_receipt(goal: str, profile: str = "self_update_preflight") -> Path:
    created_at = time.strftime("%Y%m%d-%H%M%S")

    validation = validate_profiles()
    if not validation.get("ok"):
        raise RuntimeError(f"worker profile validation failed: {validation}")

    profile_payload = profile_summary(profile)

    branch = git_text(["branch", "--show-current"])
    head = git_text(["rev-parse", "--verify", "HEAD"])
    latest_commit = git_text(["log", "--oneline", "-1"])
    status_before = git_text(["status", "--short"])

    snapshot = create_execution_snapshot(
        action="self_update_preflight",
        target={
            "goal": goal,
            "profile": profile,
            "enabled_tools": profile_payload["enabled_tool_names"],
        },
        gate_decision="allow",
        gate_reason="preflight inspection only",
        actor="link_self_update",
        details={
            "branch": branch,
            "head": head,
            "status_before": status_before,
            "worker_profile": profile_payload,
        },
    )

    receipt = {
        "receipt_version": 2,
        "runner": "link_self_update",
        "mode": "preflight",
        "created_at": created_at,
        "goal": goal,
        "branch": branch,
        "head": head,
        "latest_commit": latest_commit,
        "status_before": status_before,
        "worker_profile": profile,
        "enabled_tools": profile_payload["enabled_tool_names"],
        "profile_details": profile_payload["profile"],
        "profile_validation": validation,
        "snapshot_path": str(snapshot),
        "allowed_actions": [
            "inspect repository state",
            "resolve restricted worker profile",
            "create execution snapshot",
            "write self-update receipt",
        ],
        "blocked_actions": [
            "modify main directly",
            "run destructive git commands",
            "apply patches without later test evidence",
            "copy external project code wholesale",
            "use tools outside the resolved worker profile",
        ],
        "next_step": "review receipt, then implement the smallest safe Link-native patch",
    }

    filename = f"{created_at}-self-update-preflight-{profile}.json"
    return write_json(RECEIPT_DIR / filename, receipt)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Link self-update preflight.")
    parser.add_argument("--goal", required=True, help="Self-update goal being evaluated.")
    parser.add_argument(
        "--profile",
        default="self_update_preflight",
        help="Worker profile to resolve for this preflight.",
    )
    args = parser.parse_args()

    path = create_preflight_receipt(goal=args.goal, profile=args.profile)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
