"""Canonical Link agent registry facade.

Import path: ``link_core.agents``

This package is the canonical home for agent identity and agent/model
configuration discovery. It is a thin facade over existing working modules:

- ``link_core.agents.link_agent_identity`` (deterministic per-role identity)
- ``link_agents`` (static agent/model configuration discovery)

No behavior is changed here. These re-exports give callers one stable import
location while the underlying modules are migrated toward the final
architecture.
"""

from __future__ import annotations

from link_core.agents.link_agent_identity import (
    deterministic_agent_id,
    ensure_memory_tree,
    ensure_role_identity,
    identity_path,
    list_identities,
    role_dir,
    safe_role_id,
)

# Static agent/model configuration discovery lives in the top-level shim,
# which forwards to its canonical implementation. Import defensively so a
# discovery dependency issue never breaks identity imports.
try:  # pragma: no cover - defensive import
    from link_agents import collect as collect_agent_sources
    from link_agents import extract_names as extract_agent_names
except Exception:  # pragma: no cover - discovery is optional at import time
    collect_agent_sources = None  # type: ignore[assignment]
    extract_agent_names = None  # type: ignore[assignment]

__all__ = [
    "deterministic_agent_id",
    "ensure_memory_tree",
    "ensure_role_identity",
    "identity_path",
    "list_identities",
    "role_dir",
    "safe_role_id",
    "collect_agent_sources",
    "extract_agent_names",
]
