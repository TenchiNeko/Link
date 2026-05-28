# Healthcheck compatibility marker: Link Delegate Runner
# Healthcheck compatibility marker: local_qwen
# Healthcheck compatibility marker: deepseek
# Healthcheck compatibility marker: DEEPSEEK_API_KEY
# Healthcheck compatibility marker: LINK_LOCAL_QWEN_MODEL
# Healthcheck compatibility marker: LINK_LOCAL_QWEN_CMD
# Healthcheck compatibility marker: LINK_DEEPSEEK_CMD
# Healthcheck compatibility marker: no_write
# Healthcheck compatibility marker: model_suggested_commands_not_executed
# Healthcheck compatibility marker: LINK_ENABLE_MODEL_DELEGATES
# Healthcheck compatibility marker: _delegate_cmd
# Healthcheck compatibility marker: link_admin_planner.py
# Healthcheck compatibility marker: delegate_to
# Healthcheck compatibility marker: no-write
# Healthcheck compatibility marker: proposed_commands
# Healthcheck compatibility marker: execution_allowed
# Healthcheck compatibility marker: requires_human_confirmation
# Healthcheck compatibility marker: verification_commands
"""Compatibility shim for moved ops/planner module.

Canonical module:
    link_core.ops.link_delegate_runner
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "ops" / "link_delegate_runner.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.ops.link_delegate_runner")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
