#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

from link_worker_dashboard_receipt_evidence import (
    WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION,
    build_worker_dashboard_receipt_evidence,
)


WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION = "LU98-worker-dashboard-evidence-index-v1"


def _compact(value: Any, limit: int = 180) -> str:
    text = str(value or "").strip()
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _safe_load_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception as exc:
        return None, str(exc)
    if not isinstance(payload, dict):
        return None, "json root is not an object"
    return payload, ""


def evidence_summary(payload: dict[str, Any], source: str = "") -> dict[str, Any]:
    summary = payload.get("summary", {})
    if not isinstance(summary, dict):
        summary = {}

    return {
        "source": source,
        "receipt_version": payload.get("receipt_version", ""),
        "generated": payload.get("generated", ""),
        "prompt": payload.get("prompt", ""),
        "route": payload.get("route", ""),
        "dispatch_ok": payload.get("dispatch_ok") is True,
        "dispatch_handled": payload.get("dispatch_handled") is True,
        "non_destructive": payload.get("non_destructive") is True,
        "dashboard_marker_present": payload.get("dashboard_marker_present") is True,
        "worker_profile": _compact(summary.get("worker_profile")),
        "current_task": _compact(summary.get("current_task")),
        "status": _compact(summary.get("status")),
        "pending_approval": summary.get("pending_approval"),
        "latest_test": _compact(summary.get("latest_test")),
        "branch": _compact(summary.get("branch")),
        "head": _compact(summary.get("head")),
        "working_tree_clean": summary.get("working_tree_clean"),
    }


def load_evidence_files(root: Path, limit: int = 20) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    evidence_dir = root / ".link" / "worker-dashboard-evidence"
    if not evidence_dir.exists():
        return [], []

    files = sorted(evidence_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    summaries: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    for path in files[:limit]:
        payload, error = _safe_load_json(path)
        if error or payload is None:
            errors.append({"source": str(path), "error": error})
            continue
        summaries.append(evidence_summary(payload, source=str(path)))

    return summaries, errors


def build_worker_dashboard_evidence_index(
    root: Path,
    limit: int = 20,
    include_live_preview: bool = True,
) -> dict[str, Any]:
    root = root.resolve()
    stored, errors = load_evidence_files(root, limit=limit)

    live_preview: dict[str, Any] | None = None
    if include_live_preview:
        live_payload = build_worker_dashboard_receipt_evidence(root=root, write=False)
        live_preview = evidence_summary(live_payload, source="live-preview")

    entries: list[dict[str, Any]] = []
    if live_preview is not None:
        entries.append(live_preview)
    entries.extend(stored)

    latest = entries[0] if entries else {}

    return {
        "receipt_version": WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "source_receipt_version": WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION,
        "evidence_dir": str(root / ".link" / "worker-dashboard-evidence"),
        "limit": limit,
        "include_live_preview": include_live_preview,
        "entry_count": len(entries),
        "stored_entry_count": len(stored),
        "error_count": len(errors),
        "latest": latest,
        "entries": entries,
        "errors": errors,
        "non_destructive": True,
    }


def render_worker_dashboard_evidence_index_markdown(index: dict[str, Any]) -> str:
    latest = index.get("latest", {})
    entries = index.get("entries", [])

    lines = [
        "# Link Worker Dashboard Evidence Index",
        "",
        f"Version: `{index.get('receipt_version')}`",
        f"Generated: {index.get('generated')}",
        f"Entries: **{index.get('entry_count')}**",
        f"Stored entries: **{index.get('stored_entry_count')}**",
        f"Errors: **{index.get('error_count')}**",
        f"Non-destructive: **{'yes' if index.get('non_destructive') else 'no'}**",
        "",
        "## Latest",
        "",
        f"- Source: `{latest.get('source', '')}`",
        f"- Worker profile: `{latest.get('worker_profile', '')}`",
        f"- Current task: {latest.get('current_task', '')}",
        f"- Status: **{latest.get('status', '')}**",
        f"- Pending approval: **{latest.get('pending_approval', '')}**",
        f"- Latest test: `{latest.get('latest_test', '')}`",
        f"- Branch: `{latest.get('branch', '')}`",
        f"- HEAD: `{latest.get('head', '')}`",
        "",
        "## Entries",
        "",
    ]

    if not entries:
        lines.append("- none")
    else:
        for item in entries[:10]:
            status = item.get("status", "")
            source = item.get("source", "")
            task = item.get("current_task", "")
            worker = item.get("worker_profile", "")
            lines.append(f"- `{source}` — **{status}** — `{worker}` — {task}")

    if index.get("errors"):
        lines.extend(["", "## Errors", ""])
        for err in index.get("errors", [])[:10]:
            lines.append(f"- `{err.get('source')}`: {err.get('error')}")

    return "\n".join(lines).rstrip() + "\n"


def render_worker_dashboard_evidence_index_html(index: dict[str, Any]) -> str:
    md = render_worker_dashboard_evidence_index_markdown(index)
    return (
        '<section class="link-worker-dashboard-evidence-index" '
        f'data-version="{html.escape(str(index.get("receipt_version", "")))}">'
        "<h2>Link Worker Dashboard Evidence Index</h2>"
        f"<pre>{html.escape(md)}</pre>"
        "</section>"
    )


def validate_worker_dashboard_evidence_index() -> list[str]:
    problems: list[str] = []
    index = build_worker_dashboard_evidence_index(Path.cwd(), include_live_preview=True)

    if index.get("receipt_version") != WORKER_DASHBOARD_EVIDENCE_INDEX_VERSION:
        problems.append("index version mismatch")

    if index.get("source_receipt_version") != WORKER_DASHBOARD_RECEIPT_EVIDENCE_VERSION:
        problems.append("source receipt version mismatch")

    if index.get("non_destructive") is not True:
        problems.append("index must be non-destructive")

    if index.get("entry_count", 0) < 1:
        problems.append("index should include live preview evidence")

    latest = index.get("latest", {})
    if not isinstance(latest, dict) or latest.get("dispatch_ok") is not True:
        problems.append(f"latest evidence is not dispatch-ok: {latest}")

    rendered = render_worker_dashboard_evidence_index_html(index)
    if "link-worker-dashboard-evidence-index" not in rendered:
        problems.append("HTML index marker missing")

    forbidden = ["git reset --hard", "git clean -fd", "git push --force"]
    for item in forbidden:
        if item in rendered:
            problems.append(f"rendered index contains forbidden text: {item}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Build Link worker dashboard evidence index.")
    parser.add_argument("--root", default=".")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--no-live-preview", action="store_true")
    args = parser.parse_args()

    index = build_worker_dashboard_evidence_index(
        root=Path(args.root),
        limit=max(1, args.limit),
        include_live_preview=not args.no_live_preview,
    )

    if args.format == "json":
        print(json.dumps(index, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_worker_dashboard_evidence_index_html(index))
    else:
        print(render_worker_dashboard_evidence_index_markdown(index), end="")

    return 0 if index.get("entry_count", 0) >= 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
