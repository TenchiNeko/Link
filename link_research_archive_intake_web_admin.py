"""Compatibility shim for moved Growth Link module.

Canonical module:
    link_modes.growth.link_research_archive_intake_web_admin
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_modes" / "growth" / "link_research_archive_intake_web_admin.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from importlib import import_module as _import_module

    _module = _import_module("link_modes.growth.link_research_archive_intake_web_admin")
    for _name, _value in vars(_module).items():
        if not (_name.startswith("__") and _name.endswith("__")):
            globals()[_name] = _value

    del _import_module, _module, _name, _value
