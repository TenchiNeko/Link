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


MARKER = "workflow spec preflight executor OK"
RECEIPT_KIND = "link_workflow_preflight_execution_receipt"
RECEIPT_SCHEMA_VERSION = 1
DEFAULT_RECEIPT_DIR = Path(__file__).resolve().parent / ".link_execution_receipts"

FORBIDDEN_SHELL_TOKENS = (
    ";",
    "&&",
    "||",
    "|",
    ">",
    "<",
    "`",
    "$(",
    "\n",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_receipt_dir() -> Path:
    configured = os.environ.get("LINK_WORKFLOW_PREFLIGHT_RECEIPT_DIR")
    if configured:
        return Path(configured).expanduser().resolve()
    return DEFAULT_RECEIPT_DIR.resolve()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(path.parent),
        delete=False,
        prefix=f".{path.name}.",
        suffix=".tmp",
    ) as tmp:
        json.dump(payload, tmp, indent=2, sort_keys=True)
        tmp.write("\n")
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def truncate_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n... truncated {len(value) - limit} chars"


def split_command(command: str) -> tuple[list[str], str | None]:
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return [], f"could not parse command: {exc}"
    if not parts:
        return [], "empty command"
    return parts, None


def command_has_shell_syntax(command: str) -> bool:
    return any(token in command for token in FORBIDDEN_SHELL_TOKENS)


def command_is_preflight_safe(command: str) -> tuple[bool, str]:
    from link_workflow_spec import command_is_obviously_dangerous

    command = command.strip()
    if not command:
        return False, "empty command"

    if command_is_obviously_dangerous(command):
        return False, "command matched dangerous-command denylist"

    if command_has_shell_syntax(command):
        return False, "shell control syntax is not allowed in preflight commands"

    parts, error = split_command(command)
    if error:
        return False, error

    exe = Path(parts[0]).name

    if exe in {"python", "python3"}:
        if len(parts) >= 3 and parts[1] == "-m" and parts[2] == "py_compile":
            return True, "allowed python py_compile preflight"
        return False, "python preflight commands are limited to -m py_compile"

    if exe == "git":
        if len(parts) >= 2 and parts[1] in {"status", "diff", "log"}:
            return True, f"allowed read-only git {parts[1]} preflight"
        return False, "git preflight commands are limited to status, diff, or log"

    if exe in {"pytest", "pwd", "ls", "grep", "rg"}:
        return True, f"allowed {exe} preflight"

    return False, f"unsupported preflight executable: {exe}"


def bounded_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except Exception:
        timeout = 30
    return max(1, min(timeout, 120))


def evaluate_stdout_expectations(check: dict[str, Any], stdout: str, stderr: str) -> list[str]:
    problems: list[str] = []

    if check.get("expect_empty_stdout") is True and stdout.strip():
        problems.append("expected empty stdout")

    if check.get("expect_empty_stderr") is True and stderr.strip():
        problems.append("expected empty stderr")

    contains = check.get("expect_stdout_contains")
    if isinstance(contains, str) and contains not in stdout:
        problems.append(f"stdout did not contain expected text: {contains}")
    elif isinstance(contains, list):
        for item in contains:
            text = str(item)
            if text not in stdout:
                problems.append(f"stdout did not contain expected text: {text}")

    return problems


