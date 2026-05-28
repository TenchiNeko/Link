# Healthcheck compatibility marker: _MICRO_PATCH_FILE_RE
# Healthcheck compatibility marker: def is_micro_patch_prompt
# Healthcheck compatibility marker: def _strip_link_engine_policy_block
# Healthcheck compatibility marker: def is_read_only_prompt
"""Compatibility shim for moved runtime module.

Canonical module:
    link_core.runtime.link_runtime_policy
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "runtime" / "link_runtime_policy.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.runtime.link_runtime_policy")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
