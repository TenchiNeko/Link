#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import tempfile
import zipfile
from pathlib import Path
from typing import Any

VERSION = "LU190-research-upgrade-miner-foundation-v1"

DEFAULT_RESEARCH_DIRS = [
    "research",
    ".link/research",
    ".link/frontier_context",
    ".link/market_context",
]

TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".py", ".json", ".jsonl", ".yaml", ".yml",
    ".toml", ".csv", ".html", ".htm",
}

MAX_FILE_BYTES = 1_500_000
MAX_ZIP_MEMBER_BYTES = 750_000

SKIP_PARTS = {
    ".git", "__pycache__", ".venv", "venv", "node_modules",
    "patch_drafts", "dashboard", "agent_queue", "backups",
}

CLUSTERS: list[dict[str, Any]] = [
    {
        "title": "research evidence index for upgrade proposals",
        "keywords": ["evidence", "citation", "source", "research", "document", "receipt", "trace"],
        "why": "Link needs source-grounded upgrade proposals so agents can cite research files instead of inventing vague maintenance work.",
        "plan": [
            "Index configured research folders and archives into a searchable evidence map.",
            "Record source path, archive member, line number, and snippet for each upgrade-relevant hit.",
            "Attach evidence references to generated approval candidates.",
            "Show evidence paths in receipts so Brandon can verify why a proposal exists.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
    {
        "title": "frontier gap grading rubric",
        "keywords": ["frontier", "swe-bench", "codex", "claude", "devin", "cursor", "benchmark", "grade", "rubric", "market"],
        "why": "A system with an F grade against frontier agents should turn that gap into concrete upgrade proposals instead of reporting no useful work.",
        "plan": [
            "Create a rubric comparing Link against frontier agent capabilities.",
            "Score gaps such as research retrieval, sandboxed implementation, codebase Q&A, task decomposition, evaluation, and rollback.",
            "Use the lowest-scoring categories to prioritize proposal generation.",
            "Store dated market/context notes separately from live source code.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_grade.py", "link_healthcheck.py"],
    },
    {
        "title": "live code versus research gap scanner",
        "keywords": ["missing", "gap", "upgrade", "not in link", "improve", "implementation", "feature", "capability"],
        "why": "Link should compare research ideas against the current codebase and propose upgrades only when the idea is not already implemented.",
        "plan": [
            "Extract capability claims from research documents.",
            "Search live Link source files for matching implementation markers.",
            "Classify each idea as implemented, partial, missing, or blocked.",
            "Generate approval candidates only for missing or partial capabilities.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_healthcheck.py"],
    },
    {
        "title": "research to approval candidate pipeline",
        "keywords": ["proposal", "approval", "candidate", "human", "oversight", "queue", "draft", "yes", "no", "try again"],
        "why": "The approval queue should be fed by real research-derived candidates, not only hardcoded fallback ideas.",
        "plan": [
            "Write mined upgrade ideas into `.link/approval_candidates.jsonl`.",
            "Deduplicate candidates against pending, approved, rejected, retry, and blocked draft history.",
            "Prefer mined candidates before generic maintenance fallbacks.",
            "Keep implementation approval-gated through the existing YES / NO / TRY AGAIN flow.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
    },
    {
        "title": "sandboxed research implementation handoff",
        "keywords": ["sandbox", "worktree", "isolation", "agent", "implementation", "test", "verify", "rollback"],
        "why": "After Brandon approves a research-derived proposal, implementation should happen in an isolated worktree with evidence and rollback safety.",
        "plan": [
            "Create a handoff receipt from approved research proposal to implementation worker.",
            "Run implementation in an isolated worktree or guarded patch path.",
            "Require compile, smoke, healthcheck, and git diff evidence before merge.",
            "Keep source edits blocked until the exact proposal hash is approved.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
    },
    {
        "title": "market context refresh adapter",
        "keywords": ["today", "current", "market", "frontier", "recent", "as of", "latest", "model", "agent"],
        "why": "Link needs a dated context lane for current frontier-agent ideas so stale assumptions do not drive the upgrade roadmap.",
        "plan": [
            "Add a local `.link/market_context/` source folder for dated market/frontier notes.",
            "Require market context notes to include date, source, and summary.",
            "Let the research miner combine local research files with dated market context.",
            "Keep market context read-only unless Brandon explicitly approves updates.",
        ],
        "files": ["link_research_upgrade_miner.py", "link_self_learning_dashboard.py", "link_healthcheck.py"],
    },
]


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def iso_now() -> str:
    return dt.datetime.now().replace(microsecond=0).isoformat()


def norm_title(title: str) -> str:
    text = str(title or "").lower()
    text = re.sub(r"\blu\d+\b", "", text)
    text = re.sub(r"\b\d+\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def rel_path(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except Exception:
        return str(path)


def safe_text(data: bytes) -> str:
    return data.decode("utf-8", errors="ignore").replace("\x00", "")


def should_skip(path: Path) -> bool:
    return any(part in SKIP_PARTS for part in path.parts)


def read_plain_file(path: Path) -> str:
    if path.stat().st_size > MAX_FILE_BYTES:
        return ""
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return ""
    return path.read_text(encoding="utf-8", errors="ignore").replace("\x00", "")


def iter_chunks(root: Path, research_dirs: list[str]) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []

    for item in research_dirs:
        base = (root / item).resolve()
        if not base.exists():
            continue

        paths = [base] if base.is_file() else sorted(base.rglob("*"))
        for path in paths:
            if not path.is_file() or should_skip(path):
                continue

            suffix = path.suffix.lower()

            if suffix == ".zip":
                try:
                    with zipfile.ZipFile(path) as zf:
                        for info in zf.infolist():
                            member_suffix = Path(info.filename).suffix.lower()
                            if info.is_dir() or member_suffix not in TEXT_SUFFIXES:
                                continue
                            if info.file_size > MAX_ZIP_MEMBER_BYTES:
                                continue
                            text = safe_text(zf.read(info))
                            if text.strip():
                                chunks.append({
                                    "source_path": f"{rel_path(root, path)}::{info.filename}",
                                    "text": text,
                                })
                except Exception:
                    continue
                continue

            text = read_plain_file(path)
            if text.strip():
                chunks.append({
                    "source_path": rel_path(root, path),
                    "text": text,
                })

    return chunks


def load_seen_titles(root: Path, candidate_file: Path) -> set[str]:
    seen: set[str] = set()

    for folder in ["pending", "approved", "rejected", "retry", "blocked"]:
        base = root / ".link/patch_drafts" / folder
        if not base.exists():
            continue
        for path in base.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            task = data.get("task") if isinstance(data.get("task"), dict) else {}
            title = data.get("title") or task.get("title")
            if title:
                seen.add(norm_title(str(title)))

    if candidate_file.exists():
        for line in candidate_file.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
            except Exception:
                continue
            title = data.get("title") or (data.get("task") or {}).get("title")
            if title:
                seen.add(norm_title(str(title)))

    return seen


def find_evidence(chunks: list[dict[str, Any]], keywords: list[str], limit: int = 6) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    lowered_keywords = [k.lower() for k in keywords]

    for chunk in chunks:
        lines = chunk["text"].splitlines()
        for idx, line in enumerate(lines, start=1):
            clean = re.sub(r"\s+", " ", line).strip()
            if not clean or len(clean) < 20:
                continue
            lower = clean.lower()
            if any(k in lower for k in lowered_keywords):
                evidence.append({
                    "source_path": chunk["source_path"],
                    "line": idx,
                    "snippet": clean[:300],
                })
                break
        if len(evidence) >= limit:
            break

    return evidence


def candidate_id(title: str, evidence: list[dict[str, Any]]) -> str:
    payload = json.dumps({"title": title, "evidence": evidence}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def build_candidates(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []

    for cluster in CLUSTERS:
        evidence = find_evidence(chunks, cluster["keywords"])
        if not evidence:
            continue

        title = cluster["title"]
        tests = [
            "python3 -m py_compile link_research_upgrade_miner.py link_dashboard_proposal_refill.py link_self_learning_dashboard.py link_healthcheck.py",
            "python3 link_research_upgrade_miner.py --smoke",
            "python3 link_research_upgrade_miner.py --write-candidates --format markdown",
            "python3 link_dashboard_proposal_refill.py --clear-bugged --write --format markdown",
            "python3 link_self_learning_dashboard.py render --format markdown",
            "python3 link_self_learning_dashboard_web_admin.py --smoke",
            "python3 link_healthcheck.py",
            "git diff --check",
        ]

        candidates.append({
            "candidate_id": candidate_id(title, evidence),
            "source": "research_upgrade_miner",
            "source_version": VERSION,
            "title": title,
            "risk": "medium",
            "why": cluster["why"],
            "plan": cluster["plan"],
            "proposed_plan": cluster["plan"],
            "files": cluster["files"],
            "files_affected": cluster["files"],
            "areas_affected": cluster["files"],
            "tests": tests,
            "checks": tests,
            "receipts": [
                ".link/research_upgrade_miner/",
                ".link/approval_candidates.jsonl",
                ".link/patch_drafts/pending/",
                ".link/patch_drafts/receipts/",
            ],
            "evidence": evidence,
            "created_at": iso_now(),
        })

    if not candidates and chunks:
        evidence = []
        for chunk in chunks[:6]:
            first_line = ""
            for line in chunk["text"].splitlines():
                clean = re.sub(r"\s+", " ", line).strip()
                if len(clean) >= 20:
                    first_line = clean[:300]
                    break
            evidence.append({
                "source_path": chunk["source_path"],
                "line": 1,
                "snippet": first_line or "Text source found; no specific keyword line selected.",
            })

        title = "research corpus inventory and upgrade extraction baseline"
        plan = [
            "Inventory all readable research files and archives.",
            "Create a searchable index of upgrade-relevant text.",
            "Classify discovered ideas into approval candidates.",
            "Use the candidate queue to continue the human-approved upgrade chain.",
        ]
        candidates.append({
            "candidate_id": candidate_id(title, evidence),
            "source": "research_upgrade_miner",
            "source_version": VERSION,
            "title": title,
            "risk": "medium",
            "why": "Research files exist, but Link needs a baseline index before it can reliably mine concrete upgrade proposals.",
            "plan": plan,
            "proposed_plan": plan,
            "files": ["link_research_upgrade_miner.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
            "files_affected": ["link_research_upgrade_miner.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
            "areas_affected": ["link_research_upgrade_miner.py", "link_dashboard_proposal_refill.py", "link_healthcheck.py"],
            "tests": [
                "python3 link_research_upgrade_miner.py --smoke",
                "python3 link_healthcheck.py",
                "git diff --check",
            ],
            "checks": [
                "python3 link_research_upgrade_miner.py --smoke",
                "python3 link_healthcheck.py",
                "git diff --check",
            ],
            "receipts": [
                ".link/research_upgrade_miner/",
                ".link/approval_candidates.jsonl",
                ".link/patch_drafts/receipts/",
            ],
            "evidence": evidence,
            "created_at": iso_now(),
        })

    return candidates


def write_markdown_summary(path: Path, receipt: dict[str, Any]) -> None:
    lines = [
        "# Link Research Upgrade Miner",
        "",
        f"Version: `{VERSION}`",
        f"Generated: `{receipt['generated_at']}`",
        f"Readable research chunks: **{receipt['chunk_count']}**",
        f"New candidates written: **{receipt['candidate_count']}**",
        "",
        "## New Candidates",
    ]

    for cand in receipt.get("candidates", []):
        lines.append("")
        lines.append(f"### {cand['title']}")
        lines.append(f"- Candidate ID: `{cand['candidate_id']}`")
        lines.append(f"- Risk: `{cand.get('risk', 'medium')}`")
        lines.append(f"- Evidence count: `{len(cand.get('evidence', []))}`")
        for ev in cand.get("evidence", [])[:3]:
            lines.append(f"  - `{ev['source_path']}` line `{ev['line']}` — {ev['snippet'][:180]}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_miner(root: Path, research_dirs: list[str], candidate_file: Path, write_candidates: bool) -> dict[str, Any]:
    root = root.resolve()
    candidate_file = candidate_file if candidate_file.is_absolute() else root / candidate_file

    chunks = iter_chunks(root, research_dirs)
    all_candidates = build_candidates(chunks)
    seen = load_seen_titles(root, candidate_file)

    new_candidates = []
    for cand in all_candidates:
        key = norm_title(cand["title"])
        if key in seen:
            continue
        seen.add(key)
        new_candidates.append(cand)

    receipt = {
        "receipt_version": VERSION,
        "action": "mine_research_upgrade_candidates",
        "status": "ok",
        "generated_at": iso_now(),
        "research_dirs": research_dirs,
        "chunk_count": len(chunks),
        "candidate_count": len(new_candidates),
        "candidate_file": str(candidate_file),
        "candidates": new_candidates,
    }

    if write_candidates:
        (root / ".link/research_upgrade_miner/receipts").mkdir(parents=True, exist_ok=True)
        candidate_file.parent.mkdir(parents=True, exist_ok=True)

        with candidate_file.open("a", encoding="utf-8") as fh:
            for cand in new_candidates:
                fh.write(json.dumps(cand, sort_keys=True) + "\n")

        receipt_path = root / ".link/research_upgrade_miner/receipts" / f"{now_stamp()}-research-upgrade-miner.json"
        receipt["receipt_path"] = str(receipt_path)
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        latest_md = root / ".link/research_upgrade_miner/latest.md"
        write_markdown_summary(latest_md, receipt)
        receipt["latest_markdown"] = str(latest_md)

    return receipt


def print_markdown(receipt: dict[str, Any]) -> None:
    print("# Link Research Upgrade Miner")
    print()
    print(f"Version: `{VERSION}`")
    print(f"Status: **{receipt['status']}**")
    print(f"Readable research chunks: **{receipt['chunk_count']}**")
    print(f"New candidates written: **{receipt['candidate_count']}**")
    print(f"Candidate file: `{receipt['candidate_file']}`")
    if receipt.get("receipt_path"):
        print(f"Receipt: `{receipt['receipt_path']}`")
    print()
    for cand in receipt.get("candidates", []):
        print(f"## Candidate: {cand['title']}")
        print(f"- ID: `{cand['candidate_id']}`")
        print(f"- Why: {cand['why']}")
        print("- Evidence:")
        for ev in cand.get("evidence", [])[:4]:
            print(f"  - `{ev['source_path']}` line `{ev['line']}` — {ev['snippet'][:220]}")
        print()


def smoke() -> None:
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "research").mkdir(parents=True)
        (root / ".link/patch_drafts/pending").mkdir(parents=True)
        (root / "research/frontier_agents.md").write_text(
            "Self-evolving agent systems need research evidence, frontier gap grading, "
            "sandboxed implementation handoff, SWE-bench style verification, and human approval.\n",
            encoding="utf-8",
        )
        receipt = run_miner(
            root=root,
            research_dirs=["research"],
            candidate_file=Path(".link/approval_candidates.jsonl"),
            write_candidates=True,
        )
        assert receipt["chunk_count"] >= 1
        assert receipt["candidate_count"] >= 1
        assert (root / ".link/approval_candidates.jsonl").exists()
    print("research upgrade miner smoke OK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    ap.add_argument("--research-dir", action="append", default=None)
    ap.add_argument("--candidate-file", default=".link/approval_candidates.jsonl")
    ap.add_argument("--write-candidates", action="store_true")
    ap.add_argument("--format", choices=["markdown", "json"], default="markdown")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    if args.smoke:
        smoke()
        return

    root = Path(args.root)
    research_dirs = args.research_dir or DEFAULT_RESEARCH_DIRS
    receipt = run_miner(
        root=root,
        research_dirs=research_dirs,
        candidate_file=Path(args.candidate_file),
        write_candidates=args.write_candidates,
    )

    if args.format == "json":
        print(json.dumps(receipt, indent=2, sort_keys=True))
    else:
        print_markdown(receipt)


if __name__ == "__main__":
    main()
