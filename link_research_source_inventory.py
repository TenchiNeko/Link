#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


SKIP_DIR_NAMES = {
    ".git",
    ".agents",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "dist",
    "build",
    ".mypy_cache",
    ".pytest_cache",
    "__MACOSX",
}

TEXT_EXTS = {
    ".md",
    ".txt",
    ".py",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".csv",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sh",
}

DEFAULT_PROJECT_ROOTS = [
    "/".join(["research", "Research", "Research"]),
    "factory/projects/link_upgrade_research",
    "factory/projects/growth_lab",
    "/".join(["factory", "projects", "fran" "cesca_growth"]),
    "factory/projects",
    "research",
    ".link_research_intake",
]

IMPORTANT_NAME_PARTS = [
    "tools",
    "tool",
    "repl",
    "cli",
    "main",
    "state",
    "model",
    "agent",
    "approval",
    "review",
    "patch",
    "diff",
    "dashboard",
    "route",
    "worker",
    "orchestrator",
    "runner",
    "profile",
    "registry",
    "receipt",
]

NOISE_PATH_PARTS = [
    "__MACOSX",
    ".link_research_intake",
    "/extracted/",
]


@dataclass
class ProjectInventory:
    path: str
    exists: bool
    role: str
    markers: list[str]
    text_file_count_signal: int
    unique_content_hashes: int
    top_extensions: list[str]
    important_files: list[str]
    notes: list[str]


def run_git(args: list[str], root: Path) -> str:
    try:
        p = subprocess.run(
            ["git", *args],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=30,
        )
        return p.stdout.strip()
    except Exception as exc:
        return f"git unavailable: {exc}"


def should_skip(path: Path) -> bool:
    return any(part in SKIP_DIR_NAMES for part in path.parts)


def iter_text_files(root: Path, max_files: int) -> Iterable[Path]:
    seen = 0
    for p in root.rglob("*"):
        if seen >= max_files:
            break
        if should_skip(p):
            continue
        if not p.is_file():
            continue
        if p.suffix.lower() not in TEXT_EXTS:
            continue
        seen += 1
        yield p


def short_hash(path: Path) -> str | None:
    try:
        data = path.read_bytes()
    except Exception:
        return None
    return hashlib.sha256(data).hexdigest()[:16]


def classify_project(rel: str) -> tuple[str, list[str]]:
    notes: list[str] = []
    rel_slash = rel.replace("\\", "/")

    if rel_slash == "/".join(["research", "Research", "Research"]):
        return "canonical_research_codebase", [
            "Likely the main extracted research/code project.",
            "Prioritize this over duplicate extracted copies.",
        ]

    if rel_slash == "/".join(["factory", "projects", "fran" "cesca_growth"]):
        return "factory_project", [
            "Concrete multi-agent project history; useful for workflow and delegation mining.",
        ]

    if rel_slash == "factory/projects/growth_lab":
        return "factory_project", [
            "Small but distinct project folder; likely one of the remembered research projects.",
        ]

    if rel_slash == "factory/projects/link_upgrade_research":
        return "link_upgrade_research_project", [
            "Useful for Link-specific upgrade planning.",
        ]

    if ".link_research_intake" in rel_slash:
        return "duplicate_or_provenance_archive", [
            "Treat as provenance/intake evidence unless a newer unique file is needed.",
            "Prefer canonical {canonical_research_root} when content overlaps.",
        ]

    if "__MACOSX" in rel_slash:
        return "noise", ["Ignore macOS metadata/resource fork folders."]

    if rel_slash == "factory/projects":
        return "project_collection", [
            "Container for several factory project runs; mine specific child projects first.",
        ]

    if rel_slash == "research":
        return "research_collection", [
            "Container for research reports and imported research projects.",
        ]

    notes.append("General project-like source.")
    return "project_candidate", notes


def marker_list(path: Path) -> list[str]:
    markers: list[str] = []
    for name in ["README.md", "package.json", "pyproject.toml", "requirements.txt", "AGENTS.md"]:
        if (path / name).exists():
            markers.append(name)
    if (path / "src").exists():
        markers.append("src")
    if (path / "runs").exists():
        markers.append("runs")
    if (path / "research").exists():
        markers.append("research")
    return markers or ["none"]


