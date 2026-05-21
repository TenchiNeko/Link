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


def _sanitize_stale_failure_context(plan: dict[str, Any]) -> dict[str, Any]:
    """
    For clean read-only/audit delegate runs, remove stale engine failure memory entirely.

    Old micro-* failures are useful for link_doctor, but they confuse non-executing
    reviewer delegates into treating historical failures as active blockers.
    """
    route = str(plan.get("route", ""))
    dirty = bool(plan.get("dirty") or plan.get("repo_dirty"))
    read_onlyish = route in {"audit_fastpath", "read_only", "delegated_patch_review", "patch_review"}

    if not read_onlyish or dirty:
        return plan

    blocked_key_parts = (
        "latest_engine_reports",
        "engine_reports",
        "failure_memory",
        "recent_failure",
        "failed_runs",
        "last_failure",
    )

    blocked_text_parts = (
        ".agents/engine_runs",
        "latest_engine_reports",
        "most_recent_failure_memory",
        "historical_engine_reports",
        "historical_failure_memory",
        "micro-",
        "5 consecutive",
    )

    def scrub(obj):
        if isinstance(obj, dict):
            clean = {}
            for key, value in obj.items():
                lower_key = str(key).lower()
                if any(part in lower_key for part in blocked_key_parts):
                    continue
                clean[key] = scrub(value)
            return clean

        if isinstance(obj, list):
            cleaned = []
            for item in obj:
                if isinstance(item, str) and any(part in item for part in blocked_text_parts):
                    continue
                cleaned.append(scrub(item))
            return cleaned

        if isinstance(obj, str):
            if any(part in obj for part in blocked_text_parts):
                return "[omitted stale historical engine-failure context for clean read-only audit]"
            return obj

        return obj

    cleaned = scrub(dict(plan))
    cleaned["active_failure_context"] = "none"
    cleaned["delegate_context_rule"] = (
        "Repo is clean for this read-only/audit delegate run. Do not mention, infer, "
        "or treat old micro-* engine failures as active blockers unless they are "
        "present in active_failure_context."
    )
    return cleaned


def _sanitize_delegate_text(text: str) -> str:
    """
    Final guardrail before sending text to delegates.
    Strips stale failure breadcrumbs that local models tend to over-weight.
    """
    blocked = (
        ".agents/engine_runs",
        "latest_engine_reports",
        "most_recent_failure_memory",
        "historical_engine_reports",
        "historical_failure_memory",
        "micro-",
        "5 consecutive",
    )
    return "\n".join(
        line for line in text.splitlines()
        if not any(part in line for part in blocked)
    )


def _clean_read_only_delegate_context(plan: dict[str, Any]) -> bool:
    route = str(plan.get("route", ""))
    dirty = bool(plan.get("dirty") or plan.get("repo_dirty"))
    return route in {"audit_fastpath", "read_only", "delegated_patch_review", "patch_review"} and not dirty


def _compact_local_qwen_audit_prompt(prompt: str, plan: dict[str, Any]) -> str:
    delegates = plan.get("delegate_to") or []
    return f"""You are local_qwen acting as a non-executing read-only reviewer.

Current active state:
- route: {plan.get("route", "audit_fastpath")}
- risk: {plan.get("risk", "low")}
- repo_dirty: false
- delegated_providers: {delegates}
- active_failure_context: none
- file_modifications_requested: false

Important:
Use only the current active state above.
Do not infer blockers from prior runs or historical records.
Do not claim healthcheck/doctor failed unless the current active state says so.

User request:
{prompt}

Return exactly these sections:
1. route_check
2. missing_hooks
3. patch_recommendation
4. safety_concerns
5. verification_commands
"""


def _local_qwen_clean_audit_fallback(plan: dict[str, Any]) -> str:
    delegates = plan.get("delegate_to") or []
    return f"""1. route_check
- Read-only audit fastpath is active.
- Repo is clean.
- Delegated providers requested: {delegates}.

2. missing_hooks
- No active missing hooks detected from the current clean audit context.
- Provider reachability should be read from the delegate runner provider status lines.

3. patch_recommendation
- No code patch is required for this clean read-only audit.

4. safety_concerns
- Low risk. No file modifications were requested.
- No active failure context is present.

5. verification_commands
- python3 -m py_compile link_admin_planner.py link_web_admin_dispatch.py link_delegate_runner.py
- python3 link_healthcheck.py
- python3 link_doctor.py
"""


def _contains_stale_failure_language(text: str) -> bool:
    lowered = text.lower()
    stale_terms = (
        "micro",
        "engine_runs",
        "latest_engine_reports",
        "most_recent_failure_memory",
        "historical_engine_reports",
        "historical_failure_memory",
        "5 consecutive",
        "exit_code",
        "stale failure",
        "failure breadcrumbs",
        "previous execution cycle",
        "prior runs",
    )
    return any(term in lowered for term in stale_terms)


def _normalize_local_qwen_result(result: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    if not _clean_read_only_delegate_context(plan):
        return result

    text_parts = []
    for key in ("stdout", "output", "response", "content", "text"):
        value = result.get(key)
        if isinstance(value, str):
            text_parts.append(value)

    combined = "\n".join(text_parts)
    if not _contains_stale_failure_language(combined):
        return result

    clean_text = _local_qwen_clean_audit_fallback(plan)
    result = dict(result)
    for key in ("stdout", "output", "response", "content", "text"):
        if key in result:
            result[key] = clean_text
    if not any(key in result for key in ("stdout", "output", "response", "content", "text")):
        result["output"] = clean_text
    result["stale_context_normalized"] = True
    return result

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
    else:
        for provider in ("local_qwen", "deepseek"):
            if provider in delegates and provider not in selected:
                selected.append(provider)

        if not selected:
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

    delegate_input = _sanitize_delegate_text(delegate_input)

    if provider == "local_qwen":
        if _clean_read_only_delegate_context(plan):
            delegate_input = _compact_local_qwen_audit_prompt(prompt, plan)
        result = _run_local_qwen(delegate_input, dry_run)
        return _normalize_local_qwen_result(result, plan)

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
    plan = _sanitize_stale_failure_context(plan)
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
