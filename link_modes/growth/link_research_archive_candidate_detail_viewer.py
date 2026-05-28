#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_INTAKE_DIR = ROOT / ".link_research_intake"
LATEST_NAME = "LATEST_RUN.txt"
CANDIDATE_FILES_NAME = "candidate_files.txt"

MARKER = "research archive intake candidate detail viewer OK"

TRIGGERS = (
    "research archive candidate",
    "research intake candidate",
    "research candidate detail",
    "show research candidate",
    "view research candidate",
    "candidate detail viewer",
    "candidate file detail",
    "show candidate detail",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def matches_research_candidate_detail_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    return any(trigger in lowered for trigger in TRIGGERS)


def normalize_direct_candidate_detail_prompt(prompt: str, explicit_candidate: str | None = None) -> str:
    """Make direct CLI shorthand like `--json top 1` route as a matched detail request."""
    text = (prompt or "").strip()
    if not text:
        return "show research archive candidate detail"

    if matches_research_candidate_detail_prompt(text):
        return text

    # Direct CLI callers often pass only a selector/path because the script name
    # already implies the research archive candidate detail action.
    if explicit_candidate:
        return f"show research archive candidate detail {text}".strip()

    if re.search(r"\b(?:top|rank|candidate)\s*#?\s*\d+\b", text.lower()):
        return f"show research archive candidate detail {text}"

    if re.search(r"[A-Za-z0-9_.-]+\.(?:tsx|ts|jsx|js|py|md|txt|json|jsonl|yaml|yml|sh|html|css)", text):
        return f"show research archive candidate detail {text}"

    return text


def parse_limit(prompt: str, default: int = 20_000) -> int:
    lowered = prompt.lower()
    match = re.search(r"\b(?:limit|chars?|characters?)\s+(\d+)\b", lowered)
    if not match:
        return default
    try:
        return max(1_000, min(80_000, int(match.group(1))))
    except Exception:
        return default


def parse_candidate_number(prompt: str) -> int | None:
    lowered = prompt.lower()
    patterns = (
        r"\b(?:candidate|rank|top)\s*#?\s*(\d+)\b",
        r"#\s*(\d+)\b",
    )
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if not match:
            continue
        try:
            value = int(match.group(1))
        except Exception:
            continue
        if value > 0:
            return value
    return None


def _rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)))
    except Exception:
        return str(path)


def _latest_run_dir(intake_dir: Path) -> Path | None:
    latest_path = intake_dir / LATEST_NAME
    if latest_path.exists() and latest_path.is_file():
        raw = latest_path.read_text(encoding="utf-8", errors="replace").strip()
        if raw:
            candidate = intake_dir / raw
            try:
                candidate.resolve(strict=False).relative_to(intake_dir.resolve(strict=False))
            except ValueError:
                candidate = None
            if candidate is not None and candidate.exists() and candidate.is_dir():
                return candidate

    if not intake_dir.exists():
        return None

    runs = [
        path
        for path in intake_dir.iterdir()
        if path.is_dir() and path.name.startswith("research-mining-")
    ]
    if not runs:
        return None

    return max(runs, key=lambda p: p.stat().st_mtime)


def _candidate_file(run_dir: Path) -> Path:
    return run_dir / CANDIDATE_FILES_NAME


def load_candidates(run_dir: Path, *, max_count: int = 5000) -> list[str]:
    path = _candidate_file(run_dir)
    if not path.exists() or not path.is_file():
        return []

    candidates: list[str] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    # Be tolerant of accidental literal backslash-n entries emitted by earlier
    # fixture/diagnostic scripts.
    text = text.replace("\\n", "\n")
    for raw in text.splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue
        candidates.append(value)
        if len(candidates) >= max_count:
            break
    return candidates


