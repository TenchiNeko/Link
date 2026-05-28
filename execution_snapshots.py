"""Compatibility shim for moved evidence/execution module.

Canonical module:
    link_core.evidence.execution_snapshots
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "evidence" / "execution_snapshots.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.evidence.execution_snapshots import *  # noqa: F401,F403
