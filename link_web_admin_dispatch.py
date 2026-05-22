#!/usr/bin/env python3
from __future__ import annotations

"""
Web admin dispatcher for Link.

Compatible with the web console's old micro-patch command shape:

    python3 link_web_admin_dispatch.py <prompt_label> /tmp/link-web-prompt.txt

It reads the real prompt, asks link_admin_planner.py for a deterministic route,
then dispatches safely:

- micro_patch -> link_micro_patch.py
- audit/read-only/broad/delegated review -> link_audit_fast.py
- unknown/high-risk -> prints the admin plan and exits without patch execution

This keeps the web UI from sending vague admin prompts directly into
link_micro_patch.py where they fail with "Expected exactly one safe target file".
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from capability_gate import classify_command as capability_classify_command
from execution_snapshots import create_execution_snapshot

ROOT = Path(__file__).resolve().parent


def explicit_delegate_providers(prompt: str) -> list[str]:
    """Honor explicit provider names in the admin/user prompt."""
    text = prompt.lower()
    providers = []

    if "local_qwen" in text or "local qwen" in text or "qwen" in text:
        providers.append("local_qwen")

    if "deepseek" in text or "deep seek" in text:
        providers.append("deepseek")

    return providers

def _read_prompt(display_prompt: str | None, prompt_file: str | None, prompt_override: str | None) -> str:
    if prompt_override:
        return prompt_override

    if prompt_file:
        path = Path(prompt_file)
        if path.exists() and path.is_file():
            return path.read_text(encoding="utf-8")

    return display_prompt or ""


def _run_capture(cmd: list[str], timeout: int = 30) -> tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return p.returncode, p.stdout, p.stderr
    except Exception as exc:
        return 99, "", f"{type(exc).__name__}: {exc}"


def _admin_plan(prompt: str) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(ROOT / "link_admin_planner.py"),
        "--prompt",
        prompt,
        "--json",
    ]
    code, out, err = _run_capture(cmd)
    if code != 0:
        return {
            "classification": {
                "task_type": "audit",
                "route": "audit_fastpath",
                "risk": "low",
                "reason": f"admin_planner_failed_fallback_to_audit: {err.strip() or code}",
            },
            "execution_allowed": False,
            "human_confirmation_required": True,
            "target_files": [],
            "delegate_to": ["local_qwen"],
            "required_verification": [
                "python3 link_healthcheck.py",
                "python3 link_doctor.py",
            ],
            "suggested_next_command": "python3 link_audit_fast.py '<specific audit prompt>'",
        }

    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:
        return {
            "classification": {
                "task_type": "audit",
                "route": "audit_fastpath",
                "risk": "low",
                "reason": f"admin_planner_json_decode_failed_fallback_to_audit: {exc}",
            },
            "execution_allowed": False,
            "human_confirmation_required": True,
            "target_files": [],
            "delegate_to": ["local_qwen"],
            "required_verification": [
                "python3 link_healthcheck.py",
                "python3 link_doctor.py",
            ],
            "suggested_next_command": "python3 link_audit_fast.py '<specific audit prompt>'",
        }


def _stream(cmd: list[str]) -> int:
    gate = capability_classify_command(cmd)
    if gate.decision == "deny":
        print(f"capability gate denied command: {gate.reason}")
        return 2

    snapshot = create_execution_snapshot(
        action="web_admin_dispatch",
        target=cmd,
        gate_decision=gate.decision,
        gate_reason=gate.reason,
        actor="link_web_admin_dispatch",
    )
    print(f"execution snapshot: {snapshot}")

    env = os.environ.copy()
    env.setdefault("PYTHONUNBUFFERED", "1")
    p = subprocess.Popen(cmd, cwd=ROOT, env=env)
    return int(p.wait())


def _audit_prompt(prompt: str, plan: dict[str, Any]) -> str:
    classification = plan.get("classification", {})
    route = classification.get("route")
    reason = classification.get("reason")
    targets = plan.get("target_files") or []
    delegates = plan.get("delegate_to") or []

    explicit = explicit_delegate_providers(prompt)
    if explicit:
        delegates = list(dict.fromkeys([*delegates, *explicit]))
        plan["delegate_to"] = delegates

    return (
        "ADMIN PLANNER ROUTED THIS WEB REQUEST TO AUDIT/REVIEW.\n\n"
        f"route: {route}\n"
        f"reason: {reason}\n"
        f"target_files: {targets}\n"
        f"delegate_to: {delegates}\n\n"
        "Task:\n"
        "- Inspect the current Link repo state.\n"
        "- Do not edit files.\n"
        "- Produce the next safe, specific action or exact patch target.\n"
        "- If this was a vague admin prompt, convert it into a concrete next task.\n\n"
        "Original prompt:\n"
        f"{prompt}"
    )


def _micro_cmd(display_prompt: str | None, prompt_file: str | None, prompt: str) -> list[str]:
    script = str(ROOT / "link_micro_patch.py")
    if prompt_file:
        return [sys.executable, script, display_prompt or "<prompt>", prompt_file]

    tmp = ROOT / ".agents" / "tmp_web_admin_dispatch_prompt.txt"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(prompt, encoding="utf-8")
    return [sys.executable, script, display_prompt or "<prompt>", str(tmp)]


def _audit_cmd(prompt: str, plan: dict[str, Any]) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "link_audit_fast.py"),
        _audit_prompt(prompt, plan),
    ]



def _delegates_enabled() -> bool:
    value = os.environ.get("LINK_ENABLE_MODEL_DELEGATES", "true").strip().lower()
    return value not in {"0", "false", "no", "off"}


def _delegate_cmd(prompt: str, plan: dict[str, object]) -> list[str]:
    return [
        sys.executable,
        str(ROOT / "link_delegate_runner.py"),
        "--prompt",
        prompt,
    ]

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("display_prompt", nargs="?")
    parser.add_argument("prompt_file", nargs="?")
    parser.add_argument("--prompt-file", dest="prompt_file_opt")
    parser.add_argument("--prompt", dest="prompt_override")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()

    prompt_file = args.prompt_file_opt or args.prompt_file
    prompt = _read_prompt(args.display_prompt, prompt_file, args.prompt_override)
    plan = _admin_plan(prompt)
    classification = plan.get("classification", {})
    route = classification.get("route")
    risk = classification.get("risk")

    if args.plan_only:
        if args.json:
            print(json.dumps(plan, indent=2, sort_keys=True))
        else:
            print("LINK WEB ADMIN DISPATCH PLAN")
            print(f"route: {route}")
            print(f"risk: {risk}")
            print(f"reason: {classification.get('reason')}")
            print(f"target_files: {plan.get('target_files')}")
            print(f"delegate_to: {plan.get('delegate_to')}")
        return 0

    print("LINK WEB ADMIN DISPATCH")
    print(f"route: {route}")
    print(f"risk: {risk}")
    print(f"reason: {classification.get('reason')}")
    print(f"delegate_to: {plan.get('delegate_to')}")
    print("")

    if route == "micro_patch" and risk in {"low", "medium"}:
        return _stream(_micro_cmd(args.display_prompt, prompt_file, prompt))

    if route in {"audit_fastpath", "read_only", "delegated_patch_review", "patch_review"}:
        if _delegates_enabled():
            return _stream(_delegate_cmd(prompt, plan))
        return _stream(_audit_cmd(prompt, plan))

    print("Admin dispatcher refused to execute this route directly.")
    print("Plan:")
    print(json.dumps(plan, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
