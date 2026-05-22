"""Project context loader for Link Factory."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTEXT_ROOT = ROOT / "factory" / "context"
MAX_CONTEXT_CHARS = 18000


def _read_markdown_files(path: Path) -> list[str]:
    if not path.exists():
        return []
    chunks: list[str] = []
    for file in sorted(path.glob("*.md")):
        try:
            text = file.read_text(encoding="utf-8").strip()
        except Exception:
            continue
        if text:
            chunks.append(f"# Context file: {file.relative_to(ROOT)}\n\n{text}")
    return chunks


def load_project_context(project: str | None) -> str:
    project = (project or "").strip()
    chunks: list[str] = []
    chunks.extend(_read_markdown_files(CONTEXT_ROOT / "_global"))
    if project:
        chunks.extend(_read_markdown_files(CONTEXT_ROOT / project))
    text = "\n\n---\n\n".join(chunks).strip()
    if len(text) > MAX_CONTEXT_CHARS:
        text = text[:MAX_CONTEXT_CHARS] + "\n\n[context truncated by loader]"
    return text


# === LU01 context/truncation hardening ===
CONTEXT_MANIFEST_SCHEMA_VERSION = "1.0"

def _lu01_relative_path(path: str) -> str:
    """Return deterministic relative-ish paths only; never emit absolute host paths."""
    from pathlib import Path as _Path
    value = str(path or "")
    try:
        pp = _Path(value)
        if pp.is_absolute():
            try:
                return pp.relative_to(_Path.cwd()).as_posix()
            except Exception:
                return pp.name
        return pp.as_posix()
    except Exception:
        return value.replace("\\", "/").lstrip("/")

def build_context_manifest(
    files_included=None,
    files_omitted=None,
    truncation_events=None,
    context_budget=None,
    max_tokens: int = 800,
) -> dict:
    """
    Deterministic manifest describing what context was included, omitted, or truncated.

    Critical rule:
    compression/capping may reduce verbose file detail, but must never remove:
    - integrity_status
    - blocking_flags
    - deliverable truncation events
    - required sentinel failures
    """
    import json

    files_included = files_included or []
    files_omitted = files_omitted or []
    truncation_events = truncation_events or []
    context_budget = context_budget or {}

    manifest = {
        "manifest_version": CONTEXT_MANIFEST_SCHEMA_VERSION,
        "context_budget": {
            "total_chars": int(context_budget.get("total_chars", 0) or 0),
            "total_tokens_est": int(context_budget.get("total_tokens_est", 0) or 0),
        },
        "files_included": [],
        "files_omitted": [],
        "truncation_events": [],
        "integrity_status": "PASS",
        "blocking_flags": [],
        "manifest_capped": False,
        "manifest_warnings": [],
    }

    for f in files_included:
        entry = {
            "path": _lu01_relative_path(f.get("path", f.get("file", ""))),
            "size_bytes": int(f.get("size_bytes", f.get("bytes", 0)) or 0),
            "truncated": bool(f.get("truncated", False)),
            "tail_sentinel": str(f.get("tail_sentinel", "OK") or "OK"),
            "required": bool(f.get("required", f.get("is_deliverable", False))),
            "is_deliverable": bool(f.get("is_deliverable", f.get("required", False))),
        }
        manifest["files_included"].append(entry)

    for f in files_omitted:
        manifest["files_omitted"].append({
            "path": _lu01_relative_path(f.get("path", f.get("file", ""))),
            "reason": str(f.get("reason", "unknown") or "unknown"),
            "required": bool(f.get("required", f.get("is_deliverable", False))),
            "is_deliverable": bool(f.get("is_deliverable", f.get("required", False))),
        })

    for e in truncation_events:
        manifest["truncation_events"].append({
            "file": _lu01_relative_path(e.get("file", e.get("path", ""))),
            "type": str(e.get("type", "unknown") or "unknown"),
            "missing_bytes": int(e.get("missing_bytes", 0) or 0),
            "is_deliverable": bool(e.get("is_deliverable", e.get("required", False))),
            "required": bool(e.get("required", e.get("is_deliverable", False))),
        })

    blocking = []

    for event in manifest["truncation_events"]:
        if event.get("is_deliverable") or event.get("required"):
            if event.get("type") in {"hard_clip", "soft_clip", "omitted", "missing", "truncated", "unknown"}:
                blocking.append(f"required_file_truncated::{event.get('file') or 'unknown'}")

    for f in manifest["files_included"]:
        sentinel = f.get("tail_sentinel", "OK")
        is_required = bool(f.get("required") or f.get("is_deliverable"))
        if is_required and sentinel == "MISSING":
            blocking.append(f"sentinel_missing::{f.get('path') or 'unknown'}")
        elif is_required and sentinel == "TRUNCATED":
            blocking.append(f"sentinel_truncated::{f.get('path') or 'unknown'}")
        elif is_required and f.get("truncated"):
            blocking.append(f"required_file_truncated::{f.get('path') or 'unknown'}")

    for f in manifest["files_omitted"]:
        if f.get("required") or f.get("is_deliverable"):
            blocking.append(f"required_file_omitted::{f.get('path') or 'unknown'}")

    # Deterministic order and de-dupe.
    manifest["blocking_flags"] = sorted(set(blocking))

    if manifest["blocking_flags"]:
        manifest["integrity_status"] = "FAIL"
    elif any(e.get("type") for e in manifest["truncation_events"]):
        manifest["integrity_status"] = "WARN"
        manifest["manifest_warnings"].append("non_blocking_truncation_detected")

    # Cap verbose details without ever removing blocking flags or critical events.
    max_chars = max(512, int(max_tokens) * 4)
    if len(json.dumps(manifest, sort_keys=True)) > max_chars:
        manifest["manifest_capped"] = True
        manifest["manifest_warnings"].append("manifest_detail_capped")

        critical_events = [
            e for e in manifest["truncation_events"]
            if e.get("required") or e.get("is_deliverable")
        ]

        manifest["files_included_count"] = len(manifest["files_included"])
        manifest["files_omitted_count"] = len(manifest["files_omitted"])
        manifest["truncation_events_count"] = len(manifest["truncation_events"])

        manifest["files_included"] = manifest["files_included"][:25]
        manifest["files_omitted"] = manifest["files_omitted"][:25]
        manifest["truncation_events"] = critical_events + [
            e for e in manifest["truncation_events"]
            if e not in critical_events
        ][:25]

    return manifest
# === end LU01 context/truncation hardening ===

