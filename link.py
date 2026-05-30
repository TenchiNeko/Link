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


def _cmd_config(argv: list[str]) -> int:
    """Read and validate Link YAML configuration files."""
    try:
        import yaml as _yaml
    except ImportError:
        print("config: PyYAML is not installed. Install with: pip install pyyaml", file=sys.stderr)
        return 1

    import json as _json

    config_root = ROOT / "configs"
    config_files = [
        ("configs/models.yaml", "Model routing", "models.yaml"),
        ("configs/teams/link_growth.yaml", "Growth team", "link_growth.yaml"),
        ("configs/teams/business_ops.yaml", "Business ops team", "business_ops.yaml"),
    ]

    file_results: list[dict] = []
    checks: list[dict] = []
    problems = 0

    for rel_path, label, basename in config_files:
        full_path = ROOT / rel_path
        entry: dict = {"label": label, "path": rel_path, "exists": False}
        if not full_path.is_file():
            entry["status"] = "missing"
            problems += 1
            file_results.append(entry)
            continue
        entry["exists"] = True
        try:
            data = _yaml.safe_load(full_path.read_text(encoding="utf-8"))
        except Exception as exc:
            entry["status"] = "parse_error"
            entry["error"] = str(exc)
            problems += 1
            file_results.append(entry)
            continue
        version = data.get("version", "unknown") if isinstance(data, dict) else "unknown"
        entry["status"] = "ok"
        entry["version"] = version
        entry["top_keys"] = list(data.keys()) if isinstance(data, dict) else []
        file_results.append(entry)

    # Model profiles consistency check.
    try:
        from link_core.router import model_profile_map as _runtime_profiles

        runtime_names = set(_runtime_profiles().keys())
        models_yaml = config_root / "models.yaml"
        if models_yaml.is_file():
            yaml_data = _yaml.safe_load(models_yaml.read_text(encoding="utf-8"))
            yaml_profiles = yaml_data.get("profiles", {}) if isinstance(yaml_data, dict) else {}
            yaml_names = set(yaml_profiles.keys())
            match = yaml_names == runtime_names
            checks.append({
                "label": "model profiles match runtime",
                "ok": match,
                "detail": f"{len(runtime_names)} runtime profiles, {len(yaml_names)} in yaml",
            })
            if not match:
                checks[-1]["yaml_only"] = sorted(yaml_names - runtime_names)
                checks[-1]["runtime_only"] = sorted(runtime_names - yaml_names)
                problems += 1
    except Exception as exc:
        checks.append({"label": "model profiles match runtime", "ok": False, "detail": str(exc)})
        problems += 1

    # Growth control-plane stages check.
    try:
        from link_core.control_plane import get_control_plane_stages as _runtime_stages

        growth_yaml = config_root / "teams" / "link_growth.yaml"
        if growth_yaml.is_file():
            yaml_data = _yaml.safe_load(growth_yaml.read_text(encoding="utf-8"))
            yaml_stages = yaml_data.get("control_plane_stages", []) if isinstance(yaml_data, dict) else []
            runtime_stages = list(_runtime_stages())
            match = yaml_stages == runtime_stages
            checks.append({
                "label": "growth control-plane stages match runtime",
                "ok": match,
                "detail": f"{len(runtime_stages)} runtime stages, {len(yaml_stages)} in yaml",
            })
            if not match:
                problems += 1
    except Exception as exc:
        checks.append({"label": "growth control-plane stages match runtime", "ok": False, "detail": str(exc)})
        problems += 1

    # Business tiers check.
    try:
        from link_core.roles import business_tier_names as _runtime_tiers

        biz_yaml = config_root / "teams" / "business_ops.yaml"
        if biz_yaml.is_file():
            yaml_data = _yaml.safe_load(biz_yaml.read_text(encoding="utf-8"))
            yaml_tiers = yaml_data.get("tiers", []) if isinstance(yaml_data, dict) else []
            runtime_tier_list = _runtime_tiers()
            runtime_tier_set = set(runtime_tier_list)
            missing = [t for t in yaml_tiers if t not in runtime_tier_set]
            ok = len(missing) == 0
            checks.append({
                "label": "business tiers in yaml present in runtime",
                "ok": ok,
                "detail": f"{len(yaml_tiers)} tiers in yaml, {len(runtime_tier_list)} in runtime",
            })
            if not ok:
                checks[-1]["missing"] = missing
                problems += 1
    except Exception as exc:
        checks.append({"label": "business tiers in yaml present in runtime", "ok": False, "detail": str(exc)})
        problems += 1

    result = {
        "config_files": file_results,
        "consistency_checks": checks,
        "all_ok": problems == 0,
    }

    if "--json" in argv:
        print(_json.dumps(result, indent=2))
        return 0 if result["all_ok"] else 1

    print("Link configuration")
    print("")
    print("Config files:")
    for entry in file_results:
        status = entry.get("status", "?")
        label = entry.get("label", entry.get("path", "?"))
        if status == "ok":
            print(f"  OK: {label} ({entry.get('version', '?')})")
        elif status == "missing":
            print(f"  MISSING: {entry['path']}")
        else:
            print(f"  ERROR: {label} - {entry.get('error', status)}")

    print("")
    print("Consistency:")
    for check in checks:
        indicator = "OK" if check["ok"] else "DRIFT"
        print(f"  {indicator}: {check['label']} ({check.get('detail', '')})")
        if not check["ok"]:
            for extra_key in ("yaml_only", "runtime_only", "missing"):
                if extra_key in check:
                    print(f"    {extra_key}: {check[extra_key]}")

    print("")
    if problems == 0:
        print("config OK")
    else:
        print(f"config FAILED ({problems} problem(s))")
    return 0 if problems == 0 else 1


