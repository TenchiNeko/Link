#!/usr/bin/env python3
from __future__ import annotations

"""
Link Delegate Runner.

No-write bridge between Link admin planning and optional model delegates.

Providers:
- local_qwen: local Ollama/Qwen/Gwen-style reviewer
- deepseek: DeepSeek API or command-based reviewer

Important:
- This runner never edits repo files.
- This runner never executes model-suggested commands.
- This runner only asks delegates for review/draft advice and writes a report.
- Link remains the only executor after safety gates.
"""

import argparse
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / ".agents" / "delegate_runs"

SCHEMA_VERSION = "link_delegate_report_v1"

DEFAULT_LOCAL_MODEL = "qwen2.5-coder:32b-instruct-q8_0"
DEFAULT_DEEPSEEK_MODEL = "deepseek-chat"
DEFAULT_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"


def _run(
    args: list[str],
    *,
    input_text: str | None = None,
    timeout: int = 180,
) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=ROOT,
            input=input_text,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 99, "", f"{type(exc).__name__}: {exc}"


def _read_prompt(
    display_prompt: str | None,
    prompt_file: str | None,
    prompt_override: str | None,
) -> str:
    if prompt_override is not None:
        return prompt_override

    if prompt_file:
        return Path(prompt_file).read_text(encoding="utf-8")

    if display_prompt:
        try:
            p = Path(display_prompt)
            if p.exists() and p.is_file():
                return p.read_text(encoding="utf-8")
        except OSError:
            pass
        return display_prompt

    if not sys.stdin.isatty():
        return sys.stdin.read()

    return ""


def _admin_plan(prompt: str) -> dict[str, Any]:
    code, out, err = _run(
        [sys.executable, str(ROOT / "link_admin_planner.py"), "--prompt", prompt, "--json"],
        timeout=30,
    )
    if code == 0:
        try:
            return json.loads(out)
        except json.JSONDecodeError as exc:
            return {
                "schema_version": "link_admin_plan_fallback_v1",
                "classification": {
                    "task_type": "audit",
                    "route": "audit_fastpath",
                    "risk": "medium",
                    "reason": f"admin_plan_json_decode_failed: {exc}",
                },
                "delegate_to": ["local_qwen"],
                "admin_error": out,
            }

    return {
        "schema_version": "link_admin_plan_fallback_v1",
        "classification": {
            "task_type": "audit",
            "route": "audit_fastpath",
            "risk": "medium",
            "reason": "admin_plan_command_failed",
        },
        "delegate_to": ["local_qwen"],
        "admin_error": err or out,
    }


def _parse_providers(value: str) -> list[str]:
    raw = (value or "auto").strip()
    if not raw:
        return ["auto"]
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return parts or ["auto"]


def _select_providers(requested: list[str], plan: dict[str, Any]) -> list[str]:
    if "none" in requested:
        return []

    allowed = ["local_qwen", "deepseek"]

    if "all" in requested:
        return allowed

    explicit = [p for p in allowed if p in requested]
    if explicit:
        return explicit

    classification = plan.get("classification", {})
    task_type = classification.get("task_type")
    risk = classification.get("risk")
    delegates = plan.get("delegate_to", []) or []

    selected: list[str] = []

    if task_type in {"patch_draft", "delegated_patch_review", "patch_review"}:
        selected.extend(["local_qwen", "deepseek"])
    elif "deepseek" in delegates:
        selected.append("deepseek")
    elif "local_qwen" in delegates:
        selected.append("local_qwen")
    else:
        selected.append("local_qwen")

    if risk == "high" and "deepseek" not in selected:
        selected.append("deepseek")

    deduped: list[str] = []
    for provider in selected:
        if provider in allowed and provider not in deduped:
            deduped.append(provider)

    return deduped


def _delegate_prompt(prompt: str, plan: dict[str, Any], provider: str) -> str:
    plan_json = json.dumps(plan, indent=2, sort_keys=True)
    return f"""You are a Link delegate reviewer named {provider}.

Rules:
- Do not edit files.
- Do not run commands.
- Do not suggest destructive commands.
- Treat Link as the only executor.
- Give concise implementation advice only.
- Prefer small deterministic patches.
- Call out missing hooks, unsafe routing, or verification gaps.

Return a compact review with:
1. route_check
2. missing_hooks
3. patch_recommendation
4. safety_concerns
5. verification_commands

User/Admin request:
{prompt}

Admin planner JSON:
{plan_json}
"""


