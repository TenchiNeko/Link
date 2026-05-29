#!/usr/bin/env python3
"""Link canonical CLI entrypoint.

This is the single front-door CLI for Link. It is intentionally a thin
delegating layer: each subcommand forwards to an existing, working module
without changing its behavior. No patches, commits, pushes, or destructive
actions happen here.

The goal of this module is architectural clarity, not new behavior. As Link
migrates toward the clean ``link_core`` / ``link_modes`` structure, this file
stays the stable command surface while the modules underneath are reorganized.

Usage:
    python3 link.py <command> [args...]
    python3 link.py --help
    python3 link.py <command> --help
"""

from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent


# Commands that delegate to an external module's main() with adjusted argv.
_DELEGATED_COMMANDS: dict[str, tuple[str, str, str]] = {
    "status": ("link_status", "main", "Check Link runtime/model/web endpoints."),
    "doctor": (
        "link_core.diagnostics.link_doctor",
        "main",
        "Full Link diagnostics dashboard.",
    ),
    "agents": ("link_agents", "main", "List Link agent/model configuration sources."),
    "engine": ("link_engine", "main", "Supervised Link run engine."),
    "route": (
        "link_core.routing.link_route_intelligence",
        "main",
        "Deterministic pre-run route intelligence.",
    ),
    "control-plane": (
        "link_core.control_plane.link_control_plane_cli",
        "main",
        "Link control-plane report/status CLI.",
    ),
    "grade": (
        "link_core.ops.link_grade",
        "main",
        "Generate branch/internal/market grade report.",
    ),
}


def _delegate(module_path: str, attr: str, argv: list[str]) -> int:
    """Call a delegated module's main() with a temporarily adjusted argv."""
    module = importlib.import_module(module_path)
    func: Callable[..., int] = getattr(module, attr)

    saved_argv = sys.argv
    sys.argv = [module_path, *argv]
    try:
        result = func()
    finally:
        sys.argv = saved_argv

    return int(result or 0)


def _run_healthcheck(argv: list[str]) -> int:
    """Run the canonical healthcheck as a subprocess (never imported here)."""
    cmd = [sys.executable, str(ROOT / "link_healthcheck.py"), *argv]
    proc = subprocess.run(cmd, cwd=str(ROOT), check=False)
    return proc.returncode


# ---------------------------------------------------------------------------
# Local commands implemented inline using canonical facade imports.
# ---------------------------------------------------------------------------


def _cmd_modes(argv: list[str]) -> int:
    """Print available Link operating modes."""
    import json as _json

    from link_core.modes import list_modes as _list_modes

    modes = _list_modes()
    if "--json" in argv:
        print(_json.dumps(modes, indent=2))
        return 0

    for mode in modes:
        name = mode["name"]
        title = mode["title"]
        desc = mode["description"][:90]
        print(f"{name.ljust(12)}{title} -- {desc}")
    return 0


def _cmd_roles(argv: list[str]) -> int:
    """Print worker profiles and business/factory roles."""
    import json as _json

    from link_core.roles import list_business_roles as _business_roles
    from link_core.roles import list_worker_profile_names as _worker_names

    worker_names = _worker_names()
    business = _business_roles()

    if "--json" in argv:
        print(_json.dumps({
            "worker_profiles": worker_names,
            "business_roles": [
                {
                    "role_id": role.get("role_id", ""),
                    "title": role.get("title", ""),
                    "department": role.get("department", ""),
                }
                for role in business
            ],
        }, indent=2))
        return 0

    print("Worker profiles:")
    for name in worker_names:
        print(f"  - {name}")

    if business:
        print("")
        print("Business roles:")
        for role in business:
            role_id = role.get("role_id", "")
            title = role.get("title", "")
            dept = role.get("department", "")
            print(f"  - {role_id.ljust(22)}{title.ljust(24)}({dept})")
    return 0


def _cmd_dashboard(argv: list[str]) -> int:
    """Print a compact dashboard/status summary."""
    from link_core.dashboard import collect as _collect
    from link_core.dashboard import print_human as _print_human

    data = _collect()
    if data is None:
        print("dashboard: could not collect diagnostics data", file=sys.stderr)
        return 1

    if "--json" in argv:
        import json as _json
        print(_json.dumps(data, indent=2, default=str))
        return 0

    _print_human(data)
    return 0


def _cmd_self_test(argv: list[str]) -> int:
    """Run canonical architecture smoke checks (import + CLI)."""
    try:
        from tests.test_canonical_architecture import main as _run_smoke
    except ImportError as exc:
        print(f"link self-test: cannot import smoke test: {exc}", file=sys.stderr)
        return 1

    try:
        _run_smoke()
    except AssertionError as exc:
        print(f"link self-test FAILED: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"link self-test ERROR: {exc}", file=sys.stderr)
        return 1

    print("link self-test passed")
    return 0


# Local commands: (function, help_text). Functions receive the remaining argv.
_LOCAL_COMMANDS: dict[str, tuple[Callable[[list[str]], int], str]] = {
    "modes": (_cmd_modes, "List Link operating modes (base/growth/business)."),
    "roles": (_cmd_roles, "List worker safety profiles and business roles."),
    "dashboard": (_cmd_dashboard, "Compact diagnostics dashboard."),
    "self-test": (_cmd_self_test, "Run canonical architecture smoke checks."),
}


def _print_help() -> None:
    print("Link canonical CLI")
    print("")
    print("Usage:")
    print("  python3 link.py <command> [args...]")
    print("")
    print("Commands:")
    all_names = list(_DELEGATED_COMMANDS) + list(_LOCAL_COMMANDS) + ["healthcheck"]
    width = max(len(name) for name in all_names)
    for name, (_, _, help_text) in _DELEGATED_COMMANDS.items():
        print(f"  {name.ljust(width)}  {help_text}")
    for name, (_, help_text) in _LOCAL_COMMANDS.items():
        print(f"  {name.ljust(width)}  {help_text}")
    print(f"  {'healthcheck'.ljust(width)}  Run the Link healthcheck (preserves baseline).")
    print("")
    print("Run 'python3 link.py <command> --help' for command-specific help.")


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)

    if not args or args[0] in {"-h", "--help", "help"}:
        _print_help()
        return 0

    command, rest = args[0], args[1:]

    if command == "healthcheck":
        return _run_healthcheck(rest)

    if command in _DELEGATED_COMMANDS:
        module_path, attr, _ = _DELEGATED_COMMANDS[command]
        return _delegate(module_path, attr, rest)

    if command in _LOCAL_COMMANDS:
        func, _ = _LOCAL_COMMANDS[command]
        return func(rest)

    print(f"link: unknown command: {command}", file=sys.stderr)
    print("Run 'python3 link.py --help' for the command list.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
