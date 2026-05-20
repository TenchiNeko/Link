#!/usr/bin/env python3
from __future__ import annotations

"""
Link Specialist Fanout.

Deterministic read-only specialist audit layer.

Writes:
- .agents/tool_results/<run_id>/specialist_fanout.json
- .agents/reports/fanout-summary-<short-id>.md
"""

import argparse
import json
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent

SOURCE_FILES = [
    "link_web.py",
    "link_runtime_policy.py",
    "link_audit_fast.py",
    "link_engine.py",
    "link_autonomous.py",
    "link_loop_state.py",
    "link_healthcheck.py",
    "link_doctor.py",
    "standalone_main.py",
    "standalone_orchestrator.py",
]

ROUTE_MARKERS = [
    "link_audit_fast.py",
    "link_micro_patch.py",
    "link_autonomous.py",
    "link_engine.py",
    "is_read_only_prompt",
    "is_micro_patch_prompt",
    "use_read_only_fastpath",
    "use_micro_patch",
    "auto_restore",
    "safe-link-latest",
]


def _run(cmd: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {
            "cmd": cmd,
            "returncode": p.returncode,
            "stdout": p.stdout.strip()[-4000:],
            "stderr": p.stderr.strip()[-4000:],
        }
    except Exception as exc:
        return {"cmd": cmd, "returncode": 999, "stdout": "", "stderr": repr(exc)}


def repo_state() -> dict[str, Any]:
    head = _run(["git", "rev-parse", "--short", "HEAD"])
    safe_latest = _run(["git", "rev-parse", "--short", "safe-link-latest"])
    status = _run(["git", "status", "--short", "--untracked-files=all"])
    recent = _run(["git", "log", "--oneline", "--decorate", "-8"])
    return {
        "head": head["stdout"],
        "safe_link_latest": safe_latest["stdout"],
        "dirty": bool(status["stdout"].strip()),
        "status_short": status["stdout"],
        "recent_commits": recent["stdout"],
    }


def route_map() -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    for rel in SOURCE_FILES:
        path = ROOT / rel
        if not path.exists() or not path.is_file():
            continue
        lines = path.read_text(errors="replace").splitlines()
        for idx, line in enumerate(lines, 1):
            matched = [m for m in ROUTE_MARKERS if m in line]
            if matched:
                hits.append(
                    {
                        "file": rel,
                        "line": idx,
                        "markers": matched,
                        "text": line.strip()[:240],
                    }
                )
    return hits[:120]


def latest_failures(limit: int = 8) -> list[dict[str, Any]]:
    base = ROOT / ".agents" / "engine_runs"
    if not base.exists():
        return []

    reports = sorted(
        [p for p in base.glob("*/engine_report.json") if p.parent.name != "selftest"],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    out: list[dict[str, Any]] = []
    for p in reports:
        try:
            d = json.loads(p.read_text(errors="replace"))
        except Exception as exc:
            out.append({"path": str(p), "error": repr(exc)})
            continue

        events = d.get("events") or []
        out.append(
            {
                "path": str(p),
                "run_id": d.get("run_id"),
                "status": d.get("status") or d.get("engine_status"),
                "phase": d.get("phase") or d.get("engine_phase"),
                "exit_code": d.get("exit_code") or d.get("engine_exit_code"),
                "failure_type": d.get("failure_type"),
                "changed_files": d.get("changed_files") or [],
                "final_commit": d.get("final_commit"),
                "child_report": d.get("child_report"),
                "last_events": [
                    {
                        "phase": e.get("phase"),
                        "level": e.get("level") or e.get("kind"),
                        "title": e.get("title") or e.get("message"),
                        "detail": str(e.get("detail") or "")[:300],
                    }
                    for e in events[-6:]
                ],
            }
        )
    return out


def safety_status() -> dict[str, Any]:
    required_files = [
        "link_healthcheck.py",
        "link_doctor.py",
        "link_runtime_policy.py",
        "link_web.py",
        "link_engine.py",
    ]

    files_present = {name: (ROOT / name).exists() for name in required_files}
    markers = {}

    for name in required_files:
        path = ROOT / name
        if not path.exists():
            continue
        text = path.read_text(errors="replace")
        markers[name] = {
            "safe-link-latest": "safe-link-latest" in text,
            "auto_restore": "auto_restore" in text or "auto-restore" in text,
            "healthcheck": "healthcheck" in text.lower(),
            "command_guard": "command_guard" in text or "modern_command_guard" in text,
        }

    py_compile = _run(["python3", "-m", "py_compile", "link_specialist_fanout.py"])

    return {
        "files_present": files_present,
        "markers": markers,
        "self_compile_ok": py_compile["returncode"] == 0,
        "self_compile_stderr": py_compile["stderr"],
    }


def write_markdown_summary(data: dict[str, Any], run_id: str) -> str:
    reports_dir = ROOT / ".agents" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / f"fanout-summary-{run_id[:8]}.md"

    repo = data.get("repo_state", {})
    routes = data.get("route_map", [])
    failures = data.get("latest_failures", [])

    lines = [
        f"# Specialist Fanout Summary — {run_id}",
        "",
        "## Repo State",
        f"- HEAD: `{repo.get('head', '')}`",
        f"- safe-link-latest: `{repo.get('safe_link_latest', '')}`",
        f"- dirty: `{repo.get('dirty', False)}`",
        "",
        "## Route Map Signals",
        f"- route marker hits: {len(routes)}",
    ]

    for r in routes[:10]:
        lines.append(f"- `{r.get('file')}:{r.get('line')}` — {', '.join(r.get('markers', []))}")

    lines += [
        "",
        "## Latest Failure Signals",
        f"- reports scanned: {len(failures)}",
    ]

    for f in failures[:5]:
        lines.append(
            f"- `{f.get('run_id')}` status={f.get('status')} phase={f.get('phase')} "
            f"exit={f.get('exit_code')} changed={len(f.get('changed_files') or [])}"
        )

    lines += [
        "",
        "## Safety Status",
        f"- self compile OK: `{data.get('safety_status', {}).get('self_compile_ok')}`",
        "",
    ]

    path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)


def run_fanout(run_id: str | None = None, write_markdown: bool = True) -> dict[str, Any]:
    run_id = run_id or f"fanout-{uuid.uuid4().hex[:12]}"
    out_dir = ROOT / ".agents" / "tool_results" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {
        "run_id": run_id,
        "generated_at": time.time(),
        "repo_state": repo_state(),
        "route_map": route_map(),
        "latest_failures": latest_failures(),
        "safety_status": safety_status(),
    }

    json_path = out_dir / "specialist_fanout.json"
    summary_path = write_markdown_summary(data, run_id) if write_markdown else None

    data["json_path"] = str(json_path)
    data["summary_path"] = summary_path
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--no-markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    data = run_fanout(run_id=args.run_id, write_markdown=not args.no_markdown)

    if args.json:
        print(json.dumps(data, sort_keys=True))
    else:
        print("specialist fanout OK")
        print(f"json: {data['json_path']}")
        if data.get("summary_path"):
            print(f"summary: {data['summary_path']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
