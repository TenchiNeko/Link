#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_INTAKE_DIR = ROOT / ".link_research_intake"
LATEST_NAME = "LATEST_RUN.txt"
CANDIDATE_FILES_NAME = "candidate_files.txt"
DIRECTORY_MAP_NAME = "DIRECTORY_MAP.md"
JSON_NAME = "research_candidate_shortlist.json"
REPORT_NAME = "CANDIDATE_SHORTLIST.md"

MARKER = "research archive candidate shortlist exporter OK"


_SCORE_RE = re.compile(
    r"^- score `(?P<score>\d+)` `(?P<path>[^`]+)`(?:\s+—\s+(?P<summary>.*))?$"
)


def _safe_rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except Exception:
        return str(path)


def normalize_candidate_path(value: str) -> str:
    text = (value or "").strip().strip("'\"")
    literal_backslash = chr(92)
    text = text.replace(literal_backslash + "r" + literal_backslash + "n", "\n")
    text = text.replace(literal_backslash + "n", "\n")
    text = text.splitlines()[0].strip().strip("'\"") if text.splitlines() else text
    text = text.replace("\\", "/")
    text = re.sub(r"^\./+", "", text)

    marker = "/extracted/"
    if marker in text:
        text = text.split(marker, 1)[1]

    return text.strip()


def candidate_lookup_keys(value: str) -> list[str]:
    norm = normalize_candidate_path(value)
    keys = [value, norm]

    parts = norm.split("/")
    for i in range(1, min(len(parts), 5)):
        keys.append("/".join(parts[i:]))

    out: list[str] = []
    seen: set[str] = set()
    for key in keys:
        clean = normalize_candidate_path(key)
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


def find_latest_run(intake_dir: Path = DEFAULT_INTAKE_DIR) -> Path | None:
    base = intake_dir
    latest_file = base / LATEST_NAME

    if latest_file.exists():
        name = latest_file.read_text(encoding="utf-8", errors="replace").strip()
        if name:
            run = Path(name)
            if not run.is_absolute():
                if name.startswith(str(base)):
                    run = ROOT / name
                else:
                    run = base / name
            if run.exists() and run.is_dir():
                return run

    if not base.exists():
        return None

    runs = [p for p in base.iterdir() if p.is_dir()]
    if not runs:
        return None

    return max(runs, key=lambda p: p.stat().st_mtime)


def load_candidates(run_dir: Path, *, max_count: int = 5000) -> list[str]:
    path = run_dir / CANDIDATE_FILES_NAME
    if not path.exists():
        return []

    text = path.read_text(encoding="utf-8", errors="replace")
    literal_backslash = chr(92)
    text = text.replace(literal_backslash + "r" + literal_backslash + "n", "\n")
    text = text.replace(literal_backslash + "n", "\n")

    candidates: list[str] = []
    seen: set[str] = set()

    for raw in text.splitlines():
        value = raw.strip()
        if not value or value.startswith("#"):
            continue

        match = _SCORE_RE.match(value)
        if match:
            value = match.group("path")

        value = normalize_candidate_path(value)
        if not value or value in seen:
            continue

        seen.add(value)
        candidates.append(value)

        if len(candidates) >= max_count:
            break

    return candidates


def parse_keyword_summary(summary: str | None) -> dict[str, int]:
    if not summary:
        return {}

    counts: dict[str, int] = {}

    for item in summary.split(","):
        key, sep, raw_value = item.strip().partition(":")
        if not sep:
            continue

        key = key.strip()
        raw_value = raw_value.strip()

        if not key or not raw_value:
            continue

        try:
            counts[key] = int(raw_value)
        except ValueError:
            continue

    return counts


def parse_directory_map_scores(run_dir: Path) -> dict[str, dict[str, Any]]:
    path = run_dir / DIRECTORY_MAP_NAME
    if not path.exists():
        return {}

    scores: dict[str, dict[str, Any]] = {}

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = _SCORE_RE.match(raw.strip())
        if not match:
            continue

        candidate = normalize_candidate_path(match.group("path"))
        info = {
            "score": int(match.group("score")),
            "keyword_counts": parse_keyword_summary(match.group("summary")),
            "directory_map_summary": match.group("summary") or "",
        }

        for key in candidate_lookup_keys(candidate):
            scores[key] = info

    return scores


def candidate_abs_path(run_dir: Path, candidate: str) -> Path:
    return run_dir / "extracted" / normalize_candidate_path(candidate)


def file_digest(path: Path, *, max_bytes: int = 256 * 1024) -> str | None:
    if not path.exists() or not path.is_file():
        return None

    h = hashlib.sha256()
    with path.open("rb") as f:
        remaining = max_bytes
        while remaining > 0:
            chunk = f.read(min(65536, remaining))
            if not chunk:
                break
            h.update(chunk)
            remaining -= len(chunk)

    return h.hexdigest()


def read_preview(path: Path, *, limit: int = 1200) -> str:
    if not path.exists() or not path.is_file():
        return ""

    return path.read_text(encoding="utf-8", errors="replace")[:limit]