def run_preflight_command(
    check: dict[str, Any],
    cwd: Path,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    command = str(check.get("command", "")).strip()
    check_id = str(check.get("id", "")).strip() or "unnamed-check"
    required = check.get("required") is not False

    safe, safety_reason = command_is_preflight_safe(command)

    result: dict[str, Any] = {
        "id": check_id,
        "description": str(check.get("description", "")).strip(),
        "command": command,
        "required": required,
        "safe": safe,
        "safety_reason": safety_reason,
        "status": "pending",
        "ok": False,
        "returncode": None,
        "stdout": "",
        "stderr": "",
        "elapsed_seconds": 0.0,
        "problems": [],
    }

    if not safe:
        result["status"] = "blocked"
        result["problems"].append(safety_reason)
        return result

    if dry_run:
        result["status"] = "dry_run"
        result["ok"] = True
        return result

    parts, error = split_command(command)
    if error:
        result["status"] = "blocked"
        result["problems"].append(error)
        return result

    started = time.monotonic()
    try:
        completed = subprocess.run(
            parts,
            cwd=str(cwd),
            text=True,
            capture_output=True,
            timeout=bounded_timeout(check.get("timeout_seconds", 30)),
            check=False,
        )
        elapsed = time.monotonic() - started

        result["returncode"] = completed.returncode
        result["stdout"] = truncate_text(completed.stdout or "")
        result["stderr"] = truncate_text(completed.stderr or "")
        result["elapsed_seconds"] = round(elapsed, 4)

        if completed.returncode != 0:
            result["problems"].append(f"command exited with {completed.returncode}")

        result["problems"].extend(
            evaluate_stdout_expectations(check, completed.stdout or "", completed.stderr or "")
        )

        if result["problems"]:
            result["status"] = "failed"
            result["ok"] = False
        else:
            result["status"] = "ok"
            result["ok"] = True

    except subprocess.TimeoutExpired as exc:
        elapsed = time.monotonic() - started
        result["status"] = "timeout"
        result["elapsed_seconds"] = round(elapsed, 4)
        result["stdout"] = truncate_text(exc.stdout or "")
        result["stderr"] = truncate_text(exc.stderr or "")
        result["problems"].append("command timed out")
    except FileNotFoundError as exc:
        elapsed = time.monotonic() - started
        result["status"] = "failed"
        result["elapsed_seconds"] = round(elapsed, 4)
        result["problems"].append(str(exc))
    except Exception as exc:
        elapsed = time.monotonic() - started
        result["status"] = "failed"
        result["elapsed_seconds"] = round(elapsed, 4)
        result["problems"].append(f"{type(exc).__name__}: {exc}")

    return result


def resolve_repo_root(spec: dict[str, Any], explicit_repo_root: Path | None = None) -> Path:
    if explicit_repo_root is not None:
        return explicit_repo_root.expanduser().resolve()

    inputs = spec.get("inputs") if isinstance(spec.get("inputs"), dict) else {}
    configured = inputs.get("repo_root", ".")
    return Path(str(configured)).expanduser().resolve()


def build_receipt_path(receipt_dir: Path, workflow_id: str) -> Path:
    safe_id = "".join(ch if ch.isalnum() or ch in "._-" else "-" for ch in workflow_id)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return receipt_dir / f"workflow-preflight-{safe_id}-{stamp}.json"


def execute_workflow_preflight(
    spec: dict[str, Any],
    *,
    repo_root: Path | None = None,
    receipt_dir: Path | None = None,
    write: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    from link_workflow_spec import normalize_spec, validate_workflow_spec

    started_at = utc_now()
    normalized = normalize_spec(spec)
    workflow_id = str(normalized.get("workflow_id", "workflow")).strip() or "workflow"
    cwd = resolve_repo_root(normalized, repo_root)

    receipt: dict[str, Any] = {
        "kind": RECEIPT_KIND,
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "workflow_id": workflow_id,
        "goal": normalized.get("goal", ""),
        "started_at": started_at,
        "finished_at": "",
        "repo_root": str(cwd),
        "dry_run": dry_run,
        "non_destructive": True,
        "ok": False,
        "status": "pending",
        "checks": [],
        "summary": {
            "total": 0,
            "ok": 0,
            "failed": 0,
            "blocked": 0,
            "optional_failed": 0,
        },
        "problems": [],
        "receipt_path": "",
    }

    validation_problems = validate_workflow_spec(normalized)
    if validation_problems:
        receipt["status"] = "invalid_spec"
        receipt["problems"].extend(validation_problems)
        receipt["finished_at"] = utc_now()
        return receipt

    if not cwd.exists() or not cwd.is_dir():
        receipt["status"] = "bad_repo_root"
        receipt["problems"].append(f"repo_root does not exist or is not a directory: {cwd}")
        receipt["finished_at"] = utc_now()
        return receipt

    checks = normalized.get("preflight_checks", [])
    if not isinstance(checks, list):
        checks = []

    for check in checks:
        if not isinstance(check, dict):
            receipt["checks"].append(
                {
                    "id": "invalid-check",
                    "required": True,
                    "safe": False,
                    "status": "blocked",
                    "ok": False,
                    "problems": ["preflight check must be an object"],
                }
            )
            continue

        result = run_preflight_command(check, cwd, dry_run=dry_run)
        receipt["checks"].append(result)

    total = len(receipt["checks"])
    ok_count = sum(1 for item in receipt["checks"] if item.get("ok") is True)
    blocked = sum(1 for item in receipt["checks"] if item.get("status") == "blocked")
    failed_required = [
        item
        for item in receipt["checks"]
        if item.get("required") is not False and item.get("ok") is not True
    ]
    optional_failed = [
        item
        for item in receipt["checks"]
        if item.get("required") is False and item.get("ok") is not True
    ]

    receipt["summary"] = {
        "total": total,
        "ok": ok_count,
        "failed": len(failed_required),
        "blocked": blocked,
        "optional_failed": len(optional_failed),
    }

    for item in failed_required:
        check_id = item.get("id", "unnamed-check")
        for problem in item.get("problems", []) or ["preflight check failed"]:
            receipt["problems"].append(f"{check_id}: {problem}")

    receipt["ok"] = not receipt["problems"]
    receipt["status"] = "ok" if receipt["ok"] else "failed"
    receipt["finished_at"] = utc_now()

    if write:
        target_dir = (receipt_dir or default_receipt_dir()).expanduser().resolve()
        path = build_receipt_path(target_dir, workflow_id)
        receipt["receipt_path"] = str(path)
        atomic_write_json(path, receipt)

    return receipt


def validate_link_workflow_preflight_executor() -> list[str]:
    from link_workflow_spec import sample_workflow_spec

    problems: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "ok.py").write_text("x = 1\n")

        spec = sample_workflow_spec()
        spec["workflow_id"] = "test-preflight"
        spec["inputs"]["repo_root"] = str(root)
        spec["preflight_checks"] = [
            {
                "id": "compile-ok",
                "description": "Compile a harmless temp file.",
                "command": "python3 -m py_compile ok.py",
                "expect_empty_stdout": True,
                "required": True,
            }
        ]

        receipt = execute_workflow_preflight(spec, repo_root=root)
        if receipt.get("ok") is not True:
            problems.append(f"expected harmless preflight to pass: {receipt.get('problems')}")

        if receipt.get("summary", {}).get("ok") != 1:
            problems.append("expected one successful preflight check")

        receipt_dir = root / "receipts"
        written = execute_workflow_preflight(spec, repo_root=root, receipt_dir=receipt_dir, write=True)
        receipt_path = Path(str(written.get("receipt_path", "")))
        if not receipt_path.exists():
            problems.append("expected written preflight receipt to exist")

        dry = execute_workflow_preflight(spec, repo_root=root, dry_run=True)
        if dry.get("ok") is not True or dry.get("checks", [{}])[0].get("status") != "dry_run":
            problems.append("expected dry-run preflight to pass with dry_run status")

        dangerous = sample_workflow_spec()
        dangerous["workflow_id"] = "dangerous-preflight"
        dangerous["inputs"]["repo_root"] = str(root)
        dangerous["preflight_checks"] = [
            {
                "id": "bad",
                "command": "git reset --hard HEAD",
                "required": True,
            }
        ]
        bad_receipt = execute_workflow_preflight(dangerous, repo_root=root)
        if bad_receipt.get("ok") is True:
            problems.append("dangerous preflight unexpectedly passed")
        if not any("dangerous" in str(problem) or "denylist" in str(problem) for problem in bad_receipt.get("problems", [])):
            problems.append("dangerous preflight did not report denylist problem")

        unsafe_python = sample_workflow_spec()
        unsafe_python["workflow_id"] = "unsafe-python-preflight"
        unsafe_python["inputs"]["repo_root"] = str(root)
        unsafe_python["preflight_checks"] = [
            {
                "id": "bad-python",
                "command": "python3 script.py",
                "required": True,
            }
        ]
        unsafe_receipt = execute_workflow_preflight(unsafe_python, repo_root=root)
        if unsafe_receipt.get("ok") is True:
            problems.append("unsafe python preflight unexpectedly passed")

    return problems


def main() -> int:
    from link_workflow_spec import sample_workflow_spec, load_workflow_spec

    parser = argparse.ArgumentParser(description="Execute safe declared Link workflow preflight checks.")
    parser.add_argument("--file", help="Path to workflow spec JSON")
    parser.add_argument("--repo-root", help="Override workflow repo_root")
    parser.add_argument("--receipt-dir", help="Directory for written receipts")
    parser.add_argument("--write", action="store_true", help="Write a JSON execution receipt")
    parser.add_argument("--dry-run", action="store_true", help="Validate and plan without executing checks")
    parser.add_argument("--json", action="store_true", help="Print JSON receipt")
    parser.add_argument("--self-test", action="store_true", help="Run built-in validation")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_link_workflow_preflight_executor()
        if problems:
            print("workflow spec preflight executor FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    spec = load_workflow_spec(Path(args.file)) if args.file else sample_workflow_spec()
    repo_root = Path(args.repo_root) if args.repo_root else None
    receipt_dir = Path(args.receipt_dir) if args.receipt_dir else None

    receipt = execute_workflow_preflight(
        spec,
        repo_root=repo_root,
        receipt_dir=receipt_dir,
        write=args.write,
        dry_run=args.dry_run,
    )

    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt.get("ok") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
