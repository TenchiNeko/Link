"""Canonical Link task routing facade.

Import path: ``link_core.router``

Link routing has two layers that this facade unifies:

1. Run routing: deciding whether a prompt should take the read-only audit
   fastpath, a micro patch, or a full autonomous run
   (``link_core.routing.link_route_intelligence``).

2. Model routing: choosing a model profile (local-fast, local-deep,
   cloud-deep, hybrid fallback) for a goal
   (``link_core.routing.link_model_routing_profiles``).

This module is a thin facade. It performs no source edits. ``decide_route``
may trigger the existing read-only specialist fanout, which only writes normal
generated artifacts under ``.agents``.
"""

from __future__ import annotations

from typing import Any

# --- Run routing ------------------------------------------------------------
from link_core.routing.link_route_intelligence import (
    ROUTE_RUNNERS,
    decide_route,
)

# --- Model routing ----------------------------------------------------------
from link_core.routing.link_model_routing_profiles import (
    ROUTING_PROFILES,
    ModelRoutingProfile,
    all_profile_summaries as all_model_profile_summaries,
    fallback_chain as model_fallback_chain,
    get_profile as get_model_profile,
    profile_map as model_profile_map,
    select_routing_profile as select_model_routing_profile,
    validate_model_routing_profiles,
)


def route_summary(prompt: str, *, run_fanout: bool = False) -> dict[str, Any]:
    """Return a combined run-route + model-route summary for a prompt.

    ``run_fanout`` defaults to False so this stays a cheap, side-effect-light
    call suitable for previews. Set it True to trigger the read-only fanout.
    """
    run = decide_route(prompt, run_fanout=run_fanout)
    model = select_model_routing_profile(prompt)
    return {
        "prompt_hash": run.get("prompt_hash"),
        "run_route": run.get("route"),
        "run_runner": run.get("runner"),
        "run_confidence": run.get("confidence"),
        "model_profile": model.get("selected_profile"),
        "model_provider": model.get("provider"),
        "model_default": model.get("default_model"),
        "model_fallback_chain": model.get("fallback_chain", []),
    }


__all__ = [
    # run routing
    "ROUTE_RUNNERS",
    "decide_route",
    # model routing
    "ROUTING_PROFILES",
    "ModelRoutingProfile",
    "all_model_profile_summaries",
    "model_fallback_chain",
    "get_model_profile",
    "model_profile_map",
    "select_model_routing_profile",
    "validate_model_routing_profiles",
    # combined
    "route_summary",
]
