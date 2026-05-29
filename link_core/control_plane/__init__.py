"""Canonical Link control-plane facade.

Import path: ``link_core.control_plane``

The control plane is the proposal -> plan -> worker -> verifier -> finalizer
pipeline. This package facade exposes the stable vocabulary and artifact
helpers over existing working modules:

- ``link_control_plane_workflow`` (canonical stages + transitions)
- ``link_control_plane_proposals`` (proposal artifact registry)
- ``link_control_plane_cli`` (read-only report/status builders)

No execution, patching, or mutation happens here. These re-exports give
callers one stable import location while the underlying modules migrate
toward the final architecture.
"""

from __future__ import annotations

from link_core.control_plane.link_control_plane_workflow import (
    CONTROL_PLANE_STAGES,
    TRANSITIONS,
    get_control_plane_stages,
    is_control_plane_prompt,
    next_stage,
    validate_stage,
)
from link_core.control_plane.link_control_plane_proposals import (
    REQUIRED_PROPOSAL_FIELDS,
    list_proposals,
    load_proposal,
    make_proposal_id,
    update_proposal_status,
    validate_proposal,
    write_proposal,
)

# Read-only report/status builders are optional at import time.
try:  # pragma: no cover - defensive import
    from link_core.control_plane.link_control_plane_cli import (
        build_report,
        build_status,
    )
except Exception:  # pragma: no cover
    build_report = None  # type: ignore[assignment]
    build_status = None  # type: ignore[assignment]

__all__ = [
    "CONTROL_PLANE_STAGES",
    "TRANSITIONS",
    "get_control_plane_stages",
    "is_control_plane_prompt",
    "next_stage",
    "validate_stage",
    "REQUIRED_PROPOSAL_FIELDS",
    "list_proposals",
    "load_proposal",
    "make_proposal_id",
    "update_proposal_status",
    "validate_proposal",
    "write_proposal",
    "build_report",
    "build_status",
]
