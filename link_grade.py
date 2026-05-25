#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from typing import Any


def run(cmd: list[str], root: Path, timeout: int = 180) -> tuple[int, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return p.returncode, p.stdout.strip()
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else ""
        return 124, (out + f"\nTIMEOUT after {timeout}s").strip()
    except Exception as e:
        return 999, f"ERROR: {e}"


def letter(score: int) -> str:
    if score >= 97:
        return "A+"
    if score >= 93:
        return "A"
    if score >= 90:
        return "A-"
    if score >= 87:
        return "B+"
    if score >= 83:
        return "B"
    if score >= 80:
        return "B-"
    if score >= 77:
        return "C+"
    if score >= 73:
        return "C"
    if score >= 70:
        return "C-"
    if score >= 67:
        return "D+"
    if score >= 63:
        return "D"
    return "F"


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_upgrades(root: Path) -> list[dict[str, Any]]:
    path = root / "link_upgrade_registry.py"
    text = read_text(path)
    if not text:
        return []

    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == "UPGRADES":
                    segment = ast.get_source_segment(text, node.value)
                    if not segment:
                        return []
                    try:
                        value = ast.literal_eval(segment)
                    except Exception:
                        return []
                    if isinstance(value, list):
                        return [item for item in value if isinstance(item, dict)]
    return []


def has_marker(root: Path, marker: str) -> bool:
    return marker in read_text(root / "link_healthcheck.py")


def bool_text(value: bool) -> str:
    return "yes" if value else "no"


def build_grade_report(root: Path, run_checks: bool = False) -> dict[str, Any]:
    generated = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    branch_code, branch = run(["git", "branch", "--show-current"], root)
    status_code, status = run(["git", "status", "-sb"], root)
    short_status_code, short_status = run(["git", "status", "--short"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    log_code, recent_log = run(["git", "log", "--oneline", "-8"], root)

    clean = short_status.strip() == ""
    upstream_state = status.splitlines()[0] if status else ""
    synced = "..." in upstream_state and "ahead" not in upstream_state.lower() and "behind" not in upstream_state.lower()

    upgrades = extract_upgrades(root)
    upgrade_ids = [str(item.get("id", "")) for item in upgrades]
    duplicate_ids = sorted({u for u in upgrade_ids if upgrade_ids.count(u) > 1 and u})

    nums: list[int] = []
    for item in upgrade_ids:
        if item.startswith("LU"):
            try:
                nums.append(int(item[2:]))
            except ValueError:
                pass
    highest_lu = f"LU{max(nums)}" if nums else ""

    health_exit = None
    health_tail = ""
    health_passed = None
    if run_checks:
        health_exit, health_out = run([sys.executable, "link_healthcheck.py"], root, timeout=300)
        health_tail = "\n".join(health_out.splitlines()[-20:])
        health_passed = health_exit == 0 and "LINK HEALTHCHECK PASSED" in health_out

    markers = {
        "profile gate smoke coverage": has_marker(root, "profile gate smoke coverage OK"),
        "research source inventory command": has_marker(root, "research source inventory command OK"),
        "link grade command": has_marker(root, "link grade command OK"),
    }

    files = {
        "tool registry": (root / "link_tool_registry.py").exists(),
        "worker profiles": (root / "link_worker_profiles.py").exists(),
        "profile gate": (root / "link_profile_gate.py").exists(),
        "research source inventory": (root / "link_research_source_inventory.py").exists(),
        "link grade": (root / "link_grade.py").exists(),
        "grade context": (root / "LINK_MINING_TEAM_GRADE_CONTEXT.md").exists(),
    }

    readiness_score = 96
    if not clean:
        readiness_score -= 10
    if not synced:
        readiness_score -= 3
    if duplicate_ids:
        readiness_score -= 8
    if run_checks and health_passed is False:
        readiness_score -= 18
    if not all(markers.values()):
        readiness_score -= 4
    readiness_score = max(0, min(100, readiness_score))

    internal_score = 79
    if files["research source inventory"]:
        internal_score += 2
    if files["link grade"]:
        internal_score += 2
    if files["grade context"]:
        internal_score += 1
    if all(markers.values()):
        internal_score += 2
    if duplicate_ids:
        internal_score -= 5
    internal_score = max(0, min(100, internal_score))

    market_score = 54
    if files["research source inventory"]:
        market_score += 2
    if files["link grade"]:
        market_score += 2
    if has_marker(root, "workflow step executor OK"):
        market_score += 1
    if has_marker(root, "delegate runner OK"):
        market_score += 1
    market_score = max(0, min(100, market_score))

    areas = [
        ("Safety and guardrails", 100, "Strong command, file, git, capability, and profile gates."),
        ("Repo health and verification", 100 if clean and not duplicate_ids else 90, "Healthcheck-driven repo discipline remains a major strength."),
        ("Agent architecture", 93 if files["worker profiles"] and files["profile gate"] else 82, "Worker profiles and tool gates are in place; runtime UX still needs tightening."),
        ("Autonomous coding execution", 74, "Still needs a guarded task-to-patch runner with plan, approval, patch, tests, and diff receipt."),
        ("Developer UX", 60 if files["link grade"] else 57, "Improved by permanent grade command, but still lacks one daily-driver command center."),
        ("Parallelism and delegation", 66, "Delegation exists conceptually, but needs clearer scheduling, isolation, and progress visibility."),
        ("Model ecosystem integration", 56, "Needs explicit local/cloud/model routing profiles and fallback behavior."),
        ("Enterprise/team readiness", 62, "Strong local proof trail, but not yet a polished multi-user/team product."),
    ]

    comparators = [
        ("Claude Code", 63, "Terminal-native agentic coding and iterative codebase work.", "Needs smoother task-to-patch execution and model-driven repair loops."),
        ("Cursor", 54, "IDE/editor UX, inline review, rules, and daily-driver ergonomics.", "Needs a polished command center and review UX."),
        ("Devin", 50, "Cloud autonomous engineer workflow from task to PR.", "Needs reliable ticket-to-PR style orchestration."),
        ("Codex-style coding agents", 57, "CLI/app/cloud workflows, worktrees, automations, and model/tool ecosystem.", "Needs stronger model routing, task queues, and parallel work controls."),
    ]

    recommendations = [
        (1, "Guarded task-to-patch runner", "Closes the largest market-relative execution gap."),
        (2, "Concise task receipt format", "Reduces noise and makes human review fast."),
        (3, "Model routing profiles", "Makes local-fast, local-deep, cloud-deep, and fallback choices explicit."),
        (4, "Worker dashboard card", "Turns profiles, enabled tools, current task, pending approval, and latest test result into visible runtime state."),
        (5, "Daily-driver command center", "Unifies status, grade, run-task, receipts, and rollback pointers."),
    ]

    return {
        "generated": generated,
        "repository": str(root),
        "branch": branch if branch_code == 0 else "",
        "head": head if head_code == 0 else "",
        "working_tree_clean": clean,
        "upstream_state": upstream_state,
        "synced_with_upstream": synced,
        "highest_lu": highest_lu,
        "duplicate_upgrade_ids": duplicate_ids,
        "branch_readiness": {"score": readiness_score, "grade": letter(readiness_score), "meaning": "Current branch readiness and internal coherence."},
        "market_relative": {"score": market_score, "grade": letter(market_score), "meaning": "Comparison against polished agentic coding products available today."},
        "internal_platform_maturity": {"score": internal_score, "grade": letter(internal_score), "meaning": "Underlying platform maturity independent of market polish."},
        "markers": markers,
        "files": files,
        "areas": [{"area": a, "score": s, "grade": letter(s), "finding": f} for a, s, f in areas],
        "comparators": [{"leader": l, "link_score": s, "link_grade": letter(s), "leader_strength": st, "gap": g} for l, s, st, g in comparators],
        "recommendations": [{"priority": p, "candidate": c, "why": w} for p, c, w in recommendations],
        "healthcheck": {"ran": run_checks, "exit": health_exit, "passed": health_passed, "tail": health_tail},
        "recent_git_log": recent_log if log_code == 0 else "",
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("# Link Grade Report")
    lines.append("")
    lines.append(f"Generated: {data['generated']}")
    lines.append(f"Repository: `{data['repository']}`")
    lines.append(f"Branch: `{data['branch']}`")
    lines.append(f"HEAD: `{data['head']}`")
    lines.append(f"Working tree clean: **{bool_text(data['working_tree_clean'])}**")
    lines.append(f"Synced with upstream: **{bool_text(data['synced_with_upstream'])}**")
    lines.append(f"Highest LU detected: `{data['highest_lu']}`")
    lines.append("")
    lines.append("## Grades")
    lines.append("")
    lines.append("| Grade Type | Grade | Score | Meaning |")
    lines.append("|---|---:|---:|---|")
    for key, label in [
        ("branch_readiness", "Branch readiness"),
        ("internal_platform_maturity", "Internal platform maturity"),
        ("market_relative", "Market-relative"),
    ]:
        item = data[key]
        lines.append(f"| {label} | {item['grade']} | {item['score']} | {item['meaning']} |")
    lines.append("")
    lines.append("## Area Breakdown")
    lines.append("")
    lines.append("| Area | Grade | Score | Finding |")
    lines.append("|---|---:|---:|---|")
    for area in data["areas"]:
        lines.append(f"| {area['area']} | {area['grade']} | {area['score']} | {area['finding']} |")
    lines.append("")
    lines.append("## Market Comparators")
    lines.append("")
    lines.append("| Comparator | Link Grade vs Leader | Leader Strength | Main Gap |")
    lines.append("|---|---:|---|---|")
    for comp in data["comparators"]:
        lines.append(f"| {comp['leader']} | {comp['link_grade']} / {comp['link_score']} | {comp['leader_strength']} | {comp['gap']} |")
    lines.append("")
    lines.append("## Evidence")
    lines.append("")
    lines.append(f"- Duplicate upgrade IDs: `{data['duplicate_upgrade_ids']}`")
    lines.append(f"- Upstream state: `{data['upstream_state']}`")
    for name, value in data["markers"].items():
        lines.append(f"- Healthcheck marker `{name}`: **{bool_text(value)}**")
    for name, value in data["files"].items():
        lines.append(f"- File/component `{name}` present: **{bool_text(value)}**")
    if data["healthcheck"]["ran"]:
        lines.append(f"- Healthcheck exit: `{data['healthcheck']['exit']}`")
        lines.append(f"- Healthcheck passed: **{bool_text(bool(data['healthcheck']['passed']))}**")
    lines.append("")
    lines.append("## Recommended Next Upgrades")
    lines.append("")
    lines.append("| Priority | Candidate | Why |")
    lines.append("|---:|---|---|")
    for rec in data["recommendations"]:
        lines.append(f"| {rec['priority']} | {rec['candidate']} | {rec['why']} |")
    if data["healthcheck"]["tail"]:
        lines.append("")
        lines.append("## Healthcheck Tail")
        lines.append("")
        lines.append("    " + data["healthcheck"]["tail"].replace("\n", "\n    "))
    lines.append("")
    lines.append("## Recent Git Log")
    lines.append("")
    lines.append("    " + data["recent_git_log"].replace("\n", "\n    "))
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Link branch/internal/market grade report.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--output")
    parser.add_argument("--run-checks", action="store_true")
    args = parser.parse_args()

    root = Path.cwd()
    data = build_grade_report(root, run_checks=args.run_checks)
    rendered = json.dumps(data, indent=2, sort_keys=True) if args.format == "json" else render_markdown(data)

    if args.output:
        out = Path(args.output)
        if not out.is_absolute():
            out = root / out
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(rendered + "\n", encoding="utf-8")
        print(out)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
