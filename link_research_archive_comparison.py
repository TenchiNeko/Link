#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import zipfile
from pathlib import Path
from typing import Any


RESEARCH_ARCHIVE_COMPARISON_VERSION = "LU104R-research-archive-comparison-v1"

TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".toml",
    ".js", ".ts", ".tsx", ".jsx", ".sh", ".rs", ".go", ".java", ".cpp",
    ".c", ".h", ".html", ".css", ".ini", ".cfg", ".env", ".example",
}

KEYWORD_GROUPS: dict[str, list[str]] = {
    "autonomous_agent": [
        "agent", "autonomous", "planner", "executor", "tool use", "tool_use",
        "workflow", "task runner", "delegate", "multi-agent", "swarm", "crew",
        "auto-gpt", "autogpt", "babyagi",
    ],
    "self_learning": [
        "self-learning", "self learning", "learn from", "reflection", "reflect",
        "self improve", "self-improve", "feedback loop", "experience", "lessons",
        "reinforcement", "rlhf", "dpo", "fine-tune", "finetune", "training loop",
        "curriculum", "evolve", "growth",
    ],
    "persistence_memory": [
        "memory", "long-term memory", "vector", "embedding", "sqlite", "database",
        "journal", "receipt", "queue", "state", "checkpoint", "knowledge base",
    ],
    "autonomous_runtime": [
        "daemon", "scheduler", "cron", "tick", "watcher", "background",
        "loop", "interval", "without prompt", "unprompted", "self act",
        "self-act", "autostart",
    ],
    "safety_gating": [
        "approval", "human approval", "guard", "sandbox", "deny", "allowlist",
        "policy", "permission", "capability", "rollback", "dry run",
    ],
}


def compact(value: Any, limit: int = 220) -> str:
    text = str(value or "").replace("\x00", " ").strip()
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def is_text_entry(name: str) -> bool:
    path = Path(name)
    if path.name.startswith("."):
        return False
    if "__pycache__" in path.parts:
        return False
    return path.suffix.lower() in TEXT_EXTENSIONS or path.name.lower() in {
        "readme", "license", "dockerfile", "makefile",
    }