def _configured_local_qwen() -> tuple[bool, str]:
    if os.environ.get("LINK_LOCAL_QWEN_CMD"):
        return True, "LINK_LOCAL_QWEN_CMD"
    if shutil.which("ollama"):
        return True, "ollama"
    return False, "Neither LINK_LOCAL_QWEN_CMD nor ollama was found"


def _configured_deepseek() -> tuple[bool, str]:
    if os.environ.get("LINK_DEEPSEEK_CMD"):
        return True, "LINK_DEEPSEEK_CMD"
    if os.environ.get("DEEPSEEK_API_KEY"):
        return True, "DEEPSEEK_API_KEY"
    return False, "Neither LINK_DEEPSEEK_CMD nor DEEPSEEK_API_KEY was set"


def _run_local_qwen(prompt: str, dry_run: bool) -> dict[str, Any]:
    configured, reason = _configured_local_qwen()
    if dry_run:
        return {
            "provider": "local_qwen",
            "status": "planned" if configured else "skipped",
            "configured": configured,
            "reason": reason,
        }

    if not configured:
        return {
            "provider": "local_qwen",
            "status": "skipped",
            "configured": False,
            "reason": reason,
        }

    timeout = int(os.environ.get("LINK_DELEGATE_TIMEOUT", "180"))
    cmd_env = os.environ.get("LINK_LOCAL_QWEN_CMD")

    if cmd_env:
        cmd = shlex.split(cmd_env)
    else:
        model = os.environ.get("LINK_LOCAL_QWEN_MODEL", DEFAULT_LOCAL_MODEL)
        cmd = ["ollama", "run", model]

    code, out, err = _run(cmd, input_text=prompt, timeout=timeout)
    return {
        "provider": "local_qwen",
        "status": "completed" if code == 0 else "failed",
        "configured": True,
        "command": cmd,
        "exit_code": code,
        "text": out,
        "stderr": err,
    }


def _run_deepseek_cmd(prompt: str, dry_run: bool) -> dict[str, Any]:
    cmd_env = os.environ.get("LINK_DEEPSEEK_CMD")
    if dry_run:
        return {
            "provider": "deepseek",
            "status": "planned",
            "configured": True,
            "reason": "LINK_DEEPSEEK_CMD",
        }

    timeout = int(os.environ.get("LINK_DELEGATE_TIMEOUT", "180"))
    cmd = shlex.split(cmd_env or "")
    code, out, err = _run(cmd, input_text=prompt, timeout=timeout)
    return {
        "provider": "deepseek",
        "status": "completed" if code == 0 else "failed",
        "configured": True,
        "command": cmd,
        "exit_code": code,
        "text": out,
        "stderr": err,
    }


def _run_deepseek_api(prompt: str, dry_run: bool) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if dry_run:
        return {
            "provider": "deepseek",
            "status": "planned",
            "configured": True,
            "reason": "DEEPSEEK_API_KEY",
        }

    model = os.environ.get("LINK_DEEPSEEK_MODEL", DEFAULT_DEEPSEEK_MODEL)
    url = os.environ.get("LINK_DEEPSEEK_URL", DEFAULT_DEEPSEEK_URL)
    timeout = int(os.environ.get("LINK_DELEGATE_TIMEOUT", "180"))

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "You are a no-write code review delegate for Link.",
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "temperature": 0.1,
        "stream": False,
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        return {
            "provider": "deepseek",
            "status": "completed",
            "configured": True,
            "model": model,
            "text": text,
            "raw_usage": data.get("usage"),
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "provider": "deepseek",
            "status": "failed",
            "configured": True,
            "model": model,
            "error": f"HTTPError {exc.code}",
            "stderr": body,
        }
    except Exception as exc:
        return {
            "provider": "deepseek",
            "status": "failed",
            "configured": True,
            "model": model,
            "error": f"{type(exc).__name__}: {exc}",
        }


def _run_deepseek(prompt: str, dry_run: bool) -> dict[str, Any]:
    configured, reason = _configured_deepseek()
    if not configured:
        return {
            "provider": "deepseek",
            "status": "skipped",
            "configured": False,
            "reason": reason,
        }

    if os.environ.get("LINK_DEEPSEEK_CMD"):
        return _run_deepseek_cmd(prompt, dry_run)

    return _run_deepseek_api(prompt, dry_run)


