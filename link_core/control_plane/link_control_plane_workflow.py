"""Canonical Link control-plane workflow stages.

This module is intentionally small. It defines the stable vocabulary for the
future upgrade-agent control plane without executing patches or mutating state.
"""

from __future__ import annotations

from typing import Final


CONTROL_PLANE_STAGES: Final[tuple[str, ...]] = (
    "ResearchIngest",
    "CandidateExtractor",
    "FeasibilityReviewer",
    "ProposalWriter",
    "HumanApproval",
    "PatchPlanner",
    "PatchWorker",
    "Verifier",
    "Finalizer",
)

# Backward/simple alias for smoke tests and delegate recommendations.
STAGES: Final[tuple[str, ...]] = CONTROL_PLANE_STAGES

TRANSITIONS: Final[dict[str, tuple[str, ...]]] = {
    "ResearchIngest": ("CandidateExtractor",),
    "CandidateExtractor": ("FeasibilityReviewer",),
    "FeasibilityReviewer": ("ProposalWriter", "ResearchIngest"),
    "ProposalWriter": ("HumanApproval",),
    "HumanApproval": ("PatchPlanner", "ProposalWriter"),
    "PatchPlanner": ("PatchWorker",),
    "PatchWorker": ("Verifier",),
    "Verifier": ("Finalizer", "PatchWorker"),
    "Finalizer": (),
}

CONTROL_PLANE_PROMPT_MARKERS: Final[tuple[str, ...]] = (
    "project factory",
    "factory planning",
    "factory dry-run",
    "control-plane proposal",
    "control plane proposal",
    "control-plane workflow",
    "control plane workflow",
    "framework ingestion",
    "upgrade proposal",
    "researching research/",
)


def get_control_plane_stages() -> tuple[str, ...]:
    """Return the ordered canonical control-plane stages."""
    return CONTROL_PLANE_STAGES


def validate_stage(stage: str) -> bool:
    """Return True when *stage* is a known control-plane stage."""
    return stage in CONTROL_PLANE_STAGES


def next_stage(stage: str) -> tuple[str, ...]:
    """Return allowed next stages for a known stage."""
    if stage not in TRANSITIONS:
        raise ValueError(f"unknown control-plane stage: {stage}")
    return TRANSITIONS[stage]


def is_control_plane_prompt(prompt: str) -> bool:
    """Detect prompts that should use control-plane/factory routing before audit."""
    text = (prompt or "").lower()
    return any(marker in text for marker in CONTROL_PLANE_PROMPT_MARKERS)


def assert_valid_workflow() -> None:
    """Raise AssertionError if the workflow definition is internally invalid."""
    assert len(CONTROL_PLANE_STAGES) == 9
    assert CONTROL_PLANE_STAGES[0] == "ResearchIngest"
    assert CONTROL_PLANE_STAGES[-1] == "Finalizer"
    assert set(TRANSITIONS) == set(CONTROL_PLANE_STAGES)

    known = set(CONTROL_PLANE_STAGES)
    for stage, destinations in TRANSITIONS.items():
        assert stage in known
        for destination in destinations:
            assert destination in known, f"{stage} points to unknown stage {destination}"

    assert "CandidateExtractor" in TRANSITIONS["ResearchIngest"]
    assert "HumanApproval" in TRANSITIONS["ProposalWriter"]
    assert "PatchPlanner" in TRANSITIONS["HumanApproval"]
    assert "Finalizer" in TRANSITIONS["Verifier"]
