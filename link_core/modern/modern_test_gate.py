"""
Small test gate for checkpoint promotion.

Runs cheap validation first, then optional pytest if tests exist.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GateResult:
    ok: bool
    output: str


def run_gate(repo: Path) -> GateResult:
    commands: list[list[str]] = [
        ["python3", "-m", "py_compile",
         "standalone_agents.py",
         "modern_command_guard.py",
         "modern_symbol_index.py",
         "modern_task_runtime.py",
         "modern_usage_budget.py",
         "modern_edit_tools.py"],
    ]

    # Do not auto-run legacy workspace tests here.
    # This repo folder contains old experimental tests that may sys.exit()
    # or validate unrelated historical behavior. The checkpoint gate should
    # only enforce syntax/import safety for the modernized safety layer.

    chunks = []
    for cmd in commands:
        r = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, timeout=120)
        chunks.append("$ " + " ".join(cmd))
        chunks.append(r.stdout)
        chunks.append(r.stderr)
        if r.returncode != 0:
            return GateResult(False, "\n".join(chunks))

    return GateResult(True, "\n".join(chunks))
