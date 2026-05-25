#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
from pathlib import Path
from typing import Any


AUTONOMOUS_RESEARCH_REFLECTION_VERSION = "LU105-autonomous-research-reflection-v1"


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def latest_json(root: Path, folder: str) -> Path | None:
    base = root / folder
    if not base.exists():
        return None
    files = sorted(base.glob("*.json"))
    return files[-1] if files else None


def load_json(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"load_error": str(exc), "path": str(path)}


def archive_name(item: dict[str, Any]) -> str:
    return str(item.get("archive") or item.get("name") or item.get("path") or "unknown")


def evidence_counts(item: dict[str, Any]) -> dict[str, int]:
    raw = item.get("evidence_counts") or item.get("counts") or {}
    if not isinstance(raw, dict):
        return {}
    out: dict[str, int] = {}
    for key, value in raw.items():
        try:
            out[str(key)] = int(value)
        except Exception:
            pass
    return out


def classify_archive(item: dict[str, Any]) -> dict[str, Any]:
    name = archive_name(item)
    counts = evidence_counts(item)
    lower = name.lower()

    agent = counts.get("autonomous_agent", 0)
    learning = counts.get("self_learning", 0)
    memory = counts.get("persistence_memory", 0)
    runtime = counts.get("autonomous_runtime", 0)
    safety = counts.get("safety_gating", 0)

    verdict = "unknown"
    confidence = "low"
    import_value = "review manually"
    caveats: list[str] = []

    if "hermes" in lower or "agent_research" in lower:
        verdict = "agent framework candidate"
        confidence = "high"
        import_value = "study agent core, tool registry, memory, skills, and guard patterns"
    elif "ruvector" in lower:
        verdict = "memory/vector infrastructure candidate"
        confidence = "medium"
        import_value = "study vector storage/search and .claude agent config patterns, not as proof of self-learning runtime"
        caveats.append("Previous keyword scan likely over-classified this as self-learning because vector/memory and .claude agent configs inflate matches.")
    elif "research.zip" in lower or name == "Research.zip":
        verdict = "Claude-style agent/tooling reference"
        confidence = "medium"
        import_value = "study permission, tool-use, background-agent, memory include, and workflow patterns"
        caveats.append("Static evidence shows agent infrastructure; it does not prove actual autonomous self-learning.")

    if learning > 0 and runtime > 0 and memory > 0:
        caveats.append("Self-learning keywords exist, but must be separated from model training, reflection notes, and product growth flags.")
    if safety > 0:
        caveats.append("Contains useful safety/approval-gating patterns.")

    return {
        "archive": name,
        "verdict": verdict,
        "confidence": confidence,
        "import_value": import_value,
        "counts": counts,
        "caveats": caveats,
    }