def select_candidate(prompt: str, candidates: list[str], explicit_candidate: str | None = None) -> str | None:
    if explicit_candidate:
        explicit = explicit_candidate.strip()
        for candidate in candidates:
            if candidate == explicit:
                return candidate
        for candidate in candidates:
            if candidate.lower() == explicit.lower():
                return candidate
        return explicit

    if not candidates:
        return None

    number = parse_candidate_number(prompt)
    if number is not None and 1 <= number <= len(candidates):
        return candidates[number - 1]

    lowered = prompt.lower()

    # Prefer exact path containment, preserving original candidate casing.
    for candidate in candidates:
        if candidate.lower() in lowered:
            return candidate

    # Then try quoted path snippets.
    for quoted in re.findall(r"""["']([^"']+)["']""", prompt):
        q = quoted.strip()
        for candidate in candidates:
            if candidate == q or candidate.lower() == q.lower():
                return candidate
            if q.lower() in candidate.lower():
                return candidate

    # Finally, match by basename or path suffix if the user provides only a file
    # name/path-like token.
    tokens = re.findall(r"[A-Za-z0-9_./-]+\.(?:tsx|ts|jsx|js|py|md|txt|json|jsonl|yaml|yml|sh|html|css)", prompt)
    for token in tokens:
        t = token.strip().strip("'\\\"").lower()
        for candidate in candidates:
            c = candidate.lower()
            if Path(candidate).name.lower() == Path(t).name.lower():
                return candidate
            if c.endswith(t) or t.endswith(c):
                return candidate

    return candidates[0]


def _safe_candidate_path(run_dir: Path, candidate: str) -> Path | None:
    extracted = run_dir / "extracted"
    path = extracted / candidate

    extracted_resolved = extracted.resolve(strict=False)
    path_resolved = path.resolve(strict=False)

    try:
        path_resolved.relative_to(extracted_resolved)
    except ValueError:
        return None

    if path_resolved.exists() and path_resolved.is_file():
        return path_resolved

    return None


def _read_preview(path: Path, limit: int) -> tuple[str, bool]:
    text = path.read_text(encoding="utf-8", errors="replace")
    truncated = len(text) > limit
    if truncated:
        text = text[:limit] + "\n\n... truncated ..."
    return text, truncated


def _line_count(path: Path) -> int:
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def _keyword_counts(text: str) -> dict[str, int]:
    keywords = [
        "todo",
        "fixme",
        "agent",
        "workflow",
        "route",
        "guard",
        "policy",
        "context",
        "budget",
        "archive",
        "extract",
        "reference",
        "missing",
        "gap",
        "implement",
        "feature",
        "command",
        "delegate",
    ]
    lowered = text.lower()
    return {keyword: lowered.count(keyword) for keyword in keywords if lowered.count(keyword)}


