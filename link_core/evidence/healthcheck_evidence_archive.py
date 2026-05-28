
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_ARCHIVE_DIR = ROOT / ".agents" / "healthcheck_evidence"


def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def archive_root_from_env() -> Path:
    return Path(os.environ.get("LINK_HEALTHCHECK_EVIDENCE_DIR", DEFAULT_ARCHIVE_DIR))


def _archive_dirs(archive_root: Path) -> list[Path]:
    if not archive_root.exists():
        return []
    return sorted([p for p in archive_root.iterdir() if p.is_dir()], key=lambda p: p.name)


def prune_healthcheck_archives(archive_root: str | Path, retain: int = 10) -> list[str]:
    root = Path(archive_root)
    if retain < 1:
        retain = 1

    dirs = _archive_dirs(root)
    removed: list[str] = []
    excess = max(0, len(dirs) - retain)

    for old in dirs[:excess]:
        shutil.rmtree(old, ignore_errors=True)
        removed.append(str(old))

    return removed


def archive_healthcheck_output(
    output: str,
    exit_code: int,
    archive_root: str | Path | None = None,
    retain: int = 10,
    label: str = "healthcheck",
) -> Path:
    root = Path(archive_root) if archive_root is not None else archive_root_from_env()
    root.mkdir(parents=True, exist_ok=True)

    archive = root / f"{utc_stamp()}_{label}"
    archive.mkdir(parents=True, exist_ok=False)

    metadata: dict[str, Any] = {
        "archive_version": "1.0",
        "label": label,
        "exit_code": int(exit_code),
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "retain": int(retain),
    }

    (archive / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")
    (archive / "healthcheck_output.txt").write_text(output or "")
    (archive / "status.txt").write_text("PASS\n" if exit_code == 0 else "FAIL\n")

    prune_healthcheck_archives(root, retain=retain)
    return archive


def validate_healthcheck_archive(path: str | Path) -> list[str]:
    archive = Path(path)
    problems: list[str] = []

    required = ["metadata.json", "healthcheck_output.txt", "status.txt"]
    for name in required:
        if not (archive / name).exists():
            problems.append(f"missing {name}")

    try:
        metadata = json.loads((archive / "metadata.json").read_text())
        if metadata.get("archive_version") != "1.0":
            problems.append("metadata archive_version is not 1.0")
        if "exit_code" not in metadata:
            problems.append("metadata missing exit_code")
    except Exception as exc:
        problems.append(f"metadata invalid: {exc}")

    return problems


def run_healthcheck_and_archive(
    archive_root: str | Path | None = None,
    retain: int = 10,
) -> Path:
    env = os.environ.copy()
    env["LINK_HEALTHCHECK_SKIP_EVIDENCE_ARCHIVE"] = "1"

    proc = subprocess.run(
        [sys.executable, "link_healthcheck.py"],
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    archive = archive_healthcheck_output(
        output=proc.stdout,
        exit_code=proc.returncode,
        archive_root=archive_root,
        retain=retain,
        label="healthcheck",
    )

    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    return archive


def self_test() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        latest = None
        for i in range(4):
            latest = archive_healthcheck_output(
                output=f"fake healthcheck output {i}\nLINK HEALTHCHECK PASSED\n",
                exit_code=0,
                archive_root=root,
                retain=2,
                label="selftest",
            )

        assert latest is not None
        problems = validate_healthcheck_archive(latest)
        if problems:
            raise SystemExit("healthcheck evidence archive self-test failures:\n" + "\n".join(problems))

        remaining = _archive_dirs(root)
        if len(remaining) != 2:
            raise SystemExit(f"retention failed: expected 2 archives, found {len(remaining)}")

    print("healthcheck evidence archive OK")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--retain", type=int, default=int(os.environ.get("LINK_HEALTHCHECK_EVIDENCE_RETAIN", "10")))
    parser.add_argument("--archive-root", default=None)
    args = parser.parse_args()

    if args.self_test:
        self_test()
        return 0

    archive = run_healthcheck_and_archive(archive_root=args.archive_root, retain=args.retain)
    print(f"healthcheck evidence archive OK: {archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
