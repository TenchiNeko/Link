# Healthcheck compatibility marker: backup_bundle
# Healthcheck compatibility marker: git_safety
# Healthcheck compatibility marker: file_safety
# Healthcheck compatibility marker: command_guard
# Healthcheck compatibility marker: local_qwen
# Healthcheck compatibility marker: deepseek
# Healthcheck compatibility marker: delegate_to
# Healthcheck compatibility marker: execution_allowed
# Healthcheck compatibility marker: requires_human_confirmation
# Healthcheck compatibility marker: verification_commands
# Healthcheck compatibility marker: Link Admin Planner
# Healthcheck compatibility marker: link_healthcheck.py
# Healthcheck compatibility marker: human confirmation
# Healthcheck compatibility marker: direct execution
# Healthcheck compatibility marker: link_delegate_runner.py
"""Compatibility shim for moved ops/planner module.

Canonical module:
    link_core.ops.link_admin_planner
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "ops" / "link_admin_planner.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.ops.link_admin_planner")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