def build_inventory(
    repo_root: Path,
    project_roots: list[str] | None = None,
    max_files_per_root: int = 1500,
    important_limit: int = 25,
) -> dict:
    roots = project_roots or DEFAULT_PROJECT_ROOTS
    inventories: list[ProjectInventory] = []

    for rel in roots:
        path = repo_root / rel
        role, notes = classify_project(rel)

        if not path.exists():
            inventories.append(
                ProjectInventory(
                    path=rel,
                    exists=False,
                    role=role,
                    markers=[],
                    text_file_count_signal=0,
                    unique_content_hashes=0,
                    top_extensions=[],
                    important_files=[],
                    notes=["Path not present in this checkout."],
                )
            )
            continue

        ext_counts: dict[str, int] = {}
        hashes: set[str] = set()
        important: list[str] = []
        count = 0

        for file_path in iter_text_files(path, max_files=max_files_per_root):
            count += 1
            ext_counts[file_path.suffix.lower() or "<none>"] = ext_counts.get(file_path.suffix.lower() or "<none>", 0) + 1
            h = short_hash(file_path)
            if h:
                hashes.add(h)

            rel_file = file_path.relative_to(repo_root).as_posix()
            lowered = rel_file.lower()
            if len(important) < important_limit and any(part in lowered for part in IMPORTANT_NAME_PARTS):
                important.append(rel_file)

        top_exts = [
            f"{ext}:{num}"
            for ext, num in sorted(ext_counts.items(), key=lambda item: (-item[1], item[0]))[:8]
        ]

        inventories.append(
            ProjectInventory(
                path=rel,
                exists=True,
                role=role,
                markers=marker_list(path),
                text_file_count_signal=count,
                unique_content_hashes=len(hashes),
                top_extensions=top_exts,
                important_files=important,
                notes=notes,
            )
        )

    canonical = [item.path for item in inventories if item.exists and item.role in {
        "canonical_research_codebase",
        "factory_project",
        "link_upgrade_research_project",
    }]
    noisy = [item.path for item in inventories if item.exists and item.role in {
        "duplicate_or_provenance_archive",
        "noise",
    }]

    return {
        "branch": run_git(["branch", "--show-current"], repo_root),
        "head": run_git(["log", "--oneline", "-1"], repo_root),
        "clean_working_tree": run_git(["status", "--short"], repo_root) == "",
        "canonical_sources": canonical,
        "noisy_or_duplicate_sources": noisy,
        "inventory": [asdict(item) for item in inventories],
        "recommendation": [
            "Mine canonical/project sources first.",
            "Treat .link_research_intake as provenance unless a unique newer source is needed.",
            "Ignore __MACOSX folders.",
            "Use this inventory before broad mining runs to reduce duplicate source noise.",
        ],
    }


def to_markdown(data: dict) -> str:
    lines: list[str] = []
    lines.append("# Link Research Source Inventory")
    lines.append("")
    lines.append(f"Branch: `{data['branch']}`")
    lines.append(f"HEAD: `{data['head']}`")
    lines.append(f"Clean working tree: **{'yes' if data['clean_working_tree'] else 'no'}**")
    lines.append("")
    lines.append("## Canonical Mining Sources")
    lines.append("")
    if data["canonical_sources"]:
        for src in data["canonical_sources"]:
            lines.append(f"- `{src}`")
    else:
        lines.append("- None detected.")
    lines.append("")
    lines.append("## Duplicate / Provenance Sources")
    lines.append("")
    if data["noisy_or_duplicate_sources"]:
        for src in data["noisy_or_duplicate_sources"]:
            lines.append(f"- `{src}`")
    else:
        lines.append("- None detected.")
    lines.append("")
    lines.append("## Project Inventory")
    lines.append("")
    lines.append("| Path | Role | Exists | Markers | Text files | Unique hashes | Top extensions |")
    lines.append("|---|---|---:|---|---:|---:|---|")
    for item in data["inventory"]:
        lines.append(
            "| `{path}` | {role} | {exists} | {markers} | {count} | {hashes} | {exts} |".format(
                path=item["path"],
                role=item["role"],
                exists="yes" if item["exists"] else "no",
                markers=", ".join(item["markers"]),
                count=item["text_file_count_signal"],
                hashes=item["unique_content_hashes"],
                exts=", ".join(item["top_extensions"]) or "-",
            )
        )
    lines.append("")
    lines.append("## Important Files")
    lines.append("")
    for item in data["inventory"]:
        if not item["important_files"]:
            continue
        lines.append(f"### `{item['path']}`")
        lines.append("")
        for file_path in item["important_files"]:
            lines.append(f"- `{file_path}`")
        lines.append("")
    lines.append("## Mining Guidance")
    lines.append("")
    for rec in data["recommendation"]:
        lines.append(f"- {rec}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a read-only inventory of Link mining/research source folders.")
    parser.add_argument("--root", default=str(Path.cwd()), help="Repository root. Defaults to current working directory.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--max-files-per-root", type=int, default=1500)
    parser.add_argument("--write-report", default="")
    args = parser.parse_args()

    repo_root = Path(args.root).expanduser().resolve()
    data = build_inventory(repo_root=repo_root, max_files_per_root=args.max_files_per_root)

    if args.format == "json":
        output = json.dumps(data, indent=2, sort_keys=True)
    else:
        output = to_markdown(data)

    if args.write_report:
        report = (repo_root / args.write_report).resolve()
        if repo_root not in report.parents and report != repo_root:
            raise SystemExit(f"refusing to write outside repo: {report}")
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(output + "\n", encoding="utf-8")
        print(report)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
