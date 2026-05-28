
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent


def default_evidence_root() -> Path:
    configured = (
        os.environ.get("LINK_HEALTHCHECK_EVIDENCE_DIR")
        or os.environ.get("LINK_HEALTHCHECK_ARCHIVE_DIR")
    )
    if configured:
        return Path(configured)
    return ROOT / ".agents" / "healthcheck_evidence"


def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _archive_summary(path: Path) -> dict[str, Any]:
    metadata = _read_json(path / "metadata.json")
    healthcheck_log = path / "healthcheck.log"

    status = str(
        metadata.get("status")
        or metadata.get("healthcheck_status")
        or metadata.get("result")
        or "UNKNOWN"
    ).upper()

    created_at = str(
        metadata.get("created_at")
        or metadata.get("timestamp")
        or metadata.get("archived_at")
        or path.name
    )

    commit = str(
        metadata.get("commit")
        or metadata.get("head")
        or metadata.get("head_commit")
        or metadata.get("git_head")
        or ""
    )

    summary = str(
        metadata.get("summary")
        or metadata.get("reason")
        or metadata.get("description")
        or ""
    )

    marker_text = ""
    if healthcheck_log.exists():
        try:
            marker_text = healthcheck_log.read_text(errors="replace")[-4000:]
        except Exception:
            marker_text = ""

    markers = []
    for marker in (
        "LINK HEALTHCHECK PASSED",
        "Traceback",
        "FAILED",
        "ERROR",
        "healthcheck evidence archive OK",
        "upgrade evidence bundle OK",
    ):
        if marker in marker_text:
            markers.append(marker)

    return {
        "archive": path.name,
        "path": str(path),
        "created_at": created_at,
        "status": status,
        "commit": commit,
        "summary": summary,
        "markers": markers,
        "has_metadata": (path / "metadata.json").exists(),
        "has_healthcheck_log": healthcheck_log.exists(),
    }


def iter_evidence_archives(root: str | Path | None = None) -> list[Path]:
    base = Path(root) if root is not None else default_evidence_root()
    if not base.exists():
        return []

    archives = []
    for child in base.iterdir():
        if not child.is_dir():
            continue
        if (child / "metadata.json").exists() or (child / "healthcheck.log").exists():
            archives.append(child)

    return sorted(archives, key=lambda p: p.name, reverse=True)


def build_evidence_index(root: str | Path | None = None) -> dict[str, Any]:
    base = Path(root) if root is not None else default_evidence_root()
    archives = [_archive_summary(path) for path in iter_evidence_archives(base)]

    return {
        "index_version": "1.0",
        "root": str(base),
        "archive_count": len(archives),
        "archives": archives,
    }


def write_evidence_index(root: str | Path | None = None, output: str | Path | None = None) -> Path:
    index = build_evidence_index(root)
    base = Path(index["root"])
    out = Path(output) if output is not None else base / "index.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    return out


def search_evidence_index(
    query: str = "",
    root: str | Path | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    index = build_evidence_index(root)
    q = (query or "").lower().strip()
    wanted_status = (status or "").upper().strip()

    hits = []
    for row in index["archives"]:
        haystack = " ".join(
            [
                row.get("archive", ""),
                row.get("path", ""),
                row.get("created_at", ""),
                row.get("status", ""),
                row.get("commit", ""),
                row.get("summary", ""),
                " ".join(row.get("markers", [])),
            ]
        ).lower()

        if wanted_status and row.get("status", "").upper() != wanted_status:
            continue
        if q and q not in haystack:
            continue

        hits.append(row)
        if len(hits) >= limit:
            break

    return hits


def format_rows(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No matching healthcheck evidence archives."

    lines = []
    for row in rows:
        markers = ", ".join(row.get("markers", [])) or "-"
        lines.append(
            f"{row.get('archive')} [{row.get('status')}] "
            f"commit={row.get('commit') or '-'} markers={markers}"
        )
    return "\n".join(lines)


def self_test() -> list[str]:
    import tempfile

    problems = []
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)

        passed = root / "20260101-pass"
        passed.mkdir()
        (passed / "metadata.json").write_text(json.dumps({
            "created_at": "2026-01-01T00:00:00Z",
            "status": "PASS",
            "commit": "abc123",
            "summary": "clean healthcheck",
        }))
        (passed / "healthcheck.log").write_text("LINK HEALTHCHECK PASSED\n")

        failed = root / "20260102-fail"
        failed.mkdir()
        (failed / "metadata.json").write_text(json.dumps({
            "created_at": "2026-01-02T00:00:00Z",
            "status": "FAIL",
            "commit": "def456",
            "summary": "simulated failure",
        }))
        (failed / "healthcheck.log").write_text("FAILED\nTraceback\n")

        index = build_evidence_index(root)
        if index["archive_count"] != 2:
            problems.append("expected_two_archives")

        fail_hits = search_evidence_index("simulated", root=root, status="FAIL")
        if len(fail_hits) != 1 or fail_hits[0]["commit"] != "def456":
            problems.append("search_failed_archive_mismatch")

        out = write_evidence_index(root)
        if not out.exists():
            problems.append("index_file_not_written")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Index and search retained healthcheck evidence archives.")
    parser.add_argument("--root", default=None, help="Evidence archive root directory.")
    parser.add_argument("--write", action="store_true", help="Write index.json into the evidence root.")
    parser.add_argument("--query", default="", help="Search query.")
    parser.add_argument("--status", default=None, help="Optional status filter, e.g. PASS or FAIL.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = self_test()
        if problems:
            print("healthcheck evidence index FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print("healthcheck evidence index OK")
        return 0

    if args.write:
        out = write_evidence_index(args.root)
        print(f"wrote {out}")

    rows = search_evidence_index(args.query, root=args.root, status=args.status, limit=args.limit)
    print(format_rows(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
