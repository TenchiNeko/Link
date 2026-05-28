#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


MARKER = "workflow step executor OK"
RECEIPT_KIND = "link_workflow_step_execution_receipt"
RECEIPT_SCHEMA_VERSION = 1
DEFAULT_RECEIPT_DIR = Path(__file__).resolve().parent / ".link_execution_receipts"

FORBIDDEN_SHELL_TOKENS = (
    ";",
    "&&",
    "||",
    "|",
    ">",
    ">>",
    "<",
    "`",
    "$(",
)

ALLOWED_READONLY_GIT_PREFIXES = (
    ["git", "status"],
    ["git", "diff"],
    ["git", "log"],
    ["git", "show"],
)

ALLOWED_PYTHON_PREFIXES = (
    ["python3", "-m", "py_compile"],
    ["python", "-m", "py_compile"],
)

ALLOWED_SIMPLE_READONLY_COMMANDS = {
    "pwd",
    "ls",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    configured = os.environ.get("LINK_WORKFLOW_STEP_RECEIPT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"expected object JSON in {path}")
    return data


def write_json_atomic(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as fh:
        json.dump(data, fh, indent=2, sort_keys=True)
        fh.write("\n")
        tmp = Path(fh.name)
    tmp.replace(path)


def has_forbidden_shell_tokens(command: str) -> bool:
    return any(token in command for token in FORBIDDEN_SHELL_TOKENS)


def starts_with(parts: list[str], prefix: list[str]) -> bool:
    return len(parts) >= len(prefix) and parts[: len(prefix)] == prefix


def command_safety(command: str) -> tuple[bool, str]:
    stripped = command.strip()
    if not stripped:
        return False, "empty command"

    if has_forbidden_shell_tokens(stripped):
        return False, "blocked shell metacharacter or compound command"

    try:
        parts = shlex.split(stripped)
    except ValueError as exc:
        return False, f"could not parse command: {exc}"

    if not parts:
        return False, "empty parsed command"

    if parts[0] in ALLOWED_SIMPLE_READONLY_COMMANDS:
        return True, f"allowed simple read-only command: {parts[0]}"

    for prefix in ALLOWED_READONLY_GIT_PREFIXES:
        if starts_with(parts, prefix):
            return True, "allowed read-only git workflow step"

    for prefix in ALLOWED_PYTHON_PREFIXES:
        if starts_with(parts, prefix):
            return True, "allowed python compile workflow step"

    return False, f"command is not in workflow step allowlist: {parts[0]}"


def normalize_steps(spec: dict[str, Any]) -> list[dict[str, Any]]:
    raw_steps = spec.get("steps", [])
    if not isinstance(raw_steps, list):
        return []

    steps: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_steps, start=1):
        if not isinstance(raw, dict):
            steps.append(
                {
                    "id": f"step-{index}",
                    "description": "invalid non-object step",
                    "command": "",
                    "required": True,
                    "problems": ["step is not an object"],
                }
            )
            continue

        command = raw.get("command") or raw.get("run") or raw.get("shell") or ""
        if isinstance(command, list):
            command = " ".join(str(part) for part in command)
        if not isinstance(command, str):
            command = ""

        step_id = raw.get("id") or raw.get("name") or f"step-{index}"
        description = raw.get("description") or raw.get("title") or ""
        required = raw.get("required", True)

        steps.append(
            {
                "id": str(step_id),
                "description": str(description),
                "command": command,
                "required": bool(required),
                "raw": raw,
                "problems": [],
            }
        )
    return steps


def run_step_command(command: str, repo_root: Path, timeout: int) -> tuple[int, str, str, float]:
    started = time.monotonic()
    completed = subprocess.run(
        shlex.split(command),
        cwd=str(repo_root),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
    )
    elapsed = round(time.monotonic() - started, 4)
    return completed.returncode, completed.stdout, completed.stderr, elapsed


def execute_workflow_steps(
    spec: dict[str, Any],
    *,
    repo_root: Path | None = None,
    dry_run: bool = True,
    step_id: str | None = None,
    timeout: int = 30,
    receipt_dir: Path | None = None,
    write_receipt: bool = False,
) -> dict[str, Any]:
    root = (repo_root or Path(__file__).resolve().parent).resolve()
    started_at = utc_now()
    workflow_id = str(spec.get("workflow_id") or "unknown-workflow")
    goal = str(spec.get("goal") or "")

    selected_steps = normalize_steps(spec)
    if step_id:
        selected_steps = [step for step in selected_steps if step.get("id") == step_id]

    results: list[dict[str, Any]] = []
    problems: list[str] = []

    if step_id and not selected_steps:
        problems.append(f"no matching workflow step id: {step_id}")

    for step in selected_steps:
        command = step.get("command", "")
        safe, safety_reason = command_safety(command)
        step_problems = list(step.get("problems") or [])

        result: dict[str, Any] = {
            "id": step.get("id", ""),
            "description": step.get("description", ""),
            "command": command,
            "required": bool(step.get("required", True)),
            "safe": safe,
            "safety_reason": safety_reason,
            "dry_run": dry_run,
            "status": "pending",
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "elapsed_seconds": 0.0,
            "problems": step_problems,
        }

        if step_problems:
            result["status"] = "invalid"
            problems.extend(f"{result['id']}: {problem}" for problem in step_problems)
        elif not safe:
            result["status"] = "blocked"
            result["problems"].append(safety_reason)
            if result["required"]:
                problems.append(f"{result['id']}: {safety_reason}")
        elif dry_run:
            result["status"] = "dry_run"
            result["ok"] = True
        else:
            try:
                returncode, stdout, stderr, elapsed = run_step_command(command, root, timeout)
                result["returncode"] = returncode
                result["stdout"] = stdout
                result["stderr"] = stderr
                result["elapsed_seconds"] = elapsed
                if returncode == 0:
                    result["status"] = "ok"
                    result["ok"] = True
                else:
                    result["status"] = "failed"
                    result["problems"].append(f"returncode {returncode}")
                    if result["required"]:
                        problems.append(f"{result['id']}: returncode {returncode}")
            except subprocess.TimeoutExpired:
                result["status"] = "timeout"
                result["problems"].append(f"timeout after {timeout}s")
                if result["required"]:
                    problems.append(f"{result['id']}: timeout after {timeout}s")
            except Exception as exc:
                result["status"] = "error"
                result["problems"].append(str(exc))
                if result["required"]:
                    problems.append(f"{result['id']}: {exc}")

        results.append(result)

    summary = {
        "total": len(results),
        "ok": sum(1 for item in results if item.get("ok")),
        "blocked": sum(1 for item in results if item.get("status") == "blocked"),
        "failed": sum(1 for item in results if item.get("status") in {"failed", "timeout", "error", "invalid"}),
        "dry_run": sum(1 for item in results if item.get("status") == "dry_run"),
    }

    receipt = {
        "kind": RECEIPT_KIND,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "goal": goal,
        "repo_root": str(root),
        "started_at": started_at,
        "finished_at": utc_now(),
        "dry_run": dry_run,
        "non_destructive": True,
        "ok": not problems,
        "status": "ok" if not problems else "failed",
        "step_id": step_id or "",
        "steps": results,
        "summary": summary,
        "problems": problems,
        "receipt_path": "",
    }

    if write_receipt:
        out_dir = (receipt_dir or default_receipt_dir()).resolve()
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_workflow = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in workflow_id)[:80]
        receipt_path = out_dir / f"workflow-step-{safe_workflow}-{stamp}.json"
        receipt["receipt_path"] = str(receipt_path)
        write_json_atomic(receipt_path, receipt)

    return receipt


def sample_workflow_spec() -> dict[str, Any]:
    return {
        "kind": "link_workflow_spec",
        "schema_version": 1,
        "workflow_id": "lu41-workflow-step-executor",
        "goal": "Validate the workflow step executor with safe deterministic commands.",
        "steps": [
            {
                "id": "show-pwd",
                "description": "Read current repo path.",
                "command": "pwd",
                "required": True,
            },
            {
                "id": "show-git-status",
                "description": "Read current git status.",
                "command": "git status --short",
                "required": True,
            },
            {
                "id": "compile-core",
                "description": "Compile core workflow modules.",
                "command": "python3 -m py_compile link_workflow_spec.py link_workflow_preflight_executor.py",
                "required": True,
            },
        ],
    }


def validate_workflow_step_executor() -> list[str]:
    problems: list[str] = []

    dry_receipt = execute_workflow_steps(sample_workflow_spec(), dry_run=True)
    if not dry_receipt.get("ok"):
        problems.append("expected dry-run sample receipt to be ok")

    if dry_receipt.get("summary", {}).get("dry_run") != 3:
        problems.append("expected three dry-run steps")

    blocked_spec = {
        "kind": "link_workflow_spec",
        "schema_version": 1,
        "workflow_id": "blocked-test",
        "goal": "Verify destructive commands are blocked.",
        "steps": [
            {
                "id": "blocked-rm",
                "description": "Should be blocked.",
                "command": "rm -rf /",
                "required": True,
            }
        ],
    }
    blocked_receipt = execute_workflow_steps(blocked_spec, dry_run=False)
    if blocked_receipt.get("ok"):
        problems.append("expected destructive workflow step to be blocked")

    rendered = json.dumps(blocked_receipt, sort_keys=True)
    if "blocked" not in rendered or "rm -rf /" not in rendered:
        problems.append("blocked receipt missing expected evidence")

    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        receipt = execute_workflow_steps(
            sample_workflow_spec(),
            dry_run=True,
            receipt_dir=out_dir,
            write_receipt=True,
        )
        receipt_path = Path(str(receipt.get("receipt_path", "")))
        if not receipt_path.exists():
            problems.append("expected written workflow step receipt")
        else:
            loaded = load_json(receipt_path)
            if loaded.get("kind") != RECEIPT_KIND:
                problems.append("written receipt has wrong kind")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute safe workflow spec steps.")
    parser.add_argument("--spec", help="Path to workflow spec JSON. Defaults to built-in sample.")
    parser.add_argument("--step-id", help="Only run a single step id.")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parent))
    parser.add_argument("--receipt-dir")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--dry-run", action="store_true", default=False)
    parser.add_argument("--run", action="store_true", help="Actually run allowed commands.")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_workflow_step_executor()
        if problems:
            print("workflow step executor FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    if args.spec:
        spec = load_json(Path(args.spec))
    else:
        spec = sample_workflow_spec()

    dry_run = not args.run
    if args.dry_run:
        dry_run = True

    receipt = execute_workflow_steps(
        spec,
        repo_root=Path(args.repo_root),
        dry_run=dry_run,
        step_id=args.step_id,
        timeout=args.timeout,
        receipt_dir=Path(args.receipt_dir) if args.receipt_dir else None,
        write_receipt=args.write,
    )

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
