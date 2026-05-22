#!/usr/bin/env python3
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parent

def read_all(run_dir: Path) -> str:
    chunks = []
    for p in sorted(run_dir.glob("*.md")):
        chunks.append(f"\n--- {p.name} ---\n")
        chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)

def has_hard_truncation(text: str) -> bool:
    markers = [
        "[context truncated",
        "[dashboard display truncated]",
        "output truncated",
    ]
    return any(m.lower() in text.lower() for m in markers)

def audit_run(run_dir: Path) -> dict:
    text = read_all(run_dir)
    required_any = ["APPROVE DRAFT", "PASS", "REVISE"]
    return {
        "run": run_dir,
        "exists": run_dir.exists(),
        "has_markdown": bool(list(run_dir.glob("*.md"))),
        "has_decision": any(term in text for term in required_any),
        "hard_truncation": has_hard_truncation(text),
    }

def main() -> int:
    project = (
        os.environ.get("LINK_FACTORY_AUDIT_PROJECT")
        or os.environ.get("LINK_FACTORY_DEFAULT_PROJECT")
        or "default"
    )

    if len(sys.argv) > 1:
        run_dirs = [Path(arg).resolve() for arg in sys.argv[1:]]
    else:
        runs_root = ROOT / "factory" / "projects" / project / "runs"
        run_dirs = sorted(runs_root.glob("*"))[-3:] if runs_root.exists() else []

    out_dir = ROOT / "factory" / "context" / project
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "final_gate_terminal_audit.md"

    results = [audit_run(p) for p in run_dirs]
    approve = bool(results) and all(
        r["exists"] and r["has_markdown"] and r["has_decision"] and not r["hard_truncation"]
        for r in results
    )

    lines = [
        "# Final Gate Terminal Audit",
        "",
        "Deterministic local audit. Checks actual run files directly instead of relying on model context loading.",
        "",
        "## Verdict",
        "",
        "**APPROVE DRAFT**" if approve else "**REVISE**",
        "",
        "## Run Results",
        "",
        "| Run | Exists | Markdown | Decision Term | Hard Truncation |",
        "|---|---:|---:|---:|---:|",
    ]

    for r in results:
        lines.append(
            f"| `{r['run'].relative_to(ROOT) if r['run'].is_relative_to(ROOT) else r['run']}` "
            f"| {r['exists']} | {r['has_markdown']} | {r['has_decision']} | {r['hard_truncation']} |"
        )

    lines.extend([
        "",
        "## Governance Check",
        "",
        "- This script does not post, publish, deploy, schedule, buy, DM, email, or perform external actions.",
        "- It only reads local run artifacts and writes a local audit markdown file.",
        "",
    ])

    out.write_text("\n".join(lines), encoding="utf-8")
    print(out)
    print("\n".join(lines))
    return 0 if approve else 1

if __name__ == "__main__":
    raise SystemExit(main())
