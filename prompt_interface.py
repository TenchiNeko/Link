#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MAIN = ROOT / "standalone_main.py"

def ask_int(prompt, default):
    raw = input(f"{prompt} [{default}]: ").strip()
    if not raw:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        print("Using default.")
        return default

def ask_bool(prompt, default=True):
    label = "on" if default else "off"
    raw = input(f"{prompt} (on/off) [{label}]: ").strip().lower()
    if not raw:
        return default
    return raw in {"on", "yes", "y", "true", "1"}

def read_task():
    print("\nPaste/type your full task prompt below.")
    print("Finish with Ctrl+D, or type END on its own line.\n")
    lines = []
    try:
        while True:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
    except EOFError:
        pass
    except KeyboardInterrupt:
        print("\nExiting.")
        return None
    return "\n".join(lines).strip()

def run_task(task, max_iterations, worktree):
    env = os.environ.copy()
    env["ORCH_REPORT_FAST_PATH"] = "1"
    if worktree:
        env["ORCH_USE_WORKTREE"] = "1"
    else:
        env.pop("ORCH_USE_WORKTREE", None)

    cmd = [sys.executable, str(MAIN), task, "--max-iterations", str(max_iterations)]
    print("\nRunning real backend:\npython3 standalone_main.py \"<task>\" --max-iterations", max_iterations, "\n")
    return subprocess.call(cmd, cwd=str(ROOT), env=env)

def main():
    print("=== Link Orchestrator Interactive Launcher ===")

    while True:
        task = read_task()
        if task is None:
            return 0
        if not task:
            continue
        if task.lower() in {"q", "quit", "exit"}:
            return 0

        max_iterations = ask_int("Max iterations", 2)
        worktree = ask_bool("Use worktree", True)

        print("\n--- Confirm ---")
        print(task[:300] + ("..." if len(task) > 300 else ""))
        print(f"Max iterations: {max_iterations}")
        print(f"Worktree: {'on' if worktree else 'off'}")
        print("---------------")

        if ask_bool("Run", True):
            run_task(task, max_iterations, worktree)
            print("\nReady for another prompt.")

if __name__ == "__main__":
    raise SystemExit(main())
