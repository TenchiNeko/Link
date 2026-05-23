
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def _git(args: list[str]) -> str:
    return subprocess.check_output(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()


def _safe_git(args: list[str]) -> str:
    try:
        return _git(args)
    except Exception as exc:
        return f"git command failed: git {' '.join(args)}\n{exc}\n"


def _upgrade_items() -> list[dict[str, Any]]:
    import link_upgrade_registry

    items = []
    for item in link_upgrade_registry.UPGRADES:
        if isinstance(item, dict):
            items.append(dict(item))
        else:
            uid, title, marker = item
            items.append(
                {
                    "id": uid,
                    "title": title,
                    "commit_subject": "",
                    "healthcheck_markers": [marker],
                    "status": "implemented",
                }
            )
    return items


def find_upgrade(upgrade_id: str) -> dict[str, Any]:
    wanted = upgrade_id.upper()
    for item in _upgrade_items():
        if str(item.get("id", "")).upper() == wanted:
            return item
    raise ValueError(f"unknown upgrade id: {upgrade_id}")


def find_commit_for_subject(subject: str) -> str:
    if not subject:
        return "HEAD"

    log = _safe_git(["log", "--all", "--format=%H%x00%s"])
    for line in log.splitlines():
        if "\x00" not in line:
            continue
        commit, found_subject = line.split("\x00", 1)
        if found_subject.strip() == subject.strip():
            return commit.strip()

    return "HEAD"


def export_upgrade_evidence_bundle(upgrade_id: str, output_root: str | Path) -> Path:
    item = find_upgrade(upgrade_id)
    commit = find_commit_for_subject(str(item.get("commit_subject", "")))

    out_root = Path(output_root)
    bundle = out_root / f"{item['id'].lower()}_evidence_bundle"

    if bundle.exists():
        shutil.rmtree(bundle)
    bundle.mkdir(parents=True, exist_ok=True)

    metadata = {
        "bundle_version": "1.0",
        "upgrade_id": item.get("id"),
        "title": item.get("title"),
        "status": item.get("status"),
        "commit_subject": item.get("commit_subject"),
        "commit": commit,
        "healthcheck_markers": item.get("healthcheck_markers", []),
    }

    (bundle / "metadata.json").write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle / "registry_entry.json").write_text(
        json.dumps(item, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (bundle / "commit.txt").write_text(commit + "\n", encoding="utf-8")
    (bundle / "healthcheck_markers_expected.txt").write_text(
        "\n".join(str(x) for x in item.get("healthcheck_markers", [])) + "\n",
        encoding="utf-8",
    )
    (bundle / "git_show_stat.txt").write_text(
        _safe_git(["show", "--stat", "--oneline", "--decorate", "--no-renames", commit]) + "\n",
        encoding="utf-8",
    )
    (bundle / "git_show_name_status.txt").write_text(
        _safe_git(["show", "--name-status", "--oneline", "--decorate", "--no-renames", commit]) + "\n",
        encoding="utf-8",
    )
    (bundle / "git_show.patch").write_text(
        _safe_git(["show", "--format=fuller", "--no-renames", commit]) + "\n",
        encoding="utf-8",
    )

    return bundle


def validate_evidence_bundle(bundle: str | Path) -> list[str]:
    path = Path(bundle)
    required = [
        "metadata.json",
        "registry_entry.json",
        "commit.txt",
        "healthcheck_markers_expected.txt",
        "git_show_stat.txt",
        "git_show_name_status.txt",
        "git_show.patch",
    ]

    problems = []
    for name in required:
        f = path / name
        if not f.exists():
            problems.append(f"missing::{name}")
        elif f.stat().st_size <= 0:
            problems.append(f"empty::{name}")

    try:
        metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
        if not metadata.get("upgrade_id"):
            problems.append("metadata_missing_upgrade_id")
        if not metadata.get("commit"):
            problems.append("metadata_missing_commit")
    except Exception as exc:
        problems.append(f"metadata_invalid::{exc}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a Link upgrade evidence bundle.")
    parser.add_argument("upgrade_id", nargs="?", default="LU09")
    parser.add_argument("--out", default=".agents/upgrade_evidence")
    args = parser.parse_args()

    bundle = export_upgrade_evidence_bundle(args.upgrade_id, args.out)
    problems = validate_evidence_bundle(bundle)

    if problems:
        print("upgrade evidence bundle FAILED")
        for problem in problems:
            print(f"- {problem}")
        return 1

    print(f"upgrade evidence bundle OK: {bundle}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
