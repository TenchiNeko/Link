#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from link_runtime_policy import build_policy_prompt, compact_engine_report_payload

ROOT = Path(__file__).resolve().parent


def run_cmd(cmd: list[str], *, timeout: int = 120) -> tuple[int, str]:
    cp = subprocess.run(
        cmd,
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    out = "\n".join(part for part in [cp.stdout, cp.stderr] if part).strip()
    return cp.returncode, out


def emit(events: list[dict], level: str, title: str, detail: str = "", raw: str = "") -> None:
    events.append(
        {
            "ts": time.time(),
            "level": level,
            "title": title,
            "detail": detail,
            "phase": "audit",
            "raw": raw,
        }
    )
    if raw:
        print(raw)
    elif detail:
        print(f"{title}: {detail}")
    else:
        print(title)


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast read-only Link audit path")
    parser.add_argument("--prompt-file")
    args = parser.parse_args()

    prompt = ""
    if args.prompt_file:
        prompt = Path(args.prompt_file).read_text(encoding="utf-8", errors="replace")
        prompt = build_policy_prompt(prompt, audit_only=True)

    run_id = "audit-" + hex(int(time.time() * 1000))[2:]
    events: list[dict] = []
    started = time.time()

    print("LINK AUDIT FAST PATH")
    print("repo:", ROOT)
    print("run_id:", run_id)
    print()

    emit(events, "info", "Prompt received", prompt[:1000])

    rc_status, out_status = run_cmd(["git", "status", "--short", "--untracked-files=all"])
    emit(events, "info", "Git status", "clean" if not out_status else "dirty", out_status)

    rc_log, out_log = run_cmd(["git", "log", "--oneline", "--decorate", "-8"])
    emit(events, "info", "Recent commits", raw=out_log)

    rc_doctor, out_doctor = run_cmd([sys.executable, str(ROOT / "link_doctor.py")])
    emit(
        events,
        "success" if rc_doctor == 0 else "error",
        "Link doctor",
        f"exit {rc_doctor}",
        out_doctor,
    )

    rc_health, out_health = run_cmd([sys.executable, str(ROOT / "link_healthcheck.py")])
    emit(
        events,
        "success" if rc_health == 0 else "error",
        "Healthcheck",
        f"exit {rc_health}",
        out_health,
    )

    exit_code = 0 if rc_status == 0 and rc_doctor == 0 and rc_health == 0 else 1

    report = {
        "run_id": run_id,
        "status": "completed" if exit_code == 0 else "failed",
        "phase": "audit",
        "started_at": started,
        "ended_at": time.time(),
        "exit_code": exit_code,
        "changed_files": [],
        "diff_lines": 0,
        "events": events,
        "report_path": str(ROOT / ".agents" / "engine_runs" / run_id / "engine_report.json"),
        "audit_fast_path": True,
    }

    report = compact_engine_report_payload(ROOT, report)
    report_path = Path(report["report_path"])
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print()
    print("Audit report:", report_path)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
