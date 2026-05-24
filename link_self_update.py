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

ROOT = Path(__file__).resolve().parent
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
        raise RuntimeError(f"git command failed: git {' '.join(args)}\n{out}")
    return out.strip()


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")


def build_self_update_receipt(goal: str, mode: str) -> Path:
    branch = git_text(["branch", "--show-current"])
    status = git_text(["status", "--short"])
    head = git_text(["rev-parse", "--verify", "HEAD"])
    latest = git_text(["log", "--oneline", "-1"])

    if branch in {"main", "master"}:
        raise PermissionError("self-update runner refuses to operate directly on main or master")

    snapshot = create_execution_snapshot(
        action="self_update_preflight",
        target={"goal": goal, "mode": mode},
        gate_decision="allow",
        gate_reason="safe preflight receipt only",
        actor="link_self_update",
        details={
            "branch": branch,
            "head": head,
            "status_before": status,
        },
    )

    now = time.strftime("%Y%m%d-%H%M%S")
    receipt = {
        "receipt_version": 1,
        "created_at": now,
        "runner": "link_self_update",
        "mode": mode,
        "goal": goal,
        "branch": branch,
        "head": head,
        "latest_commit": latest,
        "status_before": status,
        "snapshot_path": str(snapshot),
        "allowed_actions": [
            "inspect repository state",
            "create execution snapshot",
            "write self-update receipt",
        ],
        "blocked_actions": [
            "modify main directly",
            "run destructive git commands",
            "apply patches without later test evidence",
            "copy external project code wholesale",
        ],
        "next_step": "review receipt, then implement the smallest safe Link-native patch",
    }

    safe_name = now + "-self-update-preflight.json"
    receipt_path = RECEIPT_DIR / safe_name
    write_json(receipt_path, receipt)
    return receipt_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Link self-update preflight runner")
    parser.add_argument("--goal", required=True, help="Self-update goal or upgrade objective")
    parser.add_argument("--mode", default="preflight", choices=["preflight", "inspect"])
    args = parser.parse_args()

    receipt = build_self_update_receipt(goal=args.goal, mode=args.mode)
    print(receipt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
