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


# Each command maps to (module_path, attribute, one-line help).
# Modules are imported lazily so one broken dependency never breaks the whole CLI.
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


def _print_help() -> None:
    print("Link canonical CLI")
    print("")
    print("Usage:")
    print("  python3 link.py <command> [args...]")
    print("")
    print("Commands:")
    width = max(len(name) for name in (*_DELEGATED_COMMANDS, "healthcheck"))
    for name, (_, _, help_text) in _DELEGATED_COMMANDS.items():
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

    print(f"link: unknown command: {command}", file=sys.stderr)
    print("Run 'python3 link.py --help' for the command list.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
