#!/usr/bin/env python3
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_INTAKE_DIR = ROOT / ".link_research_intake"
LATEST_NAME = "LATEST_RUN.txt"
REPORT_NAME = "REPORT.md"
JSON_NAME = "research_mining_result.json"
AGENT_JOBS_NAME = "agent_jobs.json"
DIRECTORY_MAP_NAME = "DIRECTORY_MAP.md"
CANDIDATE_FILES_NAME = "candidate_files.txt"

MARKER = "research archive intake miner web admin route OK"

RESEARCH_ARCHIVE_INTAKE_TRIGGERS = (
    "research archive intake",
    "show research archive intake",
    "latest research archive intake",
    "research archive miner",
    "research archive mining",
    "research mining report",
    "research intake report",
    "show research intake",
    "show latest research mining",
)


def wants_json(prompt: str) -> bool:
    text = f" {(prompt or '').lower()} "
    return "--json" in text or " json " in text or "as json" in text


def matches_research_archive_intake_prompt(prompt: str) -> bool:
    lowered = " ".join((prompt or "").lower().split())
    return any(trigger in lowered for trigger in RESEARCH_ARCHIVE_INTAKE_TRIGGERS)


def _read_text_limited(path: Path, limit: int = 12_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + "\n\n... truncated ..."


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _safe_run_dir_from_latest(intake_dir: Path) -> Path | None:
    latest_path = intake_dir / LATEST_NAME
    if not latest_path.exists():
        return None

    raw = latest_path.read_text(encoding="utf-8", errors="replace").strip()
    if not raw:
        return None

    candidate = intake_dir / raw
    intake_resolved = intake_dir.resolve(strict=False)
    candidate_resolved = candidate.resolve(strict=False)

    try:
        candidate_resolved.relative_to(intake_resolved)
    except ValueError:
        return None

    if candidate.exists() and candidate.is_dir():
        return candidate

    return None


def _latest_run_dir(intake_dir: Path) -> Path | None:
    direct = _safe_run_dir_from_latest(intake_dir)
    if direct is not None:
        return direct

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


def _rel(path: Path) -> str:
    try:
        return str(path.resolve(strict=False).relative_to(ROOT.resolve(strict=False)))
    except Exception:
        return str(path)


def _file_entry(run_dir: Path, name: str) -> dict[str, Any]:
    path = run_dir / name
    exists = path.exists() and path.is_file()
    return {
        "name": name,
        "exists": exists,
        "path": _rel(path),
        "size_bytes": path.stat().st_size if exists else 0,
    }


def _line_count(path: Path) -> int:
    if not path.exists() or not path.is_file():
        return 0
    try:
        return sum(1 for _ in path.open("r", encoding="utf-8", errors="replace"))
    except Exception:
        return 0


def _summarize_result(result: dict[str, Any]) -> dict[str, Any]:
    sources = result.get("sources")
    findings = result.get("findings")
    jobs = result.get("agent_jobs", result.get("jobs"))

    source_list = sources if isinstance(sources, list) else []
    finding_list = findings if isinstance(findings, list) else []
    job_list = jobs if isinstance(jobs, list) else []

    extracted_total = 0
    skipped_total = 0
    for source in source_list:
        if not isinstance(source, dict):
            continue
        extracted_total += int(source.get("extracted_count") or 0)
        skipped_total += int(source.get("skipped_count") or 0)

    return {
        "status": result.get("status") or ("ok" if result else "missing_result_json"),
        "created_at": result.get("created_at"),
        "marker": result.get("marker"),
        "source_count": len(source_list),
        "finding_count": len(finding_list),
        "agent_job_count": len(job_list),
        "extracted_count": extracted_total,
        "skipped_count": skipped_total,
        "inputs": result.get("inputs") if isinstance(result.get("inputs"), list) else [],
    }


def _directory_map_preview(run_dir: Path) -> str:
    path = run_dir / DIRECTORY_MAP_NAME
    if not path.exists():
        return ""
    text = _read_text_limited(path, limit=9_000)
    lines = text.splitlines()
    return "\n".join(lines[:120])


def build_research_archive_intake_web_admin_response(
    prompt: str,
    intake_dir: Path | None = None,
) -> dict[str, Any]:
    selected_intake_dir = intake_dir or DEFAULT_INTAKE_DIR
    matched = matches_research_archive_intake_prompt(prompt)
    run_dir = _latest_run_dir(selected_intake_dir)

    result: dict[str, Any] = {}
    if run_dir is not None:
        result = _load_json(run_dir / JSON_NAME)

    summary = _summarize_result(result)
    files: list[dict[str, Any]] = []
    if run_dir is not None:
        files = [
            _file_entry(run_dir, REPORT_NAME),
            _file_entry(run_dir, JSON_NAME),
            _file_entry(run_dir, AGENT_JOBS_NAME),
            _file_entry(run_dir, DIRECTORY_MAP_NAME),
            _file_entry(run_dir, CANDIDATE_FILES_NAME),
        ]
        summary["candidate_file_count"] = _line_count(run_dir / CANDIDATE_FILES_NAME)

    directory_map_preview = _directory_map_preview(run_dir) if run_dir is not None else ""

    payload = {
        "ok": True,
        "kind": "research_archive_intake_web_admin",
        "matched": matched,
        "json_requested": wants_json(prompt),
        "non_destructive": True,
        "data_link_card": "research-archive-intake",
        "intake_dir": _rel(selected_intake_dir),
        "latest_run": _rel(run_dir) if run_dir is not None else None,
        "status": summary.get("status") if run_dir is not None else "missing_latest_run",
        "summary": summary,
        "files": files,
        "directory_map_preview": directory_map_preview,
        "command": ["python3", "link_research_archive_intake_web_admin.py", "--json"],
    }

    payload["html"] = render_research_archive_intake_web_admin_response(payload)
    return payload


def render_research_archive_intake_web_admin_response(payload: dict[str, Any]) -> str:
    status = html.escape(str(payload.get("status") or "unknown"))
    latest_run = html.escape(str(payload.get("latest_run") or "No latest run found"))
    intake_dir = html.escape(str(payload.get("intake_dir") or DEFAULT_INTAKE_DIR))
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    file_items = []
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    for entry in files:
        if not isinstance(entry, dict):
            continue
        exists = "present" if entry.get("exists") else "missing"
        file_items.append(
            "<li>"
            f"<code>{esc(entry.get('path'))}</code> — {exists}, "
            f"{esc(entry.get('size_bytes'))} bytes"
            "</li>"
        )

    file_html = "\n".join(file_items) if file_items else "<li>No run files available.</li>"

    preview = str(payload.get("directory_map_preview") or "")
    preview_html = (
        "<h3>Directory map preview</h3>"
        f"<pre>{html.escape(preview)}</pre>"
        if preview
        else "<p>No directory map preview available.</p>"
    )

    return (
        '<section class="dashboard-card research-archive-intake-web-admin" '
        'data-link-card="research-archive-intake" '
        'data-link-destructive="false">'
        "<h2>Research archive intake miner</h2>"
        f"<p>Status: <strong>{status}</strong></p>"
        f"<p>Intake dir: <code>{intake_dir}</code></p>"
        f"<p>Latest run: <code>{latest_run}</code></p>"
        "<ul>"
        f"<li>Created: <code>{esc(summary.get('created_at'))}</code></li>"
        f"<li>Sources: <code>{esc(summary.get('source_count', 0))}</code></li>"
        f"<li>Extracted files: <code>{esc(summary.get('extracted_count', 0))}</code></li>"
        f"<li>Findings: <code>{esc(summary.get('finding_count', 0))}</code></li>"
        f"<li>Agent jobs: <code>{esc(summary.get('agent_job_count', 0))}</code></li>"
        f"<li>Candidate files: <code>{esc(summary.get('candidate_file_count', 0))}</code></li>"
        "</ul>"
        "<h3>Run files</h3>"
        f"<ul>{file_html}</ul>"
        f"{preview_html}"
        "</section>"
    )


def route_research_archive_intake_prompt(
    prompt: str,
    intake_dir: Path | None = None,
) -> list[str] | None:
    if not matches_research_archive_intake_prompt(prompt):
        return None

    response = build_research_archive_intake_web_admin_response(prompt, intake_dir)
    if wants_json(prompt):
        return [json.dumps(response, indent=2, sort_keys=True)]

    return [str(response.get("html") or "")]


def validate_research_archive_intake_web_admin_route() -> list[str]:
    problems: list[str] = []

    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        intake_dir = Path(tmp) / ".link_research_intake"
        run_dir = intake_dir / "research-mining-test"
        run_dir.mkdir(parents=True)
        (intake_dir / LATEST_NAME).write_text("research-mining-test", encoding="utf-8")

        mining_result = {
            "kind": "link_research_archive_mining_result",
            "marker": "research archive intake miner OK",
            "status": "ok",
            "ok": True,
            "created_at": "2026-05-24T00:00:00+00:00",
            "sources": [{"type": "zip", "source": "research/Research.zip", "extracted_count": 3, "skipped_count": 0}],
            "findings": [],
            "agent_jobs": [],
            "inputs": ["research/Research.zip"],
        }

        (run_dir / JSON_NAME).write_text(json.dumps(mining_result), encoding="utf-8")
        (run_dir / REPORT_NAME).write_text("# Link research archive mining report\n", encoding="utf-8")
        (run_dir / AGENT_JOBS_NAME).write_text("[]\n", encoding="utf-8")
        (run_dir / DIRECTORY_MAP_NAME).write_text(
            "# Research intake directory map\n\n- Total files: `3`\n",
            encoding="utf-8",
        )
        (run_dir / CANDIDATE_FILES_NAME).write_text(
            "Research/Research/src/screens/REPL.tsx\n",
            encoding="utf-8",
        )

        prompt = "show research archive intake json"
        response = build_research_archive_intake_web_admin_response(prompt, intake_dir)

        if not response.get("ok"):
            problems.append("response should be ok")
        if not response.get("matched"):
            problems.append("response should be matched")
        if not response.get("json_requested"):
            problems.append("response should detect json request")
        if not response.get("non_destructive"):
            problems.append("response should be non-destructive")
        if response.get("status") != "ok":
            problems.append("response should report ok status")

        summary = response.get("summary")
        if not isinstance(summary, dict):
            problems.append("summary missing")
        else:
            if summary.get("extracted_count") != 3:
                problems.append("summary extracted_count mismatch")
            if summary.get("candidate_file_count") != 1:
                problems.append("summary candidate_file_count mismatch")

        rendered = str(response.get("html") or "")
        if "Research archive intake miner" not in rendered:
            problems.append("HTML missing title")
        if "research-archive-intake" not in rendered:
            problems.append("HTML missing data-link-card marker")
        if "data-link-destructive=\"false\"" not in rendered:
            problems.append("HTML missing non-destructive marker")

        routed = route_research_archive_intake_prompt(prompt, intake_dir)
        if not routed:
            problems.append("route returned no output for matching prompt")
        else:
            try:
                routed_payload = json.loads(routed[0])
            except Exception as exc:
                problems.append(f"json route output was not valid json: {exc}")
            else:
                if routed_payload.get("kind") != "research_archive_intake_web_admin":
                    problems.append("json route output kind mismatch")

        nonmatch = route_research_archive_intake_prompt("show recovery dashboard", intake_dir)
        if nonmatch is not None:
            problems.append("route should ignore unrelated prompts")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description="Research archive intake miner web admin route.")
    parser.add_argument("prompt", nargs="*", default=[])
    parser.add_argument("--intake-dir")
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        problems = validate_research_archive_intake_web_admin_route()
        if problems:
            print("research archive intake miner web admin route FAILED")
            for problem in problems:
                print(f"- {problem}")
            return 1
        print(MARKER)
        return 0

    prompt = " ".join(args.prompt) if args.prompt else "show research archive intake"
    if args.json and " json" not in f" {prompt.lower()} ":
        prompt = f"{prompt} json"

    response = build_research_archive_intake_web_admin_response(
        prompt,
        Path(args.intake_dir) if args.intake_dir else None,
    )

    if wants_json(prompt):
        print(json.dumps(response, indent=2, sort_keys=True))
    else:
        print(response.get("html", ""))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
