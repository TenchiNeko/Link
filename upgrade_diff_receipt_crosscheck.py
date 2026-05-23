
#!/usr/bin/env python3
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent


def _git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def get_commit_subject(ref: str = "HEAD") -> str:
    return _git(["show", "-s", "--format=%s", ref])


def get_changed_files(ref: str = "HEAD") -> list[str]:
    out = _git(["diff-tree", "--no-commit-id", "--name-only", "-r", ref])
    return sorted(line.strip() for line in out.splitlines() if line.strip())


def build_diff_receipt(ref: str = "HEAD", upgrade_id: str | None = None) -> dict:
    return {
        "receipt_version": "1.0",
        "ref": ref,
        "upgrade_id": upgrade_id or "",
        "commit_subject": get_commit_subject(ref),
        "changed_files": get_changed_files(ref),
    }


def crosscheck_diff_receipt(
    receipt: dict,
    required_files: Iterable[str] = (),
    required_subject_contains: str = "",
    required_upgrade_id: str = "",
) -> list[str]:
    problems: list[str] = []

    if receipt.get("receipt_version") != "1.0":
        problems.append("invalid_or_missing_receipt_version")

    subject = receipt.get("commit_subject", "")
    changed_files = set(receipt.get("changed_files", []))
    upgrade_id = receipt.get("upgrade_id", "")

    if required_upgrade_id and upgrade_id != required_upgrade_id:
        problems.append(f"upgrade_id_mismatch::{upgrade_id or 'missing'}")

    if required_subject_contains and required_subject_contains not in subject:
        problems.append(f"commit_subject_missing::{required_subject_contains}")

    for path in required_files:
        if path not in changed_files:
            problems.append(f"changed_file_missing::{path}")

    if not changed_files:
        problems.append("changed_files_empty")

    return problems


def synthetic_lu08_receipt() -> dict:
    return {
        "receipt_version": "1.0",
        "ref": "synthetic",
        "upgrade_id": "LU08",
        "commit_subject": "feat: add upgrade diff receipt cross-check LU08",
        "changed_files": [
            "upgrade_diff_receipt_crosscheck.py",
            "link_healthcheck.py",
            "link_upgrade_registry.py",
            "UPGRADES.md",
        ],
    }


def main() -> int:
    required = [
        "upgrade_diff_receipt_crosscheck.py",
        "link_healthcheck.py",
        "link_upgrade_registry.py",
        "UPGRADES.md",
    ]
    problems = crosscheck_diff_receipt(
        synthetic_lu08_receipt(),
        required_files=required,
        required_subject_contains="LU08",
        required_upgrade_id="LU08",
    )
    if problems:
        print("upgrade diff receipt cross-check FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print("upgrade diff receipt cross-check OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
