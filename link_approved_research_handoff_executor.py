#!/usr/bin/env python3
from __future__ import annotations

import argparse, datetime as dt, hashlib, json, re, tempfile
from pathlib import Path
from typing import Any

VERSION = "LU228-approved-research-handoff-executor-v1"

EXCLUDED_TITLES = {
    "approved research proposal implementation queue",
    "approved research handoff executor",
}

RESEARCH_TASK_IDS = {"LU201", "LU202", "LU203", "LU204", "LU205", "LU206"}


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _hash_obj(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]


def _title_of(data: dict[str, Any]) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    return str(data.get("title") or task.get("title") or "")


def _task_id_of(data: dict[str, Any]) -> str:
    task = data.get("task") if isinstance(data.get("task"), dict) else {}
    return str(data.get("task_id") or task.get("id") or "")


def _is_research_approved_draft(data: dict[str, Any]) -> bool:
    title = _title_of(data).strip().lower()
    if title in EXCLUDED_TITLES:
        return False

    task_id = _task_id_of(data)
    source = str(data.get("source") or "")
    source_version = str(data.get("source_version") or "")
    has_evidence = bool(data.get("evidence"))

    return (
        task_id in RESEARCH_TASK_IDS
        or source == "research_upgrade_miner"
        or "research-upgrade" in source_version
        or has_evidence
    )


def _existing_handoff_source_ids(handoff_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in handoff_dir.glob("*.json"):
        data = _load_json(path)
        if not data:
            continue
        source_draft_id = str(data.get("source_draft_id") or "")
        if source_draft_id:
            ids.add(source_draft_id)
    return ids


def ensure_handoffs(root: str | Path = ".", write: bool = True) -> dict[str, Any]:
    root = Path(root)
    approved_dir = root / ".link/patch_drafts/approved"
    handoff_dir = root / ".link/approved_research_handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)

    existing_source_ids = _existing_handoff_source_ids(handoff_dir)
    created: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    for approved_path in sorted(approved_dir.glob("*.json")) if approved_dir.exists() else []:
        data = _load_json(approved_path)
        if not data:
            skipped.append({"path": str(approved_path), "reason": "unreadable_json"})
            continue

        if not _is_research_approved_draft(data):
            continue

        draft_id = str(data.get("draft_id") or approved_path.stem)
        if draft_id in existing_source_ids:
            skipped.append({"draft_id": draft_id, "reason": "handoff_already_exists"})
            continue

        title = _title_of(data)
        task_id = _task_id_of(data)
        handoff_id = f"{draft_id}-{_hash_obj({'draft_id': draft_id, 'proposal_hash': data.get('proposal_hash'), 'title': title})}"

        handoff = {
            "receipt_version": VERSION,
            "status": "ready_for_implementation_candidate",
            "action": "approved_research_handoff_created",
            "handoff_id": handoff_id,
            "source_draft_id": draft_id,
            "source_task_id": task_id,
            "source_title": title,
            "source_proposal_hash": data.get("proposal_hash") or data.get("hash"),
            "source_path": str(approved_path.resolve()),
            "source_files": data.get("files") or data.get("files_affected") or data.get("areas_affected") or [],
            "source_plan": data.get("plan") or data.get("proposed_plan") or [],
            "source_tests": data.get("tests") or data.get("checks") or [],
            "source_evidence": data.get("evidence") or [],
            "why": "Approved research-derived proposal is ready to be converted into a concrete implementation candidate while preserving human approval and rollback safety.",
            "created_at": dt.datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        }

        handoff_path = handoff_dir / f"{handoff_id}.json"
        handoff["handoff_path"] = str(handoff_path.resolve())

        if write:
            handoff_path.write_text(json.dumps(handoff, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

        created.append(handoff)

    return {
        "version": VERSION,
        "status": "ok",
        "action": "ensure_approved_research_handoffs",
        "created_count": len(created),
        "skipped_count": len(skipped),
        "handoff_dir": str(handoff_dir.resolve()),
        "created": created,
        "skipped": skipped[:25],
    }


def render_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Link Approved Research Handoff Executor",
        "",
        f"Version: `{VERSION}`",
        f"Status: **{result.get('status')}**",
        f"Action: `{result.get('action')}`",
        f"Created handoffs: **{result.get('created_count', 0)}**",
        f"Handoff dir: `{result.get('handoff_dir')}`",
        "",
    ]
    for item in result.get("created", []):
        lines.extend([
            f"## Handoff: {item.get('source_title')}",
            f"- Source draft: `{item.get('source_draft_id')}`",
            f"- Handoff ID: `{item.get('handoff_id')}`",
            f"- Path: `{item.get('handoff_path')}`",
            "",
        ])
    return "\n".join(lines)


def smoke() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        approved = root / ".link/patch_drafts/approved"
        approved.mkdir(parents=True)
        sample = {
            "draft_id": "smoke-lu201-research-evidence-index",
            "task_id": "LU201",
            "title": "research evidence index for upgrade proposals",
            "source": "research_upgrade_miner",
            "proposal_hash": "abc123",
            "files": ["link_research_upgrade_miner.py"],
            "plan": ["Index research evidence."],
            "evidence": [{"source_path": "research/example.md", "line": 1, "snippet": "agent research"}],
        }
        (approved / "smoke-lu201-research-evidence-index.json").write_text(json.dumps(sample), encoding="utf-8")
        result = ensure_handoffs(root, write=True)
        assert result["created_count"] == 1, result
        assert list((root / ".link/approved_research_handoffs").glob("*.json"))
    print("approved research handoff executor smoke OK")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    args = parser.parse_args()

    if args.smoke:
        smoke()
        return

    result = ensure_handoffs(args.root, write=args.write)
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True, default=str))
    else:
        print(render_markdown(result))


if __name__ == "__main__":
    main()
