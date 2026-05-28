"""Compatibility shim for moved ops/planner module.

Canonical module:
    link_core.ops.runtime_legacy_audit
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "ops" / "runtime_legacy_audit.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.ops.runtime_legacy_audit import *  # noqa: F401,F403