def _cmd_growth(argv: list[str]) -> int:
    """Growth mode subcommand dispatcher.

    Usage: python3 link.py growth <subcommand> [args...]

    Subcommands:
      status     Render a read-only Growth mode status console.
      proposals  View control-plane proposal cards.
      propose    Mine research into proposals (dry-run by default).
      approve    Accept a pending proposal.
      reject     Reject a pending proposal.
    """
    subcommand = argv[0] if argv else ""
    if subcommand in ("status", "--json", ""):
        from link_modes.growth.link_growth_console import main as _growth_main

        return _growth_main(argv if subcommand == "status" else [])
    if subcommand == "proposals":
        from link_modes.growth.link_growth_console import proposals_main as _growth_proposals_main

        return _growth_proposals_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "propose":
        from link_modes.growth.link_growth_console import propose_main as _growth_propose_main

        return _growth_propose_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "approve":
        from link_modes.growth.link_growth_console import approve_main as _growth_approve_main

        return _growth_approve_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "reject":
        from link_modes.growth.link_growth_console import reject_main as _growth_reject_main

        return _growth_reject_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "handoff":
        from link_modes.growth.link_growth_console import handoff_main as _growth_handoff_main

        return _growth_handoff_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "handoffs":
        from link_modes.growth.link_growth_console import handoffs_main as _growth_handoffs_main

        return _growth_handoffs_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "execute":
        from link_modes.growth.link_growth_console import execute_main as _growth_execute_main

        return _growth_execute_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "receipts":
        from link_modes.growth.link_growth_console import receipts_main as _growth_receipts_main

        return _growth_receipts_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-inventory":
        from link_modes.growth.link_growth_console import archive_inventory_main as _growth_archive_inventory_main

        return _growth_archive_inventory_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-extract":
        from link_modes.growth.link_growth_console import archive_extract_main as _growth_archive_extract_main

        return _growth_archive_extract_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-catalog":
        from link_modes.growth.link_growth_console import archive_catalog_main as _growth_archive_catalog_main

        return _growth_archive_catalog_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "archive-queue":
        from link_modes.growth.link_growth_console import archive_queue_main as _growth_archive_queue_main

        return _growth_archive_queue_main(argv[1:] if len(argv) > 1 else [])
    if subcommand == "run":
        from link_modes.growth.link_growth_console import run_main as _growth_run_main

        return _growth_run_main(argv[1:] if len(argv) > 1 else [])
    if subcommand in ("-h", "--help", "help"):
        print("Growth mode commands:")
        print("  status             Render Growth mode status console")
        print("  proposals          View control-plane proposal cards")
        print("  propose            Mine research into proposals")
        print("  approve            Accept a pending proposal")
        print("  reject             Reject a pending proposal")
        print("  handoff            Create a worker handoff from an accepted proposal")
        print("  handoffs           View existing worker handoffs")
        print("  execute            Prepare handoff for verification")
        print("  receipts           View verifier receipts")
        print("  archive-inventory  Scan research archives without extraction")
        print("  archive-extract    Safely extract a research archive")
        print("  archive-catalog    Catalog extracted research contents")
        print("  archive-queue      Rank extracted sources for mining")
        print("  run                Guided Growth workflow dashboard")
        return 0
    print(f"growth: unknown subcommand: {subcommand}", file=sys.stderr)
    print("Run 'python3 link.py growth --help' for subcommands.", file=sys.stderr)
    return 2


# Local commands: (function, help_text). Functions receive the remaining argv.
_LOCAL_COMMANDS: dict[str, tuple[Callable[[list[str]], int], str]] = {
    "modes": (_cmd_modes, "List Link operating modes (base/growth/business)."),
    "roles": (_cmd_roles, "List worker safety profiles and business roles."),
    "dashboard": (_cmd_dashboard, "Compact diagnostics dashboard."),
    "self-test": (_cmd_self_test, "Run canonical architecture smoke checks."),
    "config": (_cmd_config, "Validate Link configuration files against runtime."),
    "growth": (_cmd_growth, "Growth mode terminal console."),
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