def build_research_archive_candidate_detail_response(
    prompt: str,
    intake_dir: Path | None = None,
    *,
    candidate: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    selected_intake_dir = intake_dir or DEFAULT_INTAKE_DIR
    run_dir = _latest_run_dir(selected_intake_dir)
    char_limit = limit if limit is not None else parse_limit(prompt)

    if run_dir is None:
        payload = {
            "ok": False,
            "kind": "research_archive_candidate_detail_viewer",
            "matched": matches_research_candidate_detail_prompt(prompt),
            "json_requested": wants_json(prompt),
            "non_destructive": True,
            "status": "missing_latest_run",
            "intake_dir": _rel(selected_intake_dir),
            "latest_run": None,
            "candidate": None,
            "html": "",
        }
        payload["html"] = render_research_archive_candidate_detail_response(payload)
        return payload

    candidates = load_candidates(run_dir)
    selected_candidate = select_candidate(prompt, candidates, candidate)
    candidate_path = (
        _safe_candidate_path(run_dir, selected_candidate)
        if selected_candidate is not None
        else None
    )

    if selected_candidate is None or candidate_path is None:
        payload = {
            "ok": False,
            "kind": "research_archive_candidate_detail_viewer",
            "matched": matches_research_candidate_detail_prompt(prompt),
            "json_requested": wants_json(prompt),
            "non_destructive": True,
            "status": "missing_candidate_file",
            "intake_dir": _rel(selected_intake_dir),
            "latest_run": _rel(run_dir),
            "candidate": selected_candidate,
            "candidate_count": len(candidates),
            "available_candidates": candidates[:25],
            "html": "",
        }
        payload["html"] = render_research_archive_candidate_detail_response(payload)
        return payload

    content_preview, truncated = _read_preview(candidate_path, char_limit)
    content_sha = hashlib.sha256(candidate_path.read_bytes()).hexdigest()

    payload = {
        "ok": True,
        "kind": "research_archive_candidate_detail_viewer",
        "matched": matches_research_candidate_detail_prompt(prompt),
        "json_requested": wants_json(prompt),
        "non_destructive": True,
        "data_link_card": "research-archive-candidate-detail",
        "status": "ok",
        "intake_dir": _rel(selected_intake_dir),
        "latest_run": _rel(run_dir),
        "candidate": selected_candidate,
        "candidate_rank": candidates.index(selected_candidate) + 1 if selected_candidate in candidates else None,
        "candidate_count": len(candidates),
        "path": _rel(candidate_path),
        "size_bytes": candidate_path.stat().st_size,
        "line_count": _line_count(candidate_path),
        "sha256": content_sha,
        "preview_char_limit": char_limit,
        "preview_truncated": truncated,
        "keyword_counts": _keyword_counts(content_preview),
        "content_preview": content_preview,
        "html": "",
    }
    payload["html"] = render_research_archive_candidate_detail_response(payload)
    return payload


def render_research_archive_candidate_detail_response(payload: dict[str, Any]) -> str:
    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    status = str(payload.get("status") or "unknown")
    candidate = payload.get("candidate")
    preview = str(payload.get("content_preview") or "")

    if not payload.get("ok"):
        available = payload.get("available_candidates")
        items = ""
        if isinstance(available, list) and available:
            items = "<h3>Available candidates</h3><ol>" + "".join(
                f"<li><code>{esc(item)}</code></li>" for item in available[:25]
            ) + "</ol>"
        return (
            '<section class="dashboard-card research-archive-candidate-detail error" '
            'data-link-card="research-archive-candidate-detail" '
            'data-link-destructive="false">'
            "<h2>Research archive candidate detail</h2>"
            f"<p>Status: <strong>{esc(status)}</strong></p>"
            f"<p>Latest run: <code>{esc(payload.get('latest_run'))}</code></p>"
            f"<p>Candidate: <code>{esc(candidate)}</code></p>"
            f"{items}"
            "</section>"
        )

    keyword_counts = payload.get("keyword_counts")
    keyword_html = ""
    if isinstance(keyword_counts, dict) and keyword_counts:
        keyword_html = "<h3>Keyword counts</h3><ul>" + "".join(
            f"<li><code>{esc(k)}</code>: <code>{esc(v)}</code></li>"
            for k, v in sorted(keyword_counts.items())
        ) + "</ul>"

    return (
        '<section class="dashboard-card research-archive-candidate-detail" '
        'data-link-card="research-archive-candidate-detail" '
        'data-link-destructive="false">'
        "<h2>Research archive candidate detail</h2>"
        f"<p>Status: <strong>{esc(status)}</strong></p>"
        f"<p>Candidate: <code>{esc(candidate)}</code></p>"
        "<ul>"
        f"<li>Rank: <code>{esc(payload.get('candidate_rank'))}</code> of <code>{esc(payload.get('candidate_count'))}</code></li>"
        f"<li>Path: <code>{esc(payload.get('path'))}</code></li>"
        f"<li>Size: <code>{esc(payload.get('size_bytes'))}</code> bytes</li>"
        f"<li>Lines: <code>{esc(payload.get('line_count'))}</code></li>"
        f"<li>SHA256: <code>{esc(payload.get('sha256'))}</code></li>"
        f"<li>Preview truncated: <code>{esc(payload.get('preview_truncated'))}</code></li>"
        "</ul>"
        f"{keyword_html}"
        "<h3>Content preview</h3>"
        f"<pre>{html.escape(preview)}</pre>"
        "</section>"
    )


def route_research_archive_candidate_detail_prompt(prompt: str) -> list[str] | None:
    if not matches_research_candidate_detail_prompt(prompt):
        return None

    response = build_research_archive_candidate_detail_response(prompt)
    if wants_json(prompt):
        return [json.dumps(response, indent=2, sort_keys=True)]

    return [str(response.get("html") or "")]


def validate_research_archive_candidate_detail_viewer() -> list[str]:
    problems: list[str] = []

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        run_dir = intake_dir / "research-mining-candidate-test"
        extracted = run_dir / "extracted"
        candidate_rel = "Research/Research/src/screens/REPL.tsx"
        candidate_path = extracted / candidate_rel
        candidate_path.parent.mkdir(parents=True)
        candidate_path.write_text(
            "const agent = 'test';\n"
            "// TODO: route workflow command guard context\n"
            "export function demo() { return agent }\n",
            encoding="utf-8",
        )

        run_dir.mkdir(parents=True, exist_ok=True)
        (intake_dir / LATEST_NAME).write_text(run_dir.name, encoding="utf-8")
        (run_dir / CANDIDATE_FILES_NAME).write_text(candidate_rel + "\n", encoding="utf-8")

        response = build_research_archive_candidate_detail_response(
            f"show research archive candidate detail json {candidate_rel}",
            intake_dir,
        )

        if not response.get("ok"):
            problems.append("candidate detail response should be ok")
        if not response.get("matched"):
            problems.append("candidate detail response should be matched")
        if not response.get("json_requested"):
            problems.append("candidate detail response should detect json")
        if not response.get("non_destructive"):
            problems.append("candidate detail response should be non-destructive")
        if response.get("candidate") != candidate_rel:
            problems.append("candidate detail selected wrong candidate")
        if "TODO" not in str(response.get("content_preview") or ""):
            problems.append("candidate detail content preview missing source content")
        if response.get("line_count") != 3:
            problems.append("candidate detail line count mismatch")

        rendered = str(response.get("html") or "")
        if "Research archive candidate detail" not in rendered:
            problems.append("candidate detail HTML missing title")
        if "research-archive-candidate-detail" not in rendered:
            problems.append("candidate detail HTML missing card marker")
        if 'data-link-destructive="false"' not in rendered:
            problems.append("candidate detail HTML missing non-destructive marker")

        missing = build_research_archive_candidate_detail_response(
            "show research archive candidate detail json ../outside.txt",
            intake_dir,
            candidate="../outside.txt",
        )
        if missing.get("ok"):
            problems.append("candidate detail should reject outside path")

    nonmatch = route_research_archive_candidate_detail_prompt("show recovery dashboard")
    if nonmatch is not None:
        problems.append("candidate detail route should ignore unrelated prompts")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Research archive intake candidate detail viewer.")
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--candidate")
    parser.add_argument("--intake-dir")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_research_archive_candidate_detail_viewer()
        if problems:
            print("research archive intake candidate detail viewer FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    raw_prompt = " ".join(args.prompt) if args.prompt else "show research archive candidate detail"
    prompt = normalize_direct_candidate_detail_prompt(
        raw_prompt,
        explicit_candidate=args.candidate,
    )
    if args.json and " json" not in f" {prompt.lower()} ":
        prompt = f"{prompt} json"

    response = build_research_archive_candidate_detail_response(
        prompt,
        Path(args.intake_dir) if args.intake_dir else None,
        candidate=args.candidate,
        limit=args.limit,
    )

    if wants_json(prompt):
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
