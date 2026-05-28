"""Compatibility shim for moved dashboard module.

Canonical module:
    link_core.dashboard.latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "dashboard" / "latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.dashboard.latest_recovery_plan_dashboard_receipt_evidence_index_execution_receipt_evidence_index")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