def _run_provider(provider: str, prompt: str, plan: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    delegate_input = _delegate_prompt(prompt, plan, provider)

    if provider == "local_qwen":
        return _run_local_qwen(delegate_input, dry_run)

    if provider == "deepseek":
        return _run_deepseek(delegate_input, dry_run)

    return {
        "provider": provider,
        "status": "skipped",
        "configured": False,
        "reason": "unknown provider",
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Link Delegate Report",
        "",
        f"- schema: `{report.get('schema_version')}`",
        f"- prompt_hash: `{report.get('prompt_hash')}`",
        f"- route: `{report.get('plan', {}).get('classification', {}).get('route')}`",
        f"- risk: `{report.get('plan', {}).get('classification', {}).get('risk')}`",
        f"- dry_run: `{report.get('dry_run')}`",
        "",
        "## Providers",
        "",
    ]

    for item in report.get("provider_results", []):
        lines.append(f"### {item.get('provider')}")
        lines.append("")
        lines.append(f"- status: `{item.get('status')}`")
        lines.append(f"- configured: `{item.get('configured')}`")
        if item.get("reason"):
            lines.append(f"- reason: {item.get('reason')}")
        if item.get("error"):
            lines.append(f"- error: {item.get('error')}")
        if item.get("stderr"):
            lines.append("")
            lines.append("```")
            lines.append(str(item.get("stderr"))[:2000])
            lines.append("```")
        if item.get("text"):
            lines.append("")
            lines.append("```")
            lines.append(str(item.get("text"))[:5000])
            lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _write_report(report: dict[str, Any]) -> dict[str, Any]:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    digest = report["prompt_hash"][:10]
    run_dir = RUNS_DIR / f"delegate-{stamp}-{digest}"
    run_dir.mkdir(parents=True, exist_ok=False)

    report_path = run_dir / "delegate_report.json"
    md_path = run_dir / "delegate_report.md"

    report["report_path"] = str(report_path)
    report["markdown_path"] = str(md_path)

    report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")
    return report


def build_report(
    prompt: str,
    providers_requested: list[str],
    dry_run: bool,
) -> dict[str, Any]:
    plan = _admin_plan(prompt)
    selected = _select_providers(providers_requested, plan)

    provider_results = [
        _run_provider(provider, prompt, plan, dry_run)
        for provider in selected
    ]

    return {
        "schema_version": SCHEMA_VERSION,
        "prompt": prompt,
        "prompt_hash": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "dry_run": dry_run,
        "providers_requested": selected,
        "plan": plan,
        "provider_results": provider_results,
        "safety": {
            "no_write": True,
            "model_suggested_commands_not_executed": True,
            "link_remains_only_executor": True,
        },
    }


def print_human(report: dict[str, Any]) -> None:
    classification = report.get("plan", {}).get("classification", {})
    print("LINK DELEGATE RUNNER")
    print(f"route: {classification.get('route')}")
    print(f"risk: {classification.get('risk')}")
    print(f"dry_run: {report.get('dry_run')}")
    print("")
    print("providers:")
    for item in report.get("provider_results", []):
        print(f"- {item.get('provider')}: {item.get('status')} configured={item.get('configured')}")
        if item.get("reason"):
            print(f"  reason: {item.get('reason')}")
        if item.get("error"):
            print(f"  error: {item.get('error')}")
    if report.get("report_path"):
        print("")
        print(f"report: {report.get('report_path')}")
        print(f"markdown: {report.get('markdown_path')}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("display_prompt", nargs="?")
    parser.add_argument("prompt_file", nargs="?")
    parser.add_argument("--prompt-file", dest="prompt_file_opt")
    parser.add_argument("--prompt", dest="prompt_override")
    parser.add_argument("--providers", default="auto", help="auto, all, none, local_qwen, deepseek, or comma list")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--no-report", action="store_true")
    args = parser.parse_args()

    prompt_file = args.prompt_file_opt or args.prompt_file
    prompt = _read_prompt(args.display_prompt, prompt_file, args.prompt_override)
    providers = _parse_providers(args.providers)

    report = build_report(prompt, providers, args.dry_run)

    if not args.no_report:
        report = _write_report(report)
    else:
        report["report_path"] = None
        report["markdown_path"] = None

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print_human(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
