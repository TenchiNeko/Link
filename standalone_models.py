"""Compatibility shim for moved standalone module.

Canonical module:
    link_core.standalone.standalone_models
"""

from __future__ import annotations

# runpy.run_path compatibility marker
import runpy as _runpy
from importlib import import_module as _import_module

_CANONICAL_MODULE = "link_core.standalone.standalone_models"

if __name__ == "__main__":
    _runpy.run_module(_CANONICAL_MODULE, run_name="__main__", alter_sys=True)
else:
    _module = _import_module(_CANONICAL_MODULE)
    for _name, _value in vars(_module).items():
        if _name not in {"__name__", "__package__", "__loader__", "__spec__"}:
            globals()[_name] = _value
