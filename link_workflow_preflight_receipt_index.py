"""Compatibility shim for moved workflow module.

Canonical module:
    link_core.workflow.link_workflow_preflight_receipt_index
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "workflow" / "link_workflow_preflight_receipt_index.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_core.workflow.link_workflow_preflight_receipt_index import *  # noqa: F401,F403
