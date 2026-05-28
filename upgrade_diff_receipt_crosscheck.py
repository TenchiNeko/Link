"""Compatibility shim for moved Growth Link module.

Canonical module:
    link_modes.growth.upgrade_diff_receipt_crosscheck
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_modes" / "growth" / "upgrade_diff_receipt_crosscheck.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_modes.growth.upgrade_diff_receipt_crosscheck import *  # noqa: F401,F403
