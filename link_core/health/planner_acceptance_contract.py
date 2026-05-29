
#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def build_acceptance_contract(
    upgrade_id: str,
    title: str,
    required_files: list[str],
    required_healthcheck_markers: list[str],
    required_commit_subject: str,
    registry_id: str | None = None,
) -> dict:
    return {
        "contract_version": "1.0",
        "upgrade_id": upgrade_id,
        "title": title,
        "required_files": list(required_files),
        "required_healthcheck_markers": list(required_healthcheck_markers),
        "required_commit_subject": required_commit_subject,
        "registry_id": registry_id or upgrade_id,
    }


def validate_acceptance_contract(
    contract: dict,
    repo_root: str | Path = ".",
    healthcheck_output: str = "",
    git_log_output: str = "",
    registry_ids: Iterable[str] | None = None,
) -> list[str]:
    root = Path(repo_root)
    problems: list[str] = []

    for key in [
        "contract_version",
        "upgrade_id",
        "title",
        "required_files",
        "required_healthcheck_markers",
        "required_commit_subject",
        "registry_id",
    ]:
        if key not in contract:
            problems.append(f"missing contract key: {key}")

    for rel in contract.get("required_files", []):
        rel_path = Path(str(rel))
        if rel_path.is_absolute() or ".." in rel_path.parts:
            problems.append(f"unsafe required file path: {rel}")
            continue
        if not (root / rel_path).exists():
            problems.append(f"missing required file: {rel}")

    for marker in contract.get("required_healthcheck_markers", []):
        if marker not in healthcheck_output:
            problems.append(f"missing healthcheck marker: {marker}")

    commit_subject = contract.get("required_commit_subject", "")
    if commit_subject and commit_subject not in git_log_output:
        problems.append(f"missing expected commit subject: {commit_subject}")

    expected_registry_id = contract.get("registry_id")
    if expected_registry_id:
        ids = set(registry_ids or [])
        if expected_registry_id not in ids:
            problems.append(f"missing registry id: {expected_registry_id}")

    return problems


def evaluate_acceptance_contract(
    contract: dict,
    repo_root: str | Path = ".",
    healthcheck_output: str = "",
    git_log_output: str = "",
    registry_ids: Iterable[str] | None = None,
) -> dict:
    problems = validate_acceptance_contract(
        contract=contract,
        repo_root=repo_root,
        healthcheck_output=healthcheck_output,
        git_log_output=git_log_output,
        registry_ids=registry_ids,
    )
    return {
        "accepted": not problems,
        "upgrade_id": contract.get("upgrade_id", "unknown"),
        "problems": problems,
    }


def current_registry_ids() -> list[str]:
    import link_upgrade_registry
    return link_upgrade_registry.implemented_upgrade_ids()
