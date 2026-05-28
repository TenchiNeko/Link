"""Compatibility shim for moved dashboard module.

Canonical module:
    link_core.dashboard.link_worker_dashboard_evidence_index
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "dashboard" / "link_worker_dashboard_evidence_index.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.dashboard.link_worker_dashboard_evidence_index import *  # noqa: F401,F403