def build_shortlist_records(
    run_dir: Path,
    *,
    limit: int = 25,
    preview_limit: int = 1200,
) -> tuple[list[dict[str, Any]], int]:
    candidates = load_candidates(run_dir)
    scores = parse_directory_map_scores(run_dir)

    records: list[dict[str, Any]] = []

    for rank, candidate in enumerate(candidates, start=1):
        abs_path = candidate_abs_path(run_dir, candidate)
        if not abs_path.exists() or not abs_path.is_file():
            continue

        score_info: dict[str, Any] = {}
        for key in candidate_lookup_keys(candidate):
            if key in scores:
                score_info = scores[key]
                break

        text = read_preview(abs_path, limit=preview_limit)
        try:
            line_count = abs_path.read_text(encoding="utf-8", errors="replace").count("\n") + 1
        except Exception:
            line_count = 0

        records.append(
            {
                "rank": rank,
                "candidate": normalize_candidate_path(candidate),
                "path": _safe_rel(abs_path),
                "exists": True,
                "size_bytes": abs_path.stat().st_size,
                "line_count": line_count,
                "sha256_prefix": file_digest(abs_path),
                "score": score_info.get("score"),
                "keyword_counts": score_info.get("keyword_counts", {}),
                "directory_map_summary": score_info.get("directory_map_summary", ""),
                "preview": text,
                "preview_truncated": len(text) >= preview_limit,
            }
        )

        if len(records) >= limit:
            break

    return records, len(candidates)


def write_shortlist_outputs(run_dir: Path, records: list[dict[str, Any]], candidate_count: int) -> dict[str, str]:
    created_at = datetime.now(timezone.utc).isoformat()

    data = {
        "ok": True,
        "marker": MARKER,
        "created_at": created_at,
        "candidate_count": candidate_count,
        "shortlist_count": len(records),
        "records": records,
    }

    json_path = run_dir / JSON_NAME
    report_path = run_dir / REPORT_NAME

    json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")

    lines = [
        "# Research archive candidate shortlist",
        "",
        f"- Created: `{created_at}`",
        f"- Candidates: `{candidate_count}`",
        f"- Shortlist: `{len(records)}`",
        "",
    ]

    for record in records:
        lines.extend(
            [
                f"## {record['rank']}. `{record['candidate']}`",
                "",
                f"- Score: `{record.get('score')}`",
                f"- Size: `{record.get('size_bytes')}` bytes",
                f"- Lines: `{record.get('line_count')}`",
                f"- SHA256 prefix digest: `{record.get('sha256_prefix')}`",
                f"- Keyword counts: `{json.dumps(record.get('keyword_counts', {}), sort_keys=True)}`",
                "",
                "```",
                record.get("preview", ""),
                "```",
                "",
            ]
        )

    report_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json": _safe_rel(json_path),
        "report": _safe_rel(report_path),
    }


def render_html(records: list[dict[str, Any]], *, run_dir: Path, candidate_count: int) -> str:
    items = []
    for record in records:
        items.append(
            "<li>"
            f"<code>{html.escape(record['candidate'])}</code> "
            f"score=<code>{html.escape(str(record.get('score')))}</code> "
            f"lines=<code>{html.escape(str(record.get('line_count')))}</code>"
            "</li>"
        )

    return (
        '<section class="dashboard-card research-archive-candidate-shortlist" '
        'data-link-card="research-archive-candidate-shortlist" data-link-destructive="false">'
        "<h2>Research archive candidate shortlist</h2>"
        "<p>Status: <strong>ok</strong></p>"
        f"<p>Run: <code>{html.escape(_safe_rel(run_dir))}</code></p>"
        f"<p>Candidates: <code>{candidate_count}</code>; Shortlist: <code>{len(records)}</code></p>"
        "<ul>"
        + "\n".join(items)
        + "</ul></section>"
    )


def build_research_archive_candidate_shortlist_response(
    intake_dir: Path = DEFAULT_INTAKE_DIR,
    *,
    limit: int = 25,
    preview_limit: int = 1200,
    write_outputs: bool = True,
    json_requested: bool = False,
) -> dict[str, Any]:
    run_dir = find_latest_run(intake_dir)
    if run_dir is None:
        return {
            "ok": False,
            "status": "error",
            "kind": "research_archive_candidate_shortlist_exporter",
            "marker": MARKER,
            "error": f"No latest research intake run found in {intake_dir}",
            "json_requested": json_requested,
            "non_destructive": True,
        }

    records, candidate_count = build_shortlist_records(
        run_dir,
        limit=limit,
        preview_limit=preview_limit,
    )

    outputs: dict[str, str] = {}
    if write_outputs:
        outputs = write_shortlist_outputs(run_dir, records, candidate_count)

    return {
        "ok": True,
        "status": "ok",
        "kind": "research_archive_candidate_shortlist_exporter",
        "marker": MARKER,
        "matched": True,
        "non_destructive": True,
        "json_requested": json_requested,
        "intake_dir": _safe_rel(intake_dir),
        "latest_run": _safe_rel(run_dir),
        "candidate_count": candidate_count,
        "shortlist_count": len(records),
        "paths": outputs,
        "records": records,
        "html": render_html(records, run_dir=run_dir, candidate_count=candidate_count),
    }


