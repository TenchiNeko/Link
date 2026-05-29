#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from link_common import ROOT, json_print, read_json

DEFAULT_RULES: dict[str, Any] = {
    "command_guard": {
        "allow": [
            "read-only inspection commands",
            "git status/diff/log",
            "python compilation checks",
            "healthcheck/self-test commands",
        ],
        "caution": [
            "commands that modify files",
            "git add/commit/checkout",
            "package installation",
            "script execution not known to be read-only",
        ],
        "deny": [
            "destructive recursive deletes against root/home",
            "force push",
            "hard reset",
            "git clean deleting untracked work",
            "downloaded shell scripts piped directly into a shell",
            "recursive world-writable chmods against home/repo roots",
        ],
    },
    "file_safety": {
        "allow": ["tracked source files inside repo"],
        "caution": ["research/reference material", ".agents generated state"],
        "deny": [".git internals", "paths outside repo", "protected generated/internal state"],
    },
    "git_safety": {
        "safe_reads": ["status", "diff", "log", "show"],
        "guarded_writes": ["add", "commit", "tag"],
        "deny": ["reset --hard", "clean -fdx", "push --force"],
    },
    "engine": {
        "max_changed_files_default": 8,
        "max_diff_lines_default": 1200,
        "expected_change_guard": True,
        "auto_restore_on_failure": True,
        "write_live_engine_report": True,
    },
    "web": {
        "route_runs_through_engine": True,
        "status_endpoint": "/api/run/<id>",
        "journal_status_poller": True,
        "fake_worktree_toggle_forbidden": True,
    },
    "diagnostics": {
        "doctor": True,
        "loop_report": True,
        "agent_listing": True,
        "endpoint_status": True,
        "config_conflict_report": True,
    },
    "redaction": {
        "redact_keys_matching": ["token", "secret", "api_key", "authorization", "cookie", "password", "webhook"],
    },
}


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = deep_merge(out[key], value)
        else:
            out[key] = value
    return out


def local_rules() -> dict[str, Any]:
    path = ROOT / "link_rules.local.json"
    data = read_json(path)
    return data or {}


def effective_rules() -> dict[str, Any]:
    return deep_merge(DEFAULT_RULES, local_rules())


def critique_rules(rules: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, str]] = []

    def require(path: str, severity: str, message: str) -> None:
        cur: Any = rules
        for part in path.split("."):
            if not isinstance(cur, dict) or part not in cur:
                findings.append({"severity": severity, "path": path, "message": message})
                return
            cur = cur[part]

    require("engine.expected_change_guard", "high", "No-op success can slip through without expected-change rules.")
    require("engine.auto_restore_on_failure", "high", "Failed runs should restore safe baseline automatically.")
    require("web.status_endpoint", "medium", "Web runs need a status endpoint for non-SSE diagnostics.")
    require("redaction.redact_keys_matching", "high", "Status tools must redact secrets before printing.")

    deny_text = " ".join(rules.get("command_guard", {}).get("deny", []))
    if "force push" not in deny_text:
        findings.append({"severity": "high", "path": "command_guard.deny", "message": "Force-push denial is missing."})
    if "downloaded" not in deny_text:
        findings.append({"severity": "high", "path": "command_guard.deny", "message": "Downloaded script pipe denial is missing."})

    web = rules.get("web", {})
    if web.get("fake_worktree_toggle_forbidden") is not True:
        findings.append({"severity": "medium", "path": "web.fake_worktree_toggle_forbidden", "message": "Fake UI toggles can imply isolation that is not actually active."})

    if not findings:
        findings.append({"severity": "info", "path": "all", "message": "No obvious rule conflicts detected."})

    return {"findings": findings, "finding_count": len(findings)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect and critique Link safety/runtime rules.")
    parser.add_argument("command", choices=["defaults", "effective", "critique"])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.command == "defaults":
        data = DEFAULT_RULES
    elif args.command == "effective":
        data = effective_rules()
    else:
        data = critique_rules(effective_rules())

    if args.json or args.command in {"defaults", "effective", "critique"}:
        json_print(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
