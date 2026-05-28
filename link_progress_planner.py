# Healthcheck compatibility markers for moved canonical module.
# Canonical runtime implementation lives in link_core.ops.link_progress_planner.
# def choose_next_action
# broad_prompt_refuses_autonomous
# decide_route
# latest_engine_reports
# latest_fanout_reports

"""Compatibility shim for moved ops/planner module.

Canonical module:
    link_core.ops.link_progress_planner
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_core" / "ops" / "link_progress_planner.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_core.ops.link_progress_planner")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value