def _write_self_test_intake(base: Path) -> Path:
    run_dir = base / "research-mining-shortlist-test"
    extracted = run_dir / "extracted"

    files = {
        "Research/Research/src/screens/REPL.tsx": "export const repl = true;\nagent guard context\n",
        "Research/Research/src/main.tsx": "export const main = true;\nagent context budget\n",
        "Research/Research/src/missing.ts": "",
    }

    for rel, text in files.items():
        if "missing" in rel:
            continue
        path = extracted / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    run_dir.mkdir(parents=True, exist_ok=True)
    (base / LATEST_NAME).write_text(run_dir.name + "\n", encoding="utf-8")
    (run_dir / CANDIDATE_FILES_NAME).write_text(
        "\n".join(files.keys()) + "\n",
        encoding="utf-8",
    )
    (run_dir / DIRECTORY_MAP_NAME).write_text(
        "\n".join(
            [
                "# Research intake directory map",
                "",
                "## Top candidate files",
                "- score `870` `Research/Research/src/screens/REPL.tsx` — todo:5, agent:211, workflow:1, route:5, guard:51",
                "- score `803` `Research/Research/src/main.tsx` — upgrade:3, todo:3, agent:306, context:82",
                "- score `111` `Research/Research/src/missing.ts` — agent:1",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    return run_dir



def validate_research_candidate_shortlist_exporter(*args: Any, **kwargs: Any) -> list[str]:
    """Healthcheck validator for LU53.

    Keep this quiet and return failures so link_healthcheck.py can decide how
    to report status.
    """
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_archive_candidate_shortlist_response(
            intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )

        records = response.get("records", [])

        if not response.get("ok"):
            failures.append("response should be ok")
        if response.get("candidate_count") != 3:
            failures.append(f"candidate_count should be 3, got {response.get('candidate_count')}")
        if response.get("shortlist_count") != 2:
            failures.append(f"shortlist_count should be 2, got {response.get('shortlist_count')}")
        if len(records) != 2:
            failures.append(f"shortlist should contain two records, got {len(records)}")
        if records and records[0].get("score") != 870:
            failures.append(f"first candidate score mismatch: {records[0].get('score')}")
        if records and records[0].get("keyword_counts", {}).get("agent") != 211:
            failures.append(f"first candidate keyword counts missing: {records[0].get('keyword_counts')}")
        if records and "repl" not in records[0].get("preview", ""):
            failures.append("first preview missing source content")

        paths = response.get("paths", {})
        for label in ("json", "report"):
            rel = paths.get(label)
            if not rel:
                failures.append(f"{label} output path missing")
                continue

            out_path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
            if not out_path.exists():
                failures.append(f"{label} output path missing on disk: {rel}")

    return failures


def self_test() -> bool:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        _write_self_test_intake(intake_dir)

        response = build_research_archive_candidate_shortlist_response(
            intake_dir,
            limit=2,
            preview_limit=200,
            write_outputs=True,
            json_requested=True,
        )

        records = response.get("records", [])

        if not response.get("ok"):
            failures.append("response should be ok")
        if response.get("candidate_count") != 3:
            failures.append(f"candidate_count should be 3, got {response.get('candidate_count')}")
        if response.get("shortlist_count") != 2:
            failures.append(f"shortlist_count should be 2, got {response.get('shortlist_count')}")
        if len(records) != 2:
            failures.append(f"shortlist should contain two records, got {len(records)}")
        if records and records[0].get("score") != 870:
            failures.append(f"first candidate score mismatch: {records[0].get('score')}")
        if records and records[0].get("keyword_counts", {}).get("agent") != 211:
            failures.append(f"first candidate keyword counts missing: {records[0].get('keyword_counts')}")
        if records and "repl" not in records[0].get("preview", ""):
            failures.append("first preview missing source content")

        paths = response.get("paths", {})
        for label in ("json", "report"):
            rel = paths.get(label)
            if not rel:
                failures.append(f"{label} output path missing")
                continue
            out_path = ROOT / rel if not Path(rel).is_absolute() else Path(rel)
            if not out_path.exists():
                failures.append(f"{label} output path missing on disk: {rel}")

    if failures:
        print("research archive candidate shortlist exporter FAILED")
        for failure in failures:
            print(f"- {failure}")
        return False

    print(MARKER)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Export research archive candidate shortlist.")
    parser.add_argument("--intake-dir", default=str(DEFAULT_INTAKE_DIR))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--preview-limit", type=int, default=1200)
    parser.add_argument("--json", action="store_true", dest="json_requested")
    parser.add_argument("--no-write", action="store_true")
    parser.add_argument("--self-test", action="store_true")

    args = parser.parse_args()

    if args.self_test:
        return 0 if self_test() else 1

    response = build_research_archive_candidate_shortlist_response(
        Path(args.intake_dir),
        limit=args.limit,
        preview_limit=args.preview_limit,
        write_outputs=not args.no_write,
        json_requested=args.json_requested,
    )

    if args.json_requested:
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(MARKER if response.get("ok") else response.get("error", "error"))

    return 0 if response.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