def decode_bytes(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return data.decode(enc, errors="replace")
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def term_snippet(text: str, term: str, limit: int = 260) -> str:
    lower = text.lower()
    idx = lower.find(term.lower())
    if idx < 0:
        return ""
    start = max(0, idx - limit // 2)
    end = min(len(text), idx + len(term) + limit // 2)
    return compact(text[start:end], limit=limit)


def classify_archive(counts: dict[str, int]) -> dict[str, str]:
    autonomous = counts.get("autonomous_agent", 0)
    learning = counts.get("self_learning", 0)
    memory = counts.get("persistence_memory", 0)
    runtime = counts.get("autonomous_runtime", 0)
    safety = counts.get("safety_gating", 0)

    if autonomous >= 5 and learning >= 3 and (runtime >= 2 or memory >= 3):
        label = "strong evidence of autonomous/self-learning agent tech"
        confidence = "high"
    elif autonomous >= 4 and (runtime >= 2 or memory >= 3):
        label = "autonomous-agent related; self-learning not yet proven"
        confidence = "medium"
    elif learning >= 3 and memory >= 2:
        label = "learning/memory related; autonomous action unclear"
        confidence = "medium"
    elif autonomous >= 2 or learning >= 2 or memory >= 3:
        label = "related AI/agent infrastructure; self-learning unclear"
        confidence = "low-medium"
    else:
        label = "no strong static evidence of self-learning autonomous agents"
        confidence = "low"

    if safety >= 3:
        boundary = "contains visible safety/approval gating language"
    else:
        boundary = "safety/approval gating not strongly visible in static scan"

    return {"label": label, "confidence": confidence, "boundary": boundary}


def analyze_archive(path: Path, max_files: int = 450, max_bytes_per_file: int = 100_000) -> dict[str, Any]:
    result: dict[str, Any] = {
        "archive": str(path),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
        "error": "",
        "total_entries": 0,
        "text_entries_scanned": 0,
        "top_level_dirs": [],
        "counts": {group: 0 for group in KEYWORD_GROUPS},
        "evidence": [],
        "classification": {},
    }

    if not path.exists():
        result["error"] = "archive missing"
        result["classification"] = classify_archive(result["counts"])
        return result

    try:
        with zipfile.ZipFile(path) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir()]
            result["total_entries"] = len(infos)

            top_dirs: dict[str, int] = {}
            for info in infos:
                first = Path(info.filename).parts[0] if Path(info.filename).parts else info.filename
                top_dirs[first] = top_dirs.get(first, 0) + 1
            result["top_level_dirs"] = [
                {"name": k, "count": v}
                for k, v in sorted(top_dirs.items(), key=lambda kv: (-kv[1], kv[0]))[:12]
            ]

            scanned = 0
            for info in infos:
                if scanned >= max_files:
                    break
                name = info.filename
                lower_name = name.lower()

                path_hits: dict[str, list[str]] = {}
                for group, terms in KEYWORD_GROUPS.items():
                    hits = [term for term in terms if term in lower_name]
                    if hits:
                        path_hits[group] = hits

                text = ""
                if is_text_entry(name) and info.file_size <= max_bytes_per_file * 3:
                    try:
                        with zf.open(info) as f:
                            text = decode_bytes(f.read(max_bytes_per_file))
                        scanned += 1
                    except Exception:
                        text = ""

                lower_text = text.lower()
                for group, terms in KEYWORD_GROUPS.items():
                    hits = list(path_hits.get(group, []))
                    for term in terms:
                        if term in lower_text and term not in hits:
                            hits.append(term)
                    if not hits:
                        continue

                    result["counts"][group] += len(hits)
                    if len(result["evidence"]) < 80:
                        snippet = ""
                        if text:
                            snippet = term_snippet(text, hits[0])
                        result["evidence"].append({
                            "file": name,
                            "group": group,
                            "terms": hits[:8],
                            "snippet": snippet,
                        })

            result["text_entries_scanned"] = scanned
            result["classification"] = classify_archive(result["counts"])
    except Exception as exc:
        result["error"] = str(exc)
        result["classification"] = classify_archive(result["counts"])

    return result


def default_archives(root: Path) -> list[Path]:
    research = root / "research"
    preferred = [
        research / "Research.zip",
        research / "agent_research.zip",
        research / "RuVector-main.zip",
    ]
    seen: set[Path] = set()
    paths: list[Path] = []
    for path in preferred + sorted(research.glob("*.zip")):
        if path not in seen:
            paths.append(path)
            seen.add(path)
    return paths


def compare_archives(archives: list[Path] | None = None, root: Path | None = None) -> dict[str, Any]:
    repo = root or Path.cwd()
    paths = archives or default_archives(repo)
    analyses = [analyze_archive(path) for path in paths]
    return {
        "receipt_version": RESEARCH_ARCHIVE_COMPARISON_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(repo),
        "archives": analyses,
        "answer": summarize_answer(analyses),
        "static_scan_limit": "Static scan only: evidence can show likely architecture, but cannot prove runtime autonomy without executing/reviewing code paths.",
    }


def summarize_answer(analyses: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in analyses:
        name = Path(item["archive"]).name
        label = item.get("classification", {}).get("label", "unknown")
        confidence = item.get("classification", {}).get("confidence", "unknown")
        if not item.get("exists"):
            lines.append(f"{name}: missing, not reviewed.")
        elif item.get("error"):
            lines.append(f"{name}: could not fully review: {item['error']}")
        else:
            lines.append(f"{name}: {label} confidence={confidence}.")
    return lines


def validate_comparison(report: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if report.get("receipt_version") != RESEARCH_ARCHIVE_COMPARISON_VERSION:
        problems.append("receipt version mismatch")
    if not isinstance(report.get("archives"), list):
        problems.append("archives must be a list")
    for item in report.get("archives", []):
        if "archive" not in item:
            problems.append("archive item missing archive path")
        if "counts" not in item:
            problems.append(f"{item.get('archive', '<unknown>')} missing counts")
        if "classification" not in item:
            problems.append(f"{item.get('archive', '<unknown>')} missing classification")
    return problems


def render_markdown(report: dict[str, Any]) -> str:
    out: list[str] = []
    out.append("# Link Research Archive Comparison")
    out.append("")
    out.append(f"Version: `{report['receipt_version']}`")
    out.append(f"Generated: {report['generated']}")
    out.append("")
    out.append("## Answer")
    out.append("")
    for line in report.get("answer", []):
        out.append(f"- {line}")
    out.append("")
    out.append("## Important Limit")
    out.append("")
    out.append(f"- {report.get('static_scan_limit')}")
    out.append("")

    for item in report.get("archives", []):
        name = Path(item["archive"]).name
        cls = item.get("classification", {})
        out.append(f"## {name}")
        out.append("")
        out.append(f"- Exists: **{item.get('exists')}**")
        out.append(f"- Size: `{item.get('size_bytes')}` bytes")
        out.append(f"- Entries: **{item.get('total_entries')}**")
        out.append(f"- Text files scanned: **{item.get('text_entries_scanned')}**")
        if item.get("error"):
            out.append(f"- Error: `{item.get('error')}`")
        out.append(f"- Classification: **{cls.get('label', 'unknown')}**")
        out.append(f"- Confidence: **{cls.get('confidence', 'unknown')}**")
        out.append(f"- Safety boundary: {cls.get('boundary', 'unknown')}")
        out.append("")
        out.append("### Evidence Counts")
        out.append("")
        for group, count in item.get("counts", {}).items():
            out.append(f"- `{group}`: **{count}**")
        out.append("")
        out.append("### Top Folders")
        out.append("")
        for folder in item.get("top_level_dirs", [])[:8]:
            out.append(f"- `{folder['name']}` — {folder['count']} files")
        out.append("")
        out.append("### Sample Evidence")
        out.append("")
        evidence = item.get("evidence", [])[:10]
        if not evidence:
            out.append("- No keyword evidence found in scanned text/path sample.")
        for ev in evidence:
            terms = ", ".join(f"`{term}`" for term in ev.get("terms", [])[:6])
            out.append(f"- `{ev.get('file')}` — {ev.get('group')} — {terms}")
            if ev.get("snippet"):
                out.append(f"  - {ev.get('snippet')}")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_html(report: dict[str, Any]) -> str:
    md = render_markdown(report)
    return (
        f'<section class="link-research-archive-comparison" '
        f'data-version="{html.escape(report["receipt_version"])}">'
        "<h2>Link Research Archive Comparison</h2>"
        f"<pre>{html.escape(md)}</pre>"
        "</section>"
    )


def write_report(report: dict[str, Any], root: Path) -> Path:
    out_dir = root / ".link" / "research_reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    path = out_dir / f"{stamp}-research-archive-comparison.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare research archives for autonomous/self-learning agent evidence.")
    parser.add_argument("--archives", nargs="*", default=[], help="Zip archives to inspect. Defaults to research/*.zip.")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--write", action="store_true", help="Write JSON report under .link/research_reports.")
    args = parser.parse_args()

    root = Path.cwd()
    archives = [Path(p) for p in args.archives] if args.archives else default_archives(root)
    report = compare_archives(archives=archives, root=root)
    problems = validate_comparison(report)
    if problems:
        report["validation_problems"] = problems

    if args.write:
        report["written_path"] = str(write_report(report, root))

    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(report))
    else:
        print(render_markdown(report))
        if args.write:
            print(f"Written: `{report['written_path']}`")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
