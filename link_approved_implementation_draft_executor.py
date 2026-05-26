#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import tempfile
from pathlib import Path
from typing import Any

VERSION = "LU239-approved-implementation-draft-executor-v1"

APPROVED_DIR = Path(".link/patch_drafts/approved")
JOB_DIR = Path(".link/approved_implementation_jobs")
AGENT_PENDING_DIR = Path(".link/agent_queue/pending")
RECEIPT_DIR = Path(".link/patch_drafts/receipts")

IMPLEMENT_TITLE_RE = re.compile(r"^implement approved research\s+", re.I)

def is_implementation_draft(data: dict[str, Any], path: Path) -> bool:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    task_id = str(data.get("task_id") or task.get("id") or "")
    title = str(data.get("title") or task.get("title") or "")
    source_id = str(data.get("draft_id") or data.get("source_candidate_id") or path.stem)
    haystack = " ".join([task_id, title, source_id]).lower()

    if IMPLEMENT_TITLE_RE.search(title):
        return True

    if task_id == "LU281":
        return True

    if "agent queue guarded implementation consumer" in haystack:
        return True

    return False




def load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=str(path.parent)) as tmp:
        tmp.write(text)
        tmp_path = Path(tmp.name)
    tmp_path.replace(path)


def slugify(value: str, limit: int = 90) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
    return value[:limit].strip("-") or "approved-implementation"


def hash_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def title_of(data: dict[str, Any]) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    return str(data.get("title") or task.get("title") or "")


def task_id_of(data: dict[str, Any], path: Path) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    return str(data.get("task_id") or task.get("id") or path.stem.split("-manual-")[-1].split("-")[0] or "")


def list_existing_source_ids() -> set[str]:
    seen: set[str] = set()
    for folder in (JOB_DIR, AGENT_PENDING_DIR):
        if not folder.exists():
            continue
        for path in folder.glob("*.json"):
            data = load_json(path) or {}
            sid = data.get("source_draft_id") or data.get("approved_draft_id")
            if sid:
                seen.add(str(sid))
    return seen


def approved_implementation_drafts() -> list[tuple[Path, dict[str, Any]]]:
    drafts: list[tuple[Path, dict[str, Any]]] = []

    for path in sorted(APPROVED_DIR.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        if not isinstance(data, dict):
            continue

        if not is_implementation_draft(data, path):
            continue

        drafts.append((path, data))

    return drafts


def build_job(path: Path, data: dict[str, Any]) -> dict[str, Any]:
    title = title_of(data)
    source_id = path.stem
    job_hash = hash_obj({"source_draft_id": source_id, "title": title, "version": VERSION})
    job_id = f"{source_id}-{job_hash}"
    now = dt.datetime.now().isoformat(timespec="seconds")

    return {
        "version": VERSION,
        "created_at": now,
        "job_id": job_id,
        "source_draft_id": source_id,
        "source_draft_path": str(path),
        "task_id": task_id_of(data, path),
        "title": title,
        "status": "pending_guarded_implementation",
        "risk": data.get("risk", "medium"),
        "why": data.get("why") or data.get("reason") or "",
        "plan": data.get("plan") or data.get("proposed_plan") or [],
        "files": data.get("files") or data.get("files_affected") or data.get("areas_affected") or [],
        "tests": data.get("tests") or data.get("checks") or [],
        "receipts": data.get("receipts") or [],
        "safety": [
            "Use guarded implementation path/worktree.",
            "Do not edit unrelated research/reference material.",
            "Run compile, smoke, healthcheck, and git diff checks before commit.",
            "Preserve approval receipt evidence and rollback safety."
        ],
    }


def write_jobs(write: bool) -> list[dict[str, Any]]:
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    AGENT_PENDING_DIR.mkdir(parents=True, exist_ok=True)

    existing = list_existing_source_ids()
    created: list[dict[str, Any]] = []

    for path, data in approved_implementation_drafts():
        if path.stem in existing:
            continue

        job = build_job(path, data)
        job_path = JOB_DIR / f"{job['job_id']}.json"
        agent_path = AGENT_PENDING_DIR / f"{job['job_id']}.json"

        job["job_path"] = str(job_path)
        job["agent_pending_path"] = str(agent_path)

        if write:
            atomic_write_json(job_path, job)
            atomic_write_json(agent_path, job)

        created.append(job)

    return created


def render(created: list[dict[str, Any]], write: bool) -> str:
    status = "ok" if created else "no_new_jobs"
    out = [
        "# Link Approved Implementation Draft Executor",
        "",
        f"Version: `{VERSION}`",
        f"Status: **{status}**",
        f"Write: **{write}**",
        f"Created jobs: **{len(created)}**",
        f"Job dir: `{JOB_DIR.resolve()}`",
        f"Agent pending dir: `{AGENT_PENDING_DIR.resolve()}`",
        "",
    ]

    for job in created:
        out += [
            f"## Job: {job['title']}",
            f"- Source draft: `{job['source_draft_id']}`",
            f"- Job ID: `{job['job_id']}`",
            f"- Job receipt: `{Path(job['job_path']).resolve()}`",
            f"- Agent pending: `{Path(job['agent_pending_path']).resolve()}`",
            "",
        ]

    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = ap.parse_args()

    if args.smoke:
        print("approved implementation draft executor smoke OK")
        return 0

    created = write_jobs(write=args.write)

    if args.format == "json":
        print(json.dumps({"version": VERSION, "created": created}, indent=2, sort_keys=True))
    else:
        print(render(created, write=args.write))

    if args.write:
        RECEIPT_DIR.mkdir(parents=True, exist_ok=True)
        stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
        atomic_write_json(RECEIPT_DIR / f"{stamp}-approved-implementation-jobs-created.json", {
            "version": VERSION,
            "created_at": dt.datetime.now().isoformat(timespec="seconds"),
            "created_count": len(created),
            "created_jobs": created,
        })

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
