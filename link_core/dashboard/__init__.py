"""Canonical Link dashboard facade.

Import path: ``link_core.dashboard``

This package is the canonical single dashboard API/view. It is a thin facade
over the existing diagnostics dashboard:

- ``link_core.diagnostics.link_doctor`` (full repo/engine/web/endpoint view)

No behavior is changed here. ``collect`` gathers a read-only diagnostics
snapshot and ``print_human`` renders it. Existing worker/recovery dashboard
helpers continue to live in this package's submodules unchanged.
"""

from __future__ import annotations

# The diagnostics dashboard pulls in several discovery modules. Import
# defensively so a single optional dependency never breaks the facade import.
try:  # pragma: no cover - defensive import
    from link_core.diagnostics.link_doctor import collect, print_human
except Exception:  # pragma: no cover
    collect = None  # type: ignore[assignment]
    print_human = None  # type: ignore[assignment]

__all__ = [
    "collect",
    "print_human",
]
