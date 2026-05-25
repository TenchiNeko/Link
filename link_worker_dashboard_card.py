#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import subprocess
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from link_worker_profiles import profile_summary, validate_profiles


WORKER_DASHBOARD_VERSION = "LU94-worker-dashboard-card-v1"


def run(cmd: list[str], root: Path, timeout: int = 30) -> tuple[int, str]:
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
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout if isinstance(exc.stdout, str) else ""
        return 124, (out + f"\nTIMEOUT after {timeout}s").strip()
    except Exception as exc:
        return 999, f"ERROR: {exc}"


def short_text(value: str, limit: int = 96) -> str:
    value = (value or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def normalize_model_item(item: Any) -> dict[str, Any]:
    if item is None:
        return {}
    if isinstance(item, dict):
        return dict(item)
    if is_dataclass(item):
        return asdict(item)
    if hasattr(item, "to_dict") and callable(item.to_dict):
        try:
            return dict(item.to_dict())
        except Exception:
            pass
    if hasattr(item, "__dict__"):
        return dict(item.__dict__)
    return {"value": str(item)}


def routing_inventory(module: Any) -> list[dict[str, Any]]:
    for fn_name in ["list_profiles", "list_routing_profiles", "all_profiles"]:
        fn = getattr(module, fn_name, None)
        if callable(fn):
            try:
                result = fn()
                if isinstance(result, dict):
                    if "profiles" in result and isinstance(result["profiles"], list):
                        return [normalize_model_item(x) for x in result["profiles"]]
                    return [normalize_model_item(x) for x in result.values()]
                if isinstance(result, list):
                    return [normalize_model_item(x) for x in result]
            except Exception:
                pass

    for attr in ["PROFILES", "ROUTING_PROFILES", "MODEL_ROUTING_PROFILES"]:
        result = getattr(module, attr, None)
        if result is None:
            continue
        if isinstance(result, dict):
            return [normalize_model_item(x) for x in result.values()]
        if isinstance(result, list | tuple):
            return [normalize_model_item(x) for x in result]

    profile_map = getattr(module, "profile_map", None)
    if callable(profile_map):
        try:
            result = profile_map()
            if isinstance(result, dict):
                return [normalize_model_item(x) for x in result.values()]
        except Exception:
            pass

    return []


def resolve_model_route(goal: str) -> dict[str, Any]:
    try:
        import link_model_routing_profiles as routing
    except Exception as exc:
        return {
            "ok": False,
            "source": "link_worker_dashboard_card",
            "error": f"model routing profiles unavailable: {exc}",
        }

    for fn_name in [
        "select_routing_profile",
        "select_model_routing_profile",
        "select_profile",
        "choose_routing_profile",
        "route_for_goal",
        "route_model",
    ]:
        fn = getattr(routing, fn_name, None)
        if not callable(fn):
            continue

        for args, kwargs in [
            ((goal,), {}),
            ((), {"goal": goal}),
            ((), {"task": goal}),
            ((), {"current_task": goal}),
        ]:
            try:
                selected = fn(*args, **kwargs)
                return {
                    "ok": True,
                    "source": f"link_model_routing_profiles.{fn_name}",
                    "selected": normalize_model_item(selected),
                }
            except TypeError:
                continue
            except Exception as exc:
                return {
                    "ok": False,
                    "source": f"link_model_routing_profiles.{fn_name}",
                    "error": str(exc),
                }

    profiles = routing_inventory(routing)
    goal_lower = goal.lower()

    preferred = {}
    for profile in profiles:
        haystack = " ".join(
            str(profile.get(k, ""))
            for k in ["name", "provider", "default_model", "use_cases", "fallback_profile"]
        ).lower()
        if any(token in haystack for token in goal_lower.split() if len(token) >= 4):
            preferred = profile
            break

    if not preferred and profiles:
        preferred = sorted(profiles, key=lambda x: x.get("priority", 999))[0]

    return {
        "ok": bool(preferred),
        "source": "link_model_routing_profiles.inventory",
        "selected": preferred,
        "available_count": len(profiles),
    }


def build_worker_dashboard_card(
    root: Path,
    current_task: str,
    worker_profile: str = "patch_worker",
    pending_approval: bool = False,
    latest_test_result: str = "unknown",
) -> dict[str, Any]:
    root = root.resolve()

    branch_code, branch = run(["git", "branch", "--show-current"], root)
    head_code, head = run(["git", "log", "--oneline", "-1"], root)
    status_code, status = run(["git", "status", "--short"], root)

    validation = validate_profiles()
    summary = profile_summary(worker_profile)

    enabled_tool_names = summary.get("enabled_tool_names")
    if enabled_tool_names is None:
        enabled_tool_names = []
        for tool in summary.get("enabled_tools", []):
            if isinstance(tool, dict) and tool.get("name"):
                enabled_tool_names.append(tool["name"])

    profile_payload = summary.get("profile", {})
    max_risk = profile_payload.get("max_risk") if isinstance(profile_payload, dict) else None

    return {
        "receipt_version": WORKER_DASHBOARD_VERSION,
        "generated": dt.datetime.now().isoformat(timespec="seconds"),
        "repo": str(root),
        "branch": branch if branch_code == 0 else "",
        "head": head if head_code == 0 else "",
        "working_tree_clean": status_code == 0 and status.strip() == "",
        "current_task": current_task,
        "worker_profile": worker_profile,
        "worker_profile_max_risk": max_risk,
        "profile_validation_ok": bool(validation.get("ok")),
        "enabled_tool_count": len(enabled_tool_names),
        "enabled_tool_names": enabled_tool_names[:12],
        "pending_approval": bool(pending_approval),
        "latest_test_result": latest_test_result,
        "model_routing": resolve_model_route(current_task),
        "status": "pending approval" if pending_approval else "ready",
        "next_action": "review pending approval" if pending_approval else "run targeted checks",
    }


def validate_worker_dashboard_card(card: dict[str, Any]) -> list[str]:
    problems: list[str] = []

    required = [
        "receipt_version",
        "generated",
        "repo",
        "branch",
        "head",
        "current_task",
        "worker_profile",
        "enabled_tool_count",
        "enabled_tool_names",
        "pending_approval",
        "latest_test_result",
        "model_routing",
        "status",
        "next_action",
    ]

    for key in required:
        if key not in card:
            problems.append(f"missing key: {key}")

    if card.get("receipt_version") != WORKER_DASHBOARD_VERSION:
        problems.append("unexpected receipt version")

    if not card.get("current_task"):
        problems.append("current task is empty")

    if not card.get("worker_profile"):
        problems.append("worker profile is empty")

    if not isinstance(card.get("pending_approval"), bool):
        problems.append("pending_approval must be boolean")

    if card.get("enabled_tool_count", 0) < 1:
        problems.append("dashboard card should expose at least one enabled tool")

    if not isinstance(card.get("model_routing"), dict):
        problems.append("model_routing must be an object")

    return problems


def render_worker_dashboard_markdown(card: dict[str, Any]) -> str:
    route = card.get("model_routing", {})
    selected = route.get("selected") if isinstance(route, dict) else {}
    selected_name = ""
    selected_provider = ""

    if isinstance(selected, dict):
        selected_name = selected.get("name") or selected.get("profile") or ""
        selected_provider = selected.get("provider") or ""

    lines = [
        "# Link Worker Dashboard Card",
        "",
        f"Task: {card.get('current_task')}",
        f"Worker profile: `{card.get('worker_profile')}`",
        f"Status: **{card.get('status')}**",
        f"Pending approval: **{'yes' if card.get('pending_approval') else 'no'}**",
        f"Latest test: `{card.get('latest_test_result')}`",
        f"Branch: `{card.get('branch')}`",
        f"HEAD: `{short_text(card.get('head', ''))}`",
        f"Working tree clean: **{'yes' if card.get('working_tree_clean') else 'no'}**",
        f"Enabled tools: **{card.get('enabled_tool_count')}**",
        f"Model route: `{selected_name or 'unknown'}` `{selected_provider}`".rstrip(),
        "",
        "## Visible Tools",
    ]

    for name in card.get("enabled_tool_names", [])[:8]:
        lines.append(f"- `{name}`")

    if not card.get("enabled_tool_names"):
        lines.append("- none")

    lines += [
        "",
        "## Next Action",
        card.get("next_action", ""),
    ]

    return "\n".join(lines).rstrip() + "\n"


def render_worker_dashboard_html(card: dict[str, Any]) -> str:
    tools = "".join(
        f"<li><code>{html.escape(str(name))}</code></li>"
        for name in card.get("enabled_tool_names", [])[:8]
    ) or "<li>none</li>"

    version = html.escape(str(card.get("receipt_version", "")))
    current_task = html.escape(str(card.get("current_task", "")))
    worker_profile = html.escape(str(card.get("worker_profile", "")))
    status = html.escape(str(card.get("status", "")))
    latest_test = html.escape(str(card.get("latest_test_result", "")))
    branch = html.escape(str(card.get("branch", "")))
    head = html.escape(short_text(str(card.get("head", ""))))
    pending = "yes" if card.get("pending_approval") else "no"
    clean = "yes" if card.get("working_tree_clean") else "no"

    return (
        f'<section class="link-worker-dashboard-card" data-version="{version}">\n'
        "  <h2>Link Worker Dashboard Card</h2>\n"
        f"  <p><strong>Task:</strong> {current_task}</p>\n"
        f"  <p><strong>Worker profile:</strong> <code>{worker_profile}</code></p>\n"
        f"  <p><strong>Status:</strong> {status}</p>\n"
        f"  <p><strong>Pending approval:</strong> {pending}</p>\n"
        f"  <p><strong>Latest test:</strong> <code>{latest_test}</code></p>\n"
        f"  <p><strong>Branch:</strong> <code>{branch}</code></p>\n"
        f"  <p><strong>HEAD:</strong> <code>{head}</code></p>\n"
        f"  <p><strong>Working tree clean:</strong> {clean}</p>\n"
        "  <h3>Visible Tools</h3>\n"
        f"  <ul>{tools}</ul>\n"
        "</section>"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a Link worker dashboard card.")
    parser.add_argument("--task", "--current-task", dest="current_task", required=True)
    parser.add_argument("--profile", default="patch_worker")
    parser.add_argument("--pending-approval", action="store_true")
    parser.add_argument("--latest-test-result", default="unknown")
    parser.add_argument("--root", default=".")
    parser.add_argument("--format", choices=["markdown", "json", "html"], default="markdown")
    args = parser.parse_args()

    card = build_worker_dashboard_card(
        Path(args.root),
        current_task=args.current_task,
        worker_profile=args.profile,
        pending_approval=args.pending_approval,
        latest_test_result=args.latest_test_result,
    )

    problems = validate_worker_dashboard_card(card)
    card["validation_problems"] = problems
    card["ok"] = not problems

    if args.format == "json":
        print(json.dumps(card, indent=2, sort_keys=True))
    elif args.format == "html":
        print(render_worker_dashboard_html(card))
    else:
        print(render_worker_dashboard_markdown(card))

    return 0 if not problems else 2


if __name__ == "__main__":
    raise SystemExit(main())
