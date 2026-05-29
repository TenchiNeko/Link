"""Compatibility shim for moved dashboard module.

Canonical module:
    link_core.dashboard.latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration
"""

from link_core.dashboard.latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    from pathlib import Path
    runpy.run_path(
        str(Path(__file__).resolve().parent / "link_core" / "dashboard" / "latest_recovery_plan_dashboard_receipt_evidence_index_web_admin_integration.py"),
        run_name="__main__",
    )
