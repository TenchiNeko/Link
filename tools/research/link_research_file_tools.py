#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

VERSION = "link-research-file-tools-v1"
ROOT = Path(__file__).resolve().parents[2]

ROOTS = {
    "research": ROOT / "factory" / "context",
    "runs": ROOT / "factory" / "projects",
    "approved": ROOT / ".link" / "patch_drafts" / "approved",
    "pending": ROOT / ".link" / "agent_queue" / "pending",
    "source": ROOT,
}

DENY_PARTS = {
    ".git", ".venv", "venv", "__pycache__", "node_modules",
    "external", "backups", "live_runs", ".next", "dist", "build",
}

DENY_NAMES = {".env", ".env.local", ".env.production", ".env.development"}

TEXT_EXT = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".sh",
}


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def resolve_root(root_key: str, path: str) -> Path:
    base = ROOTS[root_key].resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        raise SystemExit("Refusing path outside selected root")
    return target


def allowed(p: Path) -> bool:
    try:
        parts = set(p.relative_to(ROOT).parts)
    except ValueError:
        return False
    if parts & DENY_PARTS:
        return False
    if p.name in DENY_NAMES or p.name.startswith(".env."):
        return False
    return p.is_file() and p.suffix.lower() in TEXT_EXT


def iter_files(root: Path, limit: int):
    n = 0
    if root.is_file():
        if allowed(root):
            yield root
        return
    for p in sorted(root.rglob("*")):
        if n >= limit:
            return
        if allowed(p):
            n += 1
            yield p


def cmd_list(args):
    root = resolve_root(args.root, args.path)
    files = [rel(p) for p in iter_files(root, args.limit)]
    if args.format == "json":
        print(json.dumps({"version": VERSION, "files": files}, indent=2))
    else:
        print(f"# {VERSION}\n")
        for p in files:
            print(f"- `{p}`")


def cmd_grep(args):
    root = resolve_root(args.root, args.path)
    flags = 0 if args.case_sensitive else re.IGNORECASE
    rx = re.compile(args.pattern, flags)
    hits = []
    for p in iter_files(root, args.file_limit):
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        for i, line in enumerate(lines, 1):
            if rx.search(line):
                hits.append({"path": rel(p), "line": i, "text": line[:500]})
                if len(hits) >= args.limit:
                    break
        if len(hits) >= args.limit:
            break
    if args.format == "json":
        print(json.dumps({"version": VERSION, "matches": hits}, indent=2))
    else:
        print(f"# {VERSION}\n")
        for h in hits:
            print(f"{h['path']}:{h['line']}: {h['text']}")


def cmd_read(args):
    p = resolve_root(args.root, args.path)
    if not allowed(p):
        raise SystemExit("Refusing denied/non-text file")
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    for i in range(max(1, args.start), min(len(lines), args.end) + 1):
        print(f"{rel(p)}:{i}: {lines[i-1]}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list")
    p.add_argument("--root", choices=ROOTS, default="research")
    p.add_argument("--path", default=".")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("grep")
    p.add_argument("pattern")
    p.add_argument("--root", choices=ROOTS, default="research")
    p.add_argument("--path", default=".")
    p.add_argument("--limit", type=int, default=80)
    p.add_argument("--file-limit", type=int, default=1000)
    p.add_argument("--case-sensitive", action="store_true")
    p.add_argument("--format", choices=["markdown", "json"], default="markdown")
    p.set_defaults(func=cmd_grep)

    p = sub.add_parser("read")
    p.add_argument("--root", choices=ROOTS, default="research")
    p.add_argument("--path", required=True)
    p.add_argument("--start", type=int, default=1)
    p.add_argument("--end", type=int, default=120)
    p.set_defaults(func=cmd_read)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