def extract_archives(report: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(report.get("archives"), list):
        return [x for x in report["archives"] if isinstance(x, dict)]

    candidates: list[dict[str, Any]] = []
    for key, value in report.items():
        if isinstance(value, dict) and key.lower().endswith(".zip"):
            copy = dict(value)
            copy.setdefault("archive", key)
            candidates.append(copy)
    return candidates


def build_reflection(root: Path, goal: str, write: bool = False) -> dict[str, Any]:
    report_path = latest_json(root, ".link/research_reports")
    report = load_json(report_path)
    archives = extract_archives(report)

    reflected = [classify_archive(item) for item in archives]

    if not reflected:
        reflected = [
            {
                "archive": "Research.zip",
                "verdict": "needs deeper inspection",
                "confidence": "low",
                "import_value": "run LU104R first or verify research report schema",
                "counts": {},
                "caveats": ["No archive entries found in latest research report."],
            }
        ]

    recommendations = [
        {
            "id": "LU106",
            "title": "Autonomous tick runner",
            "why": "Lets Link consume the local queue and generate receipts without Brandon manually running every planning command.",
            "boundary": "May inspect and write .link runtime receipts; source edits and commits remain approval-gated.",
            "priority": 100,
        },
        {
            "id": "LU106A",
            "title": "Queue command backfill",
            "why": "Pending task JSON showed command=None, which would weaken the future tick runner.",
            "boundary": "Local queue metadata only; no source edits unless separately approved.",
            "priority": 98,
        },
        {
            "id": "LU106R",
            "title": "Deep archive classifier",
            "why": "Separates agent framework, vector memory, autonomous runtime, reflection, and actual training loops.",
            "boundary": "Static read-only research classification first.",
            "priority": 95,
        },
    ]

    reflection = {
        "receipt_version": AUTONOMOUS_RESEARCH_REFLECTION_VERSION,
        "generated": now(),
        "goal": goal,
        "source_report": str(report_path) if report_path else None,
        "summary": {
            "Research.zip": "Likely Claude-style agent/tooling reference; not proven self-learning runtime.",
            "agent_research.zip": "Strongest agent-framework candidate; useful for agent core, tools, skills, memory, and guards.",
            "RuVector-main.zip": "Likely vector/memory infrastructure plus .claude agent configs; useful, but not proof of self-learning agent runtime.",
        },
        "reflections": reflected,
        "next_recommendations": recommendations,
        "autonomy_boundary": [
            "Link may inspect, summarize, rank, and write local .link receipts without approval.",
            "Link must wait for approval before source edits, commits, pushes, or destructive commands.",
            "Future autonomous ticks should be local-first and receipt-backed.",
        ],
        "written": None,
    }

    if write:
        outdir = root / ".link" / "research_reflections"
        outdir.mkdir(parents=True, exist_ok=True)
        out = outdir / (dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-autonomous-research-reflection.json")
        out.write_text(json.dumps(reflection, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        reflection["written"] = str(out)

    return reflection


def render_markdown(reflection: dict[str, Any]) -> str:
    lines = [
        "# Link Autonomous Research Reflection",
        "",
        f"Version: `{reflection.get('receipt_version')}`",
        f"Generated: {reflection.get('generated')}",
        f"Goal: {reflection.get('goal')}",
        f"Source report: `{reflection.get('source_report')}`",
        "",
        "## Corrected Read",
        "",
    ]

    for name, text in (reflection.get("summary") or {}).items():
        lines.append(f"- `{name}`: {text}")

    lines += ["", "## Archive Reflections", ""]

    for item in reflection.get("reflections") or []:
        lines += [
            f"### {item.get('archive')}",
            "",
            f"- Verdict: **{item.get('verdict')}**",
            f"- Confidence: **{item.get('confidence')}**",
            f"- Import value: {item.get('import_value')}",
        ]
        counts = item.get("counts") or {}
        if counts:
            lines.append("- Evidence counts: " + ", ".join(f"`{k}`={v}" for k, v in sorted(counts.items())))
        caveats = item.get("caveats") or []
        if caveats:
            lines.append("- Caveats:")
            for caveat in caveats:
                lines.append(f"  - {caveat}")
        lines.append("")

    lines += ["## Next Recommendations", ""]
    for rec in reflection.get("next_recommendations") or []:
        lines += [
            f"- `{rec.get('id')}` — **{rec.get('title')}** — priority {rec.get('priority')}",
            f"  - Why: {rec.get('why')}",
            f"  - Boundary: {rec.get('boundary')}",
        ]

    lines += ["", "## Autonomy Boundary", ""]
    for item in reflection.get("autonomy_boundary") or []:
        lines.append(f"- {item}")

    if reflection.get("written"):
        lines += ["", f"Written: `{reflection.get('written')}`"]

    return "\n".join(lines)


def render_html(reflection: dict[str, Any]) -> str:
    return (
        f'<section class="link-autonomous-research-reflection" '
        f'data-version="{html.escape(str(reflection.get("receipt_version", "")))}">'
        "<h2>Link Autonomous Research Reflection</h2>"
        f"<pre>{html.escape(render_markdown(reflection))}</pre>"
        "</section>"
    )


def validate_autonomous_research_reflection(root: Path | None = None) -> list[str]:
    root = root or Path.cwd()
    problems: list[str] = []
    reflection = build_reflection(root, "healthcheck autonomous research reflection", write=False)
    rendered = render_html(reflection)

    if reflection.get("receipt_version") != AUTONOMOUS_RESEARCH_REFLECTION_VERSION:
        problems.append("version mismatch")
    if "link-autonomous-research-reflection" not in rendered:
        problems.append("html marker missing")
    if not reflection.get("next_recommendations"):
        problems.append("next recommendations missing")
    if "RuVector-main.zip" not in json.dumps(reflection):
        problems.append("RuVector corrected read missing")
    if reflection.get("written"):
        problems.append("healthcheck should be non-destructive")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", default="Reflect on autonomous research archives")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    reflection = build_reflection(root, args.goal, write=args.write)

    if args.format == "json":
        print(json.dumps(reflection, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_html(reflection))
    else:
        print(render_markdown(reflection))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
