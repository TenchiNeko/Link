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
