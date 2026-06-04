#!/usr/bin/env python3
"""Growth mode pipeline smoke tests -- Phase 2 first reliability slice.

Scope (read-only, temp-dir only, no network, no subprocess, no source edits):
- link_modes.growth facade exports its documented public surface
- link_research_upgrade_miner produces structured candidates with required fields
  from synthetic research input (deterministic, no .link/ mutations)
- link_research_archive_miner stages a temp zip and produces findings + agent jobs
- link_approved_research_handoff_executor converts a synthetic approved draft
  into a handoff receipt (temp dir only, no real .link/ writes)
- link_self_learning_dashboard.build_dashboard returns a dict with required keys
- link_core.control_plane.validate_proposal accepts a well-formed proposal dict

Known gap (documented, not fixed here):
- The upgrade miner produces *candidates* with a different schema than the
  control-plane *proposal* schema required by validate_proposal.
  A raw miner candidate is missing fields like proposal_id, source_path,
  source_summary, extracted_capabilities, link_takeaways, risk_level,
  recommendation, and status.
  This gap is the target of the next bridge slice. This file records the
  current behavior so a regression is caught immediately if the gap changes
  without a matching test update.

Style: if condition: raise AssertionError(msg) -- no bare assert statements.
No forbidden legacy tokens. No network. No subprocess calls.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _require(condition: bool, msg: str) -> None:
    if not condition:
        raise AssertionError(msg)


def _require_keys(d: dict[str, Any], keys: tuple[str, ...], label: str) -> None:
    for key in keys:
        if key not in d:
            raise AssertionError(f"{label} is missing required key: {key!r}")


def _sample_control_plane_proposal(
    proposal_id: str = "router-proposal-001",
    status: str = "pending",
) -> dict[str, Any]:
    return {
        "proposal_id": proposal_id,
        "title": "router smoke proposal",
        "source_path": "research/router.md",
        "source_summary": "Smoke proposal for Growth router tests.",
        "extracted_capabilities": ["router"],
        "link_takeaways": ["route next safe Growth command"],
        "affected_files": ["link_modes/growth/link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "Growth run recommends the next safe command.",
        "implementation_plan": ["Update the read-only Growth run router."],
        "verification_commands": ["python3 tests/test_growth_pipeline.py"],
        "rollback_plan": "Revert the Growth router change.",
        "recommendation": "accept",
        "status": status,
        "created_at": "2026-05-31T00:00:00",
    }


# ---------------------------------------------------------------------------
# 0. Fork lineage receipt helper -- pure model/JSON slice
# ---------------------------------------------------------------------------

def check_fork_lineage_receipt_helper() -> None:
    """Fork lineage receipts model parent/child traceability without writes."""
    from link_core.receipts import (
        FORK_LINEAGE_RECEIPT_VERSION,
        build_fork_lineage_receipt,
        fork_lineage_receipt_from_json,
        fork_lineage_receipt_to_json,
        validate_fork_lineage_receipt,
    )

    receipt = build_fork_lineage_receipt(
        parent_session_id="parent-session-001",
        child_session_id="child-session-001",
        fork_point={"message_index": 7, "run_step": "planner"},
        fork_depth=2,
        diverged=True,
        source_metadata={"source": "growth-proposal", "proposal_id": "branch-trace"},
        created_at="2026-05-31T00:00:00Z",
    )

    _require(receipt["receipt_version"] == FORK_LINEAGE_RECEIPT_VERSION,
             "fork receipt version mismatch")
    _require(receipt["parent_session_id"] == "parent-session-001",
             "parent_session_id must be preserved")
    _require(receipt["child_session_id"] == "child-session-001",
             "child_session_id must be preserved")
    _require(receipt["fork_point"]["message_index"] == 7,
             "fork_point message_index must be preserved")
    _require(receipt["fork_depth"] == 2, "fork_depth must be preserved")
    _require(receipt["diverged"] is True, "diverged must be preserved")
    _require(receipt["divergence_status"] == "diverged",
             "divergence_status must reflect diverged=True")
    _require(receipt["parent_trace"]["child_session_id"] == "child-session-001",
             "parent trace must point to child session")
    _require(receipt["child_trace"]["parent_session_id"] == "parent-session-001",
             "child trace must point back to parent session")

    encoded = fork_lineage_receipt_to_json(receipt)
    _require(encoded == fork_lineage_receipt_to_json(receipt),
             "fork receipt JSON serialization must be stable")
    decoded = fork_lineage_receipt_from_json(encoded)
    _require(decoded == receipt, "fork receipt JSON round-trip must preserve data")

    minimal = build_fork_lineage_receipt(
        parent_session_id="parent-session-002",
        child_session_id="child-session-002",
        created_at="2026-05-31T00:00:01Z",
    )
    _require(minimal["fork_point"] == {},
             "missing optional fork_point must default to empty dict")
    _require(minimal["fork_depth"] == 1,
             "missing optional fork_depth must default to 1")
    _require(minimal["diverged"] is False,
             "missing optional diverged must default to False")
    _require(minimal["source_metadata"] == {},
             "missing optional source_metadata must default to empty dict")
    validate_fork_lineage_receipt(minimal)

    try:
        build_fork_lineage_receipt(
            parent_session_id="same-session",
            child_session_id="same-session",
            created_at="2026-05-31T00:00:02Z",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("same parent/child session ids must be rejected")

    print("fork lineage receipt helper OK")


def check_transcript_snapshot_receipt_helper() -> None:
    """Transcript snapshot receipts preserve normalized messages without writes."""
    from link_core.receipts import (
        TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION,
        build_transcript_snapshot_receipt,
        transcript_snapshot_receipt_from_json,
        transcript_snapshot_receipt_to_json,
        validate_transcript_snapshot_receipt,
    )

    transcript = [
        {
            "role": "user" if index % 2 == 0 else "assistant",
            "content": f"message {index}",
            "message_index": index,
        }
        for index in range(10)
    ]
    receipt = build_transcript_snapshot_receipt(
        parent_session_id="parent-session-001",
        source_session_id="source-session-001",
        transcript_entries=transcript,
        fork_depth=3,
        metadata={"source": "growth-proposal", "proposal_id": "transcript-copy"},
        copied_at="2026-05-31T00:00:00Z",
    )
    same_receipt = build_transcript_snapshot_receipt(
        parent_session_id="parent-session-001",
        source_session_id="source-session-001",
        transcript_entries=transcript,
        fork_depth=3,
        metadata={"source": "growth-proposal", "proposal_id": "transcript-copy"},
        copied_at="2026-05-31T00:00:01Z",
    )

    _require(receipt["receipt_version"] == TRANSCRIPT_SNAPSHOT_RECEIPT_VERSION,
             "transcript snapshot receipt version mismatch")
    _require(receipt["parent_session_id"] == "parent-session-001",
             "parent_session_id must be preserved")
    _require(receipt["source_session_id"] == "source-session-001",
             "source_session_id must be preserved")
    _require(receipt["snapshot_id"] == same_receipt["snapshot_id"],
             "snapshot_id must be deterministic for the same source transcript")
    _require(receipt["fork_depth"] == 3, "fork_depth must be preserved")
    _require(receipt["message_count"] == 10,
             "message_count must match transcript length")
    _require(receipt["transcript_entries"] == transcript,
             "transcript entries must be preserved as dictionaries")
    _require(receipt["metadata"]["proposal_id"] == "transcript-copy",
             "optional metadata must be preserved")

    encoded = transcript_snapshot_receipt_to_json(receipt)
    _require(encoded == transcript_snapshot_receipt_to_json(receipt),
             "transcript snapshot JSON serialization must be stable")
    decoded = transcript_snapshot_receipt_from_json(encoded)
    _require(decoded == receipt,
             "transcript snapshot JSON round-trip must preserve data")
    validate_transcript_snapshot_receipt(receipt)

    try:
        build_transcript_snapshot_receipt(
            source_session_id="source-session-001",
            transcript_entries=transcript,
            fork_depth=-1,
            copied_at="2026-05-31T00:00:02Z",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("negative fork_depth must be rejected")

    for bad_entries in (
        "not-a-list",
        [{"role": "user"}],
        [{"content": "missing role"}],
        ["not-a-dict"],
    ):
        try:
            build_transcript_snapshot_receipt(
                source_session_id="source-session-001",
                transcript_entries=bad_entries,
                copied_at="2026-05-31T00:00:03Z",
            )
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid transcript entries must be rejected: {bad_entries!r}")

    try:
        build_transcript_snapshot_receipt(
            source_session_id="",
            transcript_entries=transcript,
            copied_at="2026-05-31T00:00:04Z",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("missing source session must be rejected")

    print("transcript snapshot receipt helper OK")


# ---------------------------------------------------------------------------
# 1. Growth facade surface
# ---------------------------------------------------------------------------

def check_growth_facade() -> None:
    """Growth __init__ exposes its canonical public surface."""
    import link_modes.growth as growth

    declared = getattr(growth, "__all__", None)
    if declared is None:
        raise AssertionError("link_modes.growth is missing __all__")

    for name in ("MODE_NAME", "TEAM_CONFIG", "describe", "control_plane_stages"):
        if name not in declared:
            raise AssertionError(f"link_modes.growth.__all__ is missing {name!r}")
        if not hasattr(growth, name):
            raise AssertionError(f"link_modes.growth does not define {name!r}")

    _require(growth.MODE_NAME == "growth", "MODE_NAME must be 'growth'")
    _require(growth.TEAM_CONFIG == "configs/teams/link_growth.yaml",
             f"TEAM_CONFIG unexpected value: {growth.TEAM_CONFIG!r}")

    desc = growth.describe()
    _require(isinstance(desc, dict), "describe() must return a dict")
    _require(desc.get("name") == "growth", "describe() name must be 'growth'")
    _require("title" in desc, "describe() must include 'title'")
    _require("entrypoint_module" in desc, "describe() must include 'entrypoint_module'")

    stages = growth.control_plane_stages()
    _require(isinstance(stages, tuple), "control_plane_stages() must return a tuple")
    _require(len(stages) == 9, f"expected 9 control-plane stages, got {len(stages)}")
    _require(stages[0] == "ResearchIngest",
             f"first stage must be 'ResearchIngest', got {stages[0]!r}")
    _require(stages[-1] == "Finalizer",
             f"last stage must be 'Finalizer', got {stages[-1]!r}")

    print("growth facade OK")


# ---------------------------------------------------------------------------
# 2. Upgrade miner -- structured candidate output
# ---------------------------------------------------------------------------

_CANDIDATE_REQUIRED_FIELDS: tuple[str, ...] = (
    "candidate_id",
    "title",
    "why",
    "plan",
    "evidence",
    "risk",
    "source",
    "tests",
    "created_at",
)


def check_upgrade_miner_candidates() -> None:
    """Upgrade miner produces structured candidates with required fields."""
    from link_modes.growth.link_research_upgrade_miner import run_miner

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "research").mkdir(parents=True)
        (root / ".link" / "patch_drafts" / "pending").mkdir(parents=True)

        (root / "research" / "upgrade_ideas.md").write_text(
            "Research: missing research evidence citation for proposals. "
            "Gap: no approval candidate pipeline from research sources. "
            "Upgrade: sandboxed implementation handoff with human approval. "
            "Frontier gap grading rubric needed. Market context refresh.\n",
            encoding="utf-8",
        )

        receipt = run_miner(
            root=root,
            research_dirs=["research"],
            candidate_file=Path(".link/approval_candidates.jsonl"),
            write_candidates=False,
        )

        _require(isinstance(receipt, dict), "run_miner must return a dict")
        _require(receipt.get("status") == "ok", f"run_miner status must be 'ok', got {receipt.get('status')!r}")
        _require(receipt.get("chunk_count", 0) >= 1,
                 f"run_miner must find >= 1 research chunk, got {receipt.get('chunk_count')}")
        _require(receipt.get("candidate_count", 0) >= 1,
                 f"run_miner must produce >= 1 candidate, got {receipt.get('candidate_count')}")

        candidates = receipt.get("candidates", [])
        _require(isinstance(candidates, list), "candidates must be a list")

        for cand in candidates:
            _require(isinstance(cand, dict), "each candidate must be a dict")
            _require_keys(cand, _CANDIDATE_REQUIRED_FIELDS, f"candidate {cand.get('title', '?')!r}")
            _require(isinstance(cand["plan"], list), "candidate plan must be a list")
            _require(len(cand["plan"]) >= 1, "candidate plan must have >= 1 step")
            _require(isinstance(cand["evidence"], list), "candidate evidence must be a list")
            _require(cand["risk"] in ("low", "medium", "high"),
                     f"candidate risk must be low/medium/high, got {cand['risk']!r}")
            _require(bool(cand["candidate_id"]), "candidate_id must not be empty")
            _require(bool(cand["title"]), "candidate title must not be empty")

    print(f"upgrade miner candidates OK ({len(candidates)} candidates produced)")


# ---------------------------------------------------------------------------
# 3. Research archive miner -- temp zip intake
# ---------------------------------------------------------------------------

def check_research_archive_miner() -> None:
    """Archive miner stages a temp zip and produces findings + agent jobs."""
    from link_modes.growth.link_research_archive_miner import mine_inputs

    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        sample_zip = td_path / "sample_research.zip"
        with zipfile.ZipFile(sample_zip, "w") as zf:
            zf.writestr(
                "notes/upgrade_ideas.md",
                "TODO: implement research evidence archive intake so agents can "
                "search zips and files. Need workflow receipt and safety guard. "
                "Upgrade: missing sandboxed implementation handoff with human approval.\n",
            )

        result = mine_inputs(
            [str(sample_zip)],
            intake_dir=td_path / "intake",
            limit_findings=50,
            write_outputs=True,
        )

        _require(isinstance(result, dict), "mine_inputs must return a dict")
        _require(result.get("ok") is True, "mine_inputs result must have ok=True")
        _require(result.get("status") == "ok", f"mine_inputs status must be 'ok', got {result.get('status')!r}")

        _require(isinstance(result.get("sources"), list), "sources must be a list")
        _require(len(result["sources"]) >= 1, "must have >= 1 source staged")

        _require(isinstance(result.get("findings"), list), "findings must be a list")
        _require(len(result["findings"]) >= 1,
                 "must produce >= 1 finding from synthetic research zip")

        _require(isinstance(result.get("agent_jobs"), list), "agent_jobs must be a list")
        _require(len(result["agent_jobs"]) >= 1,
                 "must produce >= 1 agent job from findings")

        for job in result["agent_jobs"]:
            _require(isinstance(job, dict), "each agent job must be a dict")
            for key in ("id", "title", "prompt", "category", "evidence"):
                if key not in job:
                    raise AssertionError(f"agent job missing key {key!r}")

        paths = result.get("paths", {})
        report_path = Path(paths.get("report_path", ""))
        json_path = Path(paths.get("json_path", ""))
        _require(report_path.exists(), "report markdown must be written to disk")
        _require(json_path.exists(), "json result must be written to disk")

    print(f"research archive miner OK ({len(result['findings'])} findings, {len(result['agent_jobs'])} agent jobs)")


# ---------------------------------------------------------------------------
# 4. Approved research handoff executor
# ---------------------------------------------------------------------------

def check_approved_research_handoff_executor() -> None:
    """Handoff executor converts a synthetic approved draft into a handoff receipt."""
    from link_modes.growth.link_approved_research_handoff_executor import ensure_handoffs

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        approved_dir = root / ".link" / "patch_drafts" / "approved"
        approved_dir.mkdir(parents=True)

        sample_draft = {
            "draft_id": "test-lu201-research-evidence-index",
            "task_id": "LU201",
            "title": "research evidence index for upgrade proposals",
            "source": "research_upgrade_miner",
            "proposal_hash": "deadbeef1234",
            "files": ["link_research_upgrade_miner.py"],
            "plan": ["Index research evidence."],
            "evidence": [
                {"source_path": "research/example.md", "line": 1, "snippet": "agent research evidence"}
            ],
        }
        (approved_dir / "test-lu201-research-evidence-index.json").write_text(
            json.dumps(sample_draft), encoding="utf-8"
        )

        result = ensure_handoffs(root, write=True)

        _require(isinstance(result, dict), "ensure_handoffs must return a dict")
        _require(result.get("status") == "ok",
                 f"ensure_handoffs status must be 'ok', got {result.get('status')!r}")
        _require(result.get("created_count", 0) == 1,
                 f"expected 1 handoff created, got {result.get('created_count')}")

        created = result.get("created", [])
        _require(len(created) == 1, "created list must have 1 entry")

        handoff = created[0]
        for key in ("handoff_id", "source_draft_id", "source_title", "source_plan", "source_evidence"):
            if key not in handoff:
                raise AssertionError(f"handoff missing key {key!r}")

        _require(bool(handoff["handoff_id"]), "handoff_id must not be empty")
        _require(handoff["source_draft_id"] == "test-lu201-research-evidence-index",
                 "source_draft_id must match the input draft")

        handoff_dir = root / ".link" / "approved_research_handoffs"
        written = list(handoff_dir.glob("*.json"))
        _require(len(written) == 1, f"expected 1 handoff file on disk, found {len(written)}")

    print("approved research handoff executor OK")


# ---------------------------------------------------------------------------
# 5. Self-learning dashboard build
# ---------------------------------------------------------------------------

_DASHBOARD_REQUIRED_KEYS: tuple[str, ...] = (
    "version",
    "generated",
    "mode",
    "counts",
    "patch_draft_counts",
)


def check_self_learning_dashboard() -> None:
    """build_dashboard returns a dict with required keys (temp dir, no writes)."""
    from link_modes.growth.link_self_learning_dashboard import build_dashboard

    with tempfile.TemporaryDirectory() as td:
        result = build_dashboard(root=Path(td))

    _require(isinstance(result, dict), "build_dashboard must return a dict")
    _require_keys(result, _DASHBOARD_REQUIRED_KEYS, "build_dashboard result")

    print("self-learning dashboard build OK")


# ---------------------------------------------------------------------------
# 6. Control plane -- well-formed proposal is accepted
# ---------------------------------------------------------------------------

def check_control_plane_accepts_valid_proposal() -> None:
    """validate_proposal accepts a fully-formed proposal artifact."""
    from link_core.control_plane import validate_proposal, make_proposal_id
    import datetime as dt

    proposal_id = make_proposal_id(
        "research evidence index for upgrade proposals",
        "research/upgrade_ideas.md",
    )
    proposal = {
        "proposal_id": proposal_id,
        "title": "research evidence index for upgrade proposals",
        "source_path": "research/upgrade_ideas.md",
        "source_summary": "Research doc describes indexing evidence for proposals.",
        "extracted_capabilities": ["evidence indexing", "source citation"],
        "link_takeaways": ["Link lacks source-grounded proposal evidence trail"],
        "affected_files": ["link_research_upgrade_miner.py"],
        "risk_level": "medium",
        "expected_behavior_change": "Proposals will cite source evidence paths.",
        "implementation_plan": ["Add evidence index to run_miner output."],
        "verification_commands": ["python3 -m py_compile link_research_upgrade_miner.py"],
        "rollback_plan": "Revert to prior commit; no destructive changes expected.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": dt.datetime.now().replace(microsecond=0).isoformat(),
    }

    try:
        validate_proposal(proposal)
    except Exception as exc:
        raise AssertionError(f"validate_proposal rejected a well-formed proposal: {exc}")

    print("control plane accepts valid proposal OK")


# ---------------------------------------------------------------------------
# 7. Candidate-to-proposal bridge -- produces valid proposals
# ---------------------------------------------------------------------------

def check_bridge_produces_valid_proposal() -> None:
    """Bridge converts a miner candidate into a validate_proposal-compatible dict."""
    from link_core.control_plane import validate_proposal
    from link_modes.growth.link_candidate_proposal_bridge import candidate_to_proposal

    synthetic = {
        "candidate_id": "abc123def456",
        "source": "research_upgrade_miner",
        "source_version": "LU190-research-upgrade-miner-foundation-v1",
        "title": "research evidence index for upgrade proposals",
        "risk": "medium",
        "why": "Link needs source-grounded upgrade proposals so agents can cite research files.",
        "plan": [
            "Index configured research folders and archives.",
            "Record source path and snippet for each hit.",
            "Attach evidence references to generated candidates.",
        ],
        "proposed_plan": [
            "Index configured research folders and archives.",
            "Record source path and snippet for each hit.",
            "Attach evidence references to generated candidates.",
        ],
        "files": ["link_research_upgrade_miner.py"],
        "files_affected": ["link_research_upgrade_miner.py"],
        "areas_affected": ["link_research_upgrade_miner.py"],
        "tests": ["python3 -m py_compile link_research_upgrade_miner.py"],
        "checks": ["python3 -m py_compile link_research_upgrade_miner.py"],
        "receipts": [".link/approval_candidates.jsonl"],
        "evidence": [
            {
                "source_path": "research/example.md",
                "line": 1,
                "snippet": "evidence citation research",
            }
        ],
        "created_at": "2026-05-29T00:00:00",
    }

    proposal = candidate_to_proposal(synthetic)
    try:
        validate_proposal(proposal)
    except Exception as exc:
        raise AssertionError(
            f"validate_proposal rejected bridged proposal: {exc}"
        )

    _require(
        isinstance(proposal["proposal_id"], str) and bool(proposal["proposal_id"]),
        "proposal_id must be a non-empty string",
    )
    _require(
        proposal["risk_level"] == "medium",
        f"risk_level expected 'medium', got {proposal['risk_level']!r}",
    )
    _require(
        proposal["status"] == "pending",
        f"status expected 'pending', got {proposal['status']!r}",
    )
    _require(
        proposal["recommendation"] == "accept",
        f"recommendation expected 'accept', got {proposal['recommendation']!r}",
    )
    _require(
        isinstance(proposal["implementation_plan"], list)
        and len(proposal["implementation_plan"]) > 0,
        "implementation_plan must be a non-empty list",
    )

    print("bridge produces valid proposal OK")


def check_bridge_rejects_bad_input() -> None:
    """Bridge raises TypeError on non-dict and ValueError on missing title."""
    from link_modes.growth.link_candidate_proposal_bridge import candidate_to_proposal

    try:
        candidate_to_proposal(None)  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("candidate_to_proposal(None) must raise TypeError")

    try:
        candidate_to_proposal({})
    except ValueError:
        pass
    else:
        raise AssertionError("candidate_to_proposal({}) must raise ValueError")

    print("bridge rejects bad input OK")


# ---------------------------------------------------------------------------
# 8. Growth propose() -- end-to-end candidate-to-proposal runtime path
# ---------------------------------------------------------------------------

def check_growth_propose_function() -> None:
    """propose() converts miner candidates into validated proposal dicts."""
    from link_core.control_plane import validate_proposal
    from link_modes.growth import propose
    from link_modes.growth.link_research_upgrade_miner import run_miner

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "research").mkdir(parents=True)
        (root / ".link" / "patch_drafts" / "pending").mkdir(parents=True)

        (root / "research" / "upgrade_ideas.md").write_text(
            "Evidence citation for upgrade proposals. "
            "Frontier gap grading rubric. "
            "Approval candidate pipeline. "
            "Sandboxed implementation handoff. "
            "Market context refresh adapter.\n",
            encoding="utf-8",
        )

        receipt = run_miner(
            root=root,
            research_dirs=["research"],
            candidate_file=Path(".link/approval_candidates.jsonl"),
            write_candidates=False,
        )

    candidates = receipt["candidates"]
    _require(len(candidates) >= 1, "run_miner must produce candidates for propose() test")

    proposals = propose(candidates)
    _require(isinstance(proposals, list), "propose() must return a list")
    _require(len(proposals) == len(candidates),
             f"propose() must return same count: {len(proposals)} vs {len(candidates)}")

    for proposal in proposals:
        _require(isinstance(proposal, dict), "each proposal must be a dict")
        try:
            validate_proposal(proposal)
        except Exception as exc:
            raise AssertionError(
                f"validate_proposal rejected propose() output: {exc}"
            )

    first = proposals[0]
    _require(isinstance(first["proposal_id"], str) and bool(first["proposal_id"]),
             "proposal_id must be non-empty")
    _require(first["status"] == "pending",
             f"proposal status must be 'pending', got {first['status']!r}")
    _require(first["recommendation"] == "accept",
             f"proposal recommendation must be 'accept', got {first['recommendation']!r}")
    _require(isinstance(first["implementation_plan"], list) and len(first["implementation_plan"]) > 0,
             "proposal implementation_plan must be a non-empty list")

    # validate=False path -- still produces required fields but skips validation
    proposals_no_val = propose(candidates, validate=False)
    _require(len(proposals_no_val) == len(candidates),
             "propose(validate=False) must return same count")
    for key in ("proposal_id", "title", "risk_level", "status", "recommendation"):
        if key not in proposals_no_val[0]:
            raise AssertionError(
                f"propose(validate=False) output missing key: {key!r}"
            )

    # Empty input is safe
    empty = propose([])
    _require(empty == [], "propose([]) must return empty list")

    print(f"growth propose() OK ({len(proposals)} proposals from {len(candidates)} candidates)")


# ---------------------------------------------------------------------------
# 9. Growth console data collector
# ---------------------------------------------------------------------------

def check_growth_console_data() -> None:
    """collect_console_data returns a dict with expected Growth display keys."""
    from link_modes.growth.link_growth_console import collect_console_data

    data = collect_console_data()
    _require(isinstance(data, dict), "collect_console_data must return a dict")

    for key in ("repo", "healthcheck", "mode", "pipeline", "clusters",
                "proposals", "drafts", "next_actions"):
        if key not in data:
            raise AssertionError(
                f"collect_console_data missing key: {key!r}"
            )

    repo = data["repo"]
    _require(isinstance(repo.get("branch"), str) and bool(repo["branch"]),
             "repo.branch must be a non-empty string")
    _require(isinstance(repo.get("head"), str) and bool(repo["head"]),
             "repo.head must be a non-empty string")

    mode = data["mode"]
    _require(mode.get("name") == "growth", "mode.name must be 'growth'")
    _require(mode.get("has_propose") is True, "mode.has_propose must be True")
    _require(isinstance(mode.get("bridge_version"), str),
             "mode.bridge_version must be a string")

    pipeline = data["pipeline"]
    stages = pipeline.get("stages", [])
    _require(isinstance(stages, list), "pipeline.stages must be a list")
    _require(len(stages) == 9, f"pipeline must have 9 stages, got {len(stages)}")

    clusters = data["clusters"]
    _require(isinstance(clusters, list), "clusters must be a list")
    _require(len(clusters) >= 1, "must have >= 1 upgrade cluster")

    print("growth console data OK")


# ---------------------------------------------------------------------------
# 10. Growth proposals data collector
# ---------------------------------------------------------------------------

def check_growth_proposals_data() -> None:
    """collect_proposals_data returns a dict with proposals from the registry."""
    from link_modes.growth.link_growth_console import collect_proposals_data

    data = collect_proposals_data()
    _require(isinstance(data, dict), "collect_proposals_data must return a dict")

    for key in ("count", "proposals", "storage_path"):
        if key not in data:
            raise AssertionError(
                f"collect_proposals_data missing key: {key!r}"
            )

    _require(isinstance(data["count"], int), "count must be an int")
    _require(data["count"] >= 0, f"count must be >= 0, got {data['count']}")
    _require(isinstance(data["proposals"], list), "proposals must be a list")
    _require(
        data["count"] == len(data["proposals"]),
        f"count {data['count']} must match proposals list length {len(data['proposals'])}",
    )
    _require(isinstance(data["storage_path"], str), "storage_path must be a string")
    _require(bool(data["storage_path"]), "storage_path must be non-empty")

    # If proposals exist, each must be a valid proposal dict
    for i, p in enumerate(data["proposals"]):
        _require(isinstance(p, dict), f"proposal [{i}] must be a dict")
        for key in ("proposal_id", "title", "status", "risk_level"):
            if key not in p:
                raise AssertionError(
                    f"proposal [{i}] missing required key: {key!r}"
                )

    print(f"growth proposals data OK ({data['count']} proposals on disk)")


# ---------------------------------------------------------------------------
# 11. Growth propose command -- source-to-proposal pipeline
# ---------------------------------------------------------------------------

def check_growth_propose_command() -> None:
    """collect_propose_data mines a source, bridges candidates, optionally writes."""
    from link_modes.growth.link_growth_console import collect_propose_data

    # -- Missing source produces source_exists=False, no exception --
    data_missing = collect_propose_data("/tmp/definitely-not-a-research-file-xyz")
    _require(
        data_missing.get("source_exists") is False,
        "missing source must set source_exists=False",
    )
    _require(
        data_missing.get("proposal_count", -1) == 0,
        "missing source must have 0 proposals",
    )
    _require(
        isinstance(data_missing.get("error"), str),
        "missing source must set error string",
    )

    # -- Valid source with dry-run (default) --
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "input.md"
        src.write_text(
            "Evidence citation source. Approval candidate pipeline. "
            "Sandboxed safe implementation. Frontier gap grading. "
            "Market context refresh. Research upgrade mining.\n",
            encoding="utf-8",
        )

        data = collect_propose_data(source=str(src), write=False, root=td)
        _require(data.get("source_exists") is True, "valid source must set source_exists=True")
        _require(data.get("chunk_count", 0) >= 1, "must find >= 1 chunk")
        _require(data.get("candidate_count", 0) >= 1, "must have >= 1 candidate")
        _require(data.get("proposal_count", 0) >= 1, "must have >= 1 proposal")
        _require(data.get("dry_run") is True, "default must be dry_run=True")
        _require(data.get("written_paths") == [], "dry-run must have empty written_paths")

        proposals = data.get("proposals", [])
        for p in proposals:
            for key in ("proposal_id", "title", "status", "risk_level"):
                if key not in p:
                    raise AssertionError(f"proposal missing key: {key!r}")

        # -- Write mode --
        data_w = collect_propose_data(source=str(src), write=True, root=td)
        _require(data_w.get("dry_run") is False, "write=True must set dry_run=False")
        _require(
            len(data_w.get("written_paths", [])) == data_w.get("proposal_count", 0),
            "written_paths count must match proposal_count",
        )
        for wp in data_w.get("written_paths", []):
            _require(Path(wp).exists(), f"written path must exist on disk: {wp}")

    print(f"growth propose command OK ({data['proposal_count']} proposals from {data['candidate_count']} candidates)")


# ---------------------------------------------------------------------------
# 12. Growth approve command -- approves a proposal by ID
# ---------------------------------------------------------------------------

def check_growth_approve_command() -> None:
    """collect_approve_data approves a temp proposal and records the receipt."""
    import json as _json
    from link_core.control_plane import write_proposal, load_proposal
    from link_core.control_plane.link_control_plane_proposals import proposal_storage_dir

    proposal = {
        "proposal_id": "test-approve-smoke-xyz123",
        "title": "test approve smoke proposal",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for approve command.",
        "extracted_capabilities": ["smoke"],
        "link_takeaways": ["approve works"],
        "affected_files": [],
        "risk_level": "low",
        "expected_behavior_change": "none",
        "implementation_plan": ["smoke step"],
        "verification_commands": ["echo ok"],
        "rollback_plan": "revert",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)

        from link_modes.growth.link_growth_console import collect_approve_data

        data = collect_approve_data("test-approve-smoke-xyz123", root=td)
        _require(data.get("ok") is True, "approve must set ok=True")
        _require(data["proposal_id"] == "test-approve-smoke-xyz123",
                 "approve must return correct proposal_id")
        _require(data["title"] == "test approve smoke proposal",
                 "approve must return correct title")
        _require(data["previous_status"] == "pending",
                 f"previous_status must be 'pending', got {data['previous_status']!r}")
        _require(data["new_status"] == "accepted",
                 f"new_status must be 'accepted', got {data['new_status']!r}")
        _require(bool(data["path"]), "path must be non-empty")
        _require(data.get("error") is None, "approve must have no error")

        # Verify on-disk mutation
        storage = proposal_storage_dir(td)
        loaded = load_proposal(storage / "test-approve-smoke-xyz123.json")
        _require(loaded["status"] == "accepted",
                 f"on-disk status must be 'accepted', got {loaded['status']!r}")

    print("growth approve command OK")


# ---------------------------------------------------------------------------
# 13. Growth reject command -- rejects a proposal by ID, stores reason
# ---------------------------------------------------------------------------

def check_growth_reject_command() -> None:
    """collect_reject_data rejects a temp proposal and stores the reason."""
    from link_core.control_plane import write_proposal, load_proposal
    from link_core.control_plane.link_control_plane_proposals import proposal_storage_dir

    proposal = {
        "proposal_id": "test-reject-smoke-abc456",
        "title": "test reject smoke proposal",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for reject command.",
        "extracted_capabilities": ["smoke"],
        "link_takeaways": ["reject works"],
        "affected_files": [],
        "risk_level": "medium",
        "expected_behavior_change": "none",
        "implementation_plan": ["smoke step"],
        "verification_commands": ["echo ok"],
        "rollback_plan": "revert",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)

        from link_modes.growth.link_growth_console import collect_reject_data

        data = collect_reject_data(
            "test-reject-smoke-abc456",
            reason="out of scope for current slice",
            root=td,
        )
        _require(data.get("ok") is True, "reject must set ok=True")
        _require(data["proposal_id"] == "test-reject-smoke-abc456",
                 "reject must return correct proposal_id")
        _require(data["title"] == "test reject smoke proposal",
                 "reject must return correct title")
        _require(data["previous_status"] == "pending",
                 f"previous_status must be 'pending', got {data['previous_status']!r}")
        _require(data["new_status"] == "rejected",
                 f"new_status must be 'rejected', got {data['new_status']!r}")
        _require(data.get("reason") == "out of scope for current slice",
                 f"reason must be passed through, got {data.get('reason')!r}")
        _require(data.get("error") is None, "reject must have no error")

        # Verify on-disk mutation
        storage = proposal_storage_dir(td)
        loaded = load_proposal(storage / "test-reject-smoke-abc456.json")
        _require(loaded["status"] == "rejected",
                 f"on-disk status must be 'rejected', got {loaded['status']!r}")
        _require(loaded.get("rejection_reason") == "out of scope for current slice",
                 "rejection_reason must be stored on disk")

    print("growth reject command OK")


# ---------------------------------------------------------------------------
# 14. Growth approve/reject -- missing ID fails cleanly
# ---------------------------------------------------------------------------

def check_growth_approve_reject_missing_id() -> None:
    """Missing proposal ID returns ok=False with a descriptive error."""
    from link_modes.growth.link_growth_console import (
        collect_approve_data,
        collect_reject_data,
    )

    with tempfile.TemporaryDirectory() as td:
        data_approve = collect_approve_data("nonexistent-id-xyz", root=td)
        _require(data_approve.get("ok") is False,
                 "approve with missing ID must set ok=False")
        _require(isinstance(data_approve.get("error"), str),
                 "approve with missing ID must set error string")
        _require("not found" in data_approve.get("error", "").lower(),
                 "approve error must mention 'not found'")

        data_reject = collect_reject_data("nonexistent-id-xyz", root=td)
        _require(data_reject.get("ok") is False,
                 "reject with missing ID must set ok=False")
        _require(isinstance(data_reject.get("error"), str),
                 "reject with missing ID must set error string")
        _require("not found" in data_reject.get("error", "").lower(),
                 "reject error must mention 'not found'")

    print("growth approve/reject missing ID OK")


# ---------------------------------------------------------------------------
# 15. Growth handoff command -- dry-run does not write files
# ---------------------------------------------------------------------------

def check_growth_handoff_dry_run() -> None:
    """collect_handoff_data on an accepted proposal returns a preview, no writes."""
    import json as _json
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status

    proposal = {
        "proposal_id": "handoff-smoke-dryrun-xyz",
        "title": "handoff dry-run smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for handoff dry-run.",
        "extracted_capabilities": ["dryrun smoke"],
        "link_takeaways": ["dryrun works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "Console shows handoff card.",
        "implementation_plan": ["Step one.", "Step two.", "Step three."],
        "verification_commands": ["python3 -m py_compile link_growth_console.py"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        update_proposal_status("handoff-smoke-dryrun-xyz", "accepted", root=td)

        from link_modes.growth.link_growth_console import collect_handoff_data

        data = collect_handoff_data("handoff-smoke-dryrun-xyz", write=False, root=td)
        _require(data.get("ok") is True, "dry-run handoff must set ok=True")
        _require(data["proposal_id"] == "handoff-smoke-dryrun-xyz",
                 "handoff must return correct proposal_id")
        _require(data["proposal_status"] == "accepted",
                 f"proposal_status must be 'accepted', got {data['proposal_status']!r}")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("written_paths") == [],
                 "dry-run must have empty written_paths")

        plan = data.get("patch_plan")
        _require(plan is not None, "dry-run must populate patch_plan")
        _require(isinstance(plan.get("plan_id"), str) and bool(plan["plan_id"]),
                 "plan_id must be non-empty")
        _require(plan.get("status") == "draft",
                 f"plan status must be 'draft', got {plan.get('status')!r}")

        handoff = data.get("worker_handoff")
        _require(handoff is not None, "dry-run must populate worker_handoff")
        _require(isinstance(handoff.get("handoff_id"), str) and bool(handoff["handoff_id"]),
                 "handoff_id must be non-empty")
        _require(handoff.get("stage") == "PatchWorker",
                 f"handoff stage must be 'PatchWorker', got {handoff.get('stage')!r}")
        _require(handoff.get("status") == "queued",
                 f"handoff status must be 'queued', got {handoff.get('status')!r}")

        # Confirm no files were written to the temp dir
        plan_dir = Path(td) / ".agents/control_plane/patch_plans"
        worker_dir = Path(td) / ".agents/control_plane/worker_handoffs"
        plan_files = list(plan_dir.glob("*.json")) if plan_dir.exists() else []
        worker_files = list(worker_dir.glob("*.json")) if worker_dir.exists() else []
        _require(len(plan_files) == 0, f"dry-run must not write plan files, found {len(plan_files)}")
        _require(len(worker_files) == 0, f"dry-run must not write handoff files, found {len(worker_files)}")

    print("growth handoff dry-run OK")


# ---------------------------------------------------------------------------
# 16. Growth handoff --write persists files
# ---------------------------------------------------------------------------

def check_growth_handoff_write() -> None:
    """collect_handoff_data with write=True persists plan and handoff files."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status

    proposal = {
        "proposal_id": "handoff-smoke-write-xyz",
        "title": "handoff write smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for handoff --write.",
        "extracted_capabilities": ["write smoke"],
        "link_takeaways": ["write works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "medium",
        "expected_behavior_change": "Files are written to canonical paths.",
        "implementation_plan": ["Write.", "Verify.", "Done."],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        update_proposal_status("handoff-smoke-write-xyz", "accepted", root=td)

        from link_modes.growth.link_growth_console import collect_handoff_data

        data = collect_handoff_data("handoff-smoke-write-xyz", write=True, root=td)
        _require(data.get("ok") is True, "write handoff must set ok=True")
        _require(data.get("dry_run") is False, "write=True must set dry_run=False")

        written = data.get("written_paths", [])
        _require(len(written) == 2, f"expected 2 written paths, got {len(written)}")

        plan_data = data.get("patch_plan")
        handoff_data = data.get("worker_handoff")

        # Verify plan file
        plan_dir = Path(td) / ".agents" / "control_plane" / "patch_plans"
        plan_file = plan_dir / f"{plan_data['plan_id']}.json"
        _require(plan_file.exists(), f"plan file must exist: {plan_file}")
        plan_content = json.loads(plan_file.read_text(encoding="utf-8"))
        _require(plan_content["plan_id"] == plan_data["plan_id"],
                 "plan_id must match on-disk content")

        # Verify handoff file
        worker_dir = Path(td) / ".agents" / "control_plane" / "worker_handoffs"
        handoff_file = worker_dir / f"{handoff_data['handoff_id']}.json"
        _require(handoff_file.exists(), f"handoff file must exist: {handoff_file}")
        hf_content = json.loads(handoff_file.read_text(encoding="utf-8"))
        _require(hf_content["handoff_id"] == handoff_data["handoff_id"],
                 "handoff_id must match on-disk content")
        _require(hf_content["status"] == "queued",
                 f"handoff on-disk status must be 'queued', got {hf_content['status']!r}")

    print("growth handoff write OK")


# ---------------------------------------------------------------------------
# 17. Growth handoff -- error states
# ---------------------------------------------------------------------------

def check_growth_handoff_errors() -> None:
    """collect_handoff_data returns ok=False for missing, not-found, and not-accepted."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status
    from link_modes.growth.link_growth_console import collect_handoff_data

    with tempfile.TemporaryDirectory() as td:

        # Not found
        data_nf = collect_handoff_data("nonexistent-id-handoff-xyz", root=td)
        _require(data_nf.get("ok") is False, "not-found must set ok=False")
        _require(isinstance(data_nf.get("error"), str), "not-found must set error")
        _require("not found" in data_nf.get("error", "").lower(),
                 "not-found error must mention 'not found'")

        # Exists but not accepted (pending)
        pending_proposal = {
            "proposal_id": "handoff-pending-xyz",
            "title": "pending proposal for handoff test",
            "source_path": "research/smoke.md",
            "source_summary": "Pending proposal.",
            "extracted_capabilities": ["pending"],
            "link_takeaways": ["pending"],
            "affected_files": [],
            "risk_level": "low",
            "expected_behavior_change": "none",
            "implementation_plan": ["step"],
            "verification_commands": ["echo ok"],
            "rollback_plan": "revert",
            "recommendation": "accept",
            "status": "pending",
            "created_at": "2026-05-29T00:00:00",
        }
        write_proposal(pending_proposal, root=td)

        data_pending = collect_handoff_data("handoff-pending-xyz", root=td)
        _require(data_pending.get("ok") is False, "pending must set ok=False")
        _require(isinstance(data_pending.get("error"), str), "pending must set error")
        _require("accepted" in data_pending.get("error", "").lower(),
                 "pending error must mention 'accepted'")

        # Exists but rejected
        rejected_proposal = {
            "proposal_id": "handoff-rejected-xyz",
            "title": "rejected proposal for handoff test",
            "source_path": "research/smoke.md",
            "source_summary": "Rejected proposal.",
            "extracted_capabilities": ["rejected"],
            "link_takeaways": ["rejected"],
            "affected_files": [],
            "risk_level": "low",
            "expected_behavior_change": "none",
            "implementation_plan": ["step"],
            "verification_commands": ["echo ok"],
            "rollback_plan": "revert",
            "recommendation": "reject",
            "status": "rejected",
            "created_at": "2026-05-29T00:00:00",
        }
        write_proposal(rejected_proposal, root=td)

        data_rejected = collect_handoff_data("handoff-rejected-xyz", root=td)
        _require(data_rejected.get("ok") is False, "rejected must set ok=False")
        _require(isinstance(data_rejected.get("error"), str), "rejected must set error")
        _require("accepted" in data_rejected.get("error", "").lower(),
                 "rejected error must mention 'accepted'")

        # Exists and accepted -- confirm ok=True with correct fields
        accepted_proposal = {
            "proposal_id": "handoff-accepted-xyz",
            "title": "accepted proposal for handoff error check",
            "source_path": "research/smoke.md",
            "source_summary": "Accepted.",
            "extracted_capabilities": ["accepted"],
            "link_takeaways": ["accepted"],
            "affected_files": ["link_growth_console.py"],
            "risk_level": "low",
            "expected_behavior_change": "none",
            "implementation_plan": ["Step one.", "Step two."],
            "verification_commands": ["echo ok"],
            "rollback_plan": "revert",
            "recommendation": "accept",
            "status": "pending",
            "created_at": "2026-05-29T00:00:00",
        }
        write_proposal(accepted_proposal, root=td)
        update_proposal_status("handoff-accepted-xyz", "accepted", root=td)

        data_ok = collect_handoff_data("handoff-accepted-xyz", root=td)
        _require(data_ok.get("ok") is True, "accepted must set ok=True")
        _require(data_ok["proposal_status"] == "accepted",
                 "proposal_status must be 'accepted'")
        _require(data_ok.get("plan_id") is not None, "plan_id must not be None")
        _require(data_ok.get("handoff_id") is not None, "handoff_id must not be None")

    print("growth handoff errors OK")


# ---------------------------------------------------------------------------
# 18. Growth run guide -- read-only workflow dashboard
# ---------------------------------------------------------------------------

def check_growth_run_guide() -> None:
    """collect_run_data returns a read-only Growth workflow guide dict."""
    from link_modes.growth.link_growth_console import collect_run_data

    data = collect_run_data()
    _require(isinstance(data, dict), "collect_run_data must return a dict")

    for key in ("repo", "healthcheck", "mode", "pipeline_stage",
                "proposal_counts", "proposals_total",
                "accepted_proposal_ids", "coverage", "next_action", "commands",
                "source_preview"):
        if key not in data:
            raise AssertionError(
                f"collect_run_data missing key: {key!r}"
            )

    _require(isinstance(data["repo"], dict), "repo must be a dict")
    _require(isinstance(data["repo"].get("branch"), str), "repo.branch must be a string")
    _require(isinstance(data["healthcheck"], dict), "healthcheck must be a dict")
    _require(isinstance(data["proposal_counts"], dict), "proposal_counts must be a dict")
    _require(isinstance(data["proposals_total"], int), "proposals_total must be an int")
    _require(data["proposals_total"] >= 0, f"proposals_total must be >= 0, got {data['proposals_total']}")
    _require(isinstance(data["accepted_proposal_ids"], list),
             "accepted_proposal_ids must be a list")
    _require(isinstance(data["next_action"], str), "next_action must be a string")
    _require(isinstance(data["commands"], list), "commands must be a list")
    _require(len(data["commands"]) >= 1, "commands must be non-empty")
    _require(data["pipeline_stage"] is not None, "pipeline_stage must not be None")

    coverage = data["coverage"]
    _require(isinstance(coverage, dict), "coverage must be a dict")
    int_keys = (
        "archive_count", "extracted_source_count", "catalog_count",
        "discovered_code_file_count", "queued_code_file_count",
        "skipped_code_file_count", "code_brief_count", "candidate_count",
        "proposal_count", "pending_proposal_count", "accepted_proposal_count",
        "rejected_proposal_count", "handoff_count", "verifier_receipt_count",
    )
    for key in int_keys:
        _require(key in coverage, f"coverage missing key: {key}")
        _require(isinstance(coverage[key], int), f"coverage {key} must be an int")
        _require(coverage[key] >= 0, f"coverage {key} must be >= 0")
    _require(isinstance(coverage.get("next_safest_command"), str),
             "coverage next_safest_command must be a string")
    _require(isinstance(coverage.get("next_commands"), list),
             "coverage next_commands must be a list")

    # source_preview is None when no --source given
    _require(data["source_preview"] is None,
             "source_preview must be None when no --source provided")

    print(f"growth run guide OK (stage: {data['pipeline_stage']}, proposals: {data['proposals_total']})")


# ---------------------------------------------------------------------------
# 19. Growth run --source preview
# ---------------------------------------------------------------------------

def check_growth_run_with_source() -> None:
    """collect_run_data with --source returns a mining preview, no writes."""
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_run_data

    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "research_input.md"
        src.write_text(
            "evidence citation source research document\n"
            "missing gap upgrade not in link improve\n"
            "proposal approval candidate human oversight\n",
            encoding="utf-8",
        )

        data = collect_run_data(source=str(src), root=td)
        _require(isinstance(data, dict), "collect_run_data must return a dict")
        _require(data["source_preview"] is not None,
                 "source_preview must not be None when --source given")

        sp = data["source_preview"]
        _require(sp.get("source_exists") is True, "valid source must set source_exists=True")
        _require(isinstance(sp.get("chunk_count"), int), "chunk_count must be an int")
        _require(isinstance(sp.get("candidate_count"), int), "candidate_count must be an int")
        _require(isinstance(sp.get("proposal_count"), int), "proposal_count must be an int")

        # Verify no files were created (read-only)
        plan_dir = Path(td) / ".agents" / "control_plane" / "patch_plans"
        prop_dir = Path(td) / ".agents" / "control_plane" / "proposals"
        hf_dir = Path(td) / ".agents" / "control_plane" / "worker_handoffs"
        for d in (plan_dir, prop_dir, hf_dir):
            files = list(d.glob("*.json")) if d.exists() else []
            _require(len(files) == 0,
                     f"run --source must not write files to {d}, found {len(files)}")

    print(f"growth run with source OK (candidates: {sp.get('candidate_count')})")


# ---------------------------------------------------------------------------
# 20. Growth run smart router -- read-only next command selection
# ---------------------------------------------------------------------------

def check_growth_run_smart_router() -> None:
    """collect_run_data recommends the next safest Growth command without writes."""
    from link_core.control_plane import write_proposal
    from link_modes.growth.link_growth_console import collect_run_data

    brief_text = """# Code Research Brief: router

### UPGRADE CANDIDATE: Improve router visibility

**Problem:**
Growth run does not route to the best next command.

**Evidence from source:**
- `router.md` records the missing guidance.

**Pattern observed:**
State-aware command guidance.

**Proposed Link upgrade:**
Recommend the next safe Growth command from current local artifacts.

**Likely Link files or subsystem:**
link_modes/growth/link_growth_console.py

**Risk level:**
low

**Acceptance test idea:**
Create a temp code brief and verify growth run recommends code-brief-propose.
"""

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        data = collect_run_data(root=td)
        commands = "\n".join(data.get("commands", []))
        _require("archive-inventory" in commands or "propose --source" in commands,
                 "empty router state must recommend archive inventory or ingest start")
        coverage = data.get("coverage", {})
        _require(coverage.get("next_safest_command") == data.get("commands", [""])[0],
                 "coverage next_safest_command must mirror router first command")
        _require(coverage.get("next_commands") == data.get("commands"),
                 "coverage next_commands must preserve router commands")
        for key in (
            "archive_count", "extracted_source_count", "catalog_count",
            "discovered_code_file_count", "queued_code_file_count",
            "skipped_code_file_count", "code_brief_count", "candidate_count",
            "proposal_count", "pending_proposal_count", "accepted_proposal_count",
            "rejected_proposal_count", "handoff_count", "verifier_receipt_count",
        ):
            _require(coverage.get(key) == 0, f"empty coverage {key} must be 0")
        _require(not (root / ".agents").exists(), "empty router must not create .agents")
        _require(not (root / ".link").exists(), "empty router must not create .link")

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        brief = root / "research" / "_catalog" / "code_briefs" / "router.md"
        brief.parent.mkdir(parents=True)
        brief.write_text(brief_text, encoding="utf-8")

        before = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        data = collect_run_data(root=td)
        after = sorted(str(p.relative_to(root)) for p in root.rglob("*"))
        commands = "\n".join(data.get("commands", []))
        _require(data.get("pipeline_stage") == "ProposalWriter",
                 "code brief state must route to ProposalWriter")
        _require("code-brief-propose --source" in commands,
                 "code brief state must recommend code-brief-propose")
        _require("research/_catalog/code_briefs/router.md" in commands,
                 "code brief command must include repo-relative brief path")
        coverage = data.get("coverage", {})
        _require(coverage.get("code_brief_count") == 1,
                 "coverage must count code briefs")
        _require(coverage.get("candidate_count") == 1,
                 "coverage must count code brief candidates")
        _require(coverage.get("proposal_count") == 0,
                 "coverage proposal_count must be 0 before proposal write")
        _require(coverage.get("next_safest_command") == data.get("commands", [""])[0],
                 "coverage next_safest_command must not change router behavior")
        _require(before == after, "router must not write files while inspecting code briefs")

    with tempfile.TemporaryDirectory() as td:
        write_proposal(_sample_control_plane_proposal("router-pending-001", "pending"), root=td)
        data = collect_run_data(root=td)
        commands = "\n".join(data.get("commands", []))
        _require(data.get("pipeline_stage") == "HumanApproval",
                 "pending proposals must route to HumanApproval")
        _require("growth proposals" in commands,
                 "pending proposals must recommend proposals view")
        _require("growth approve <id>" in commands,
                 "pending proposals must recommend approve placeholder")
        coverage = data.get("coverage", {})
        _require(coverage.get("proposal_count") == 1,
                 "coverage must count generated proposals")
        _require(coverage.get("pending_proposal_count") == 1,
                 "coverage must count pending proposals")

    with tempfile.TemporaryDirectory() as td:
        write_proposal(_sample_control_plane_proposal("router-accepted-001", "accepted"), root=td)
        data = collect_run_data(root=td)
        commands = "\n".join(data.get("commands", []))
        _require(data.get("pipeline_stage") == "PatchWorker",
                 "accepted proposal must route to PatchWorker")
        _require("growth handoff router-accepted-001 --write" in commands,
                 "accepted proposal must recommend handoff for the accepted id")
        coverage = data.get("coverage", {})
        _require(coverage.get("accepted_proposal_count") == 1,
                 "coverage must count accepted proposals")
        _require(coverage.get("next_safest_command") == data.get("commands", [""])[0],
                 "coverage next_safest_command must mirror accepted router command")

    print("growth run smart router OK")


# ---------------------------------------------------------------------------
# 21. Growth handoffs -- empty state
# ---------------------------------------------------------------------------

def check_growth_handoffs_empty() -> None:
    """collect_handoffs_data returns count=0 when no handoffs exist."""
    from link_modes.growth.link_growth_console import collect_handoffs_data

    with tempfile.TemporaryDirectory() as td:
        data = collect_handoffs_data(root=td)
        _require(isinstance(data, dict), "collect_handoffs_data must return a dict")
        _require(data.get("count") == 0,
                 f"empty dir must have count=0, got {data.get('count')}")
        _require(data.get("handoffs") == [],
                 "empty dir must have handoffs=[]")
        _require(isinstance(data.get("storage_path"), str),
                 "storage_path must be a string")
        _require(bool(data.get("storage_path", "")),
                 "storage_path must be non-empty")

    print("growth handoffs empty OK")


# ---------------------------------------------------------------------------
# 21. Growth handoffs -- populated state
# ---------------------------------------------------------------------------

def check_growth_handoffs_populated() -> None:
    """collect_handoffs_data returns handoffs when they exist on disk."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status
    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )
    from link_modes.growth.link_growth_console import (
        collect_handoffs_data,
        _HANDOFF_WORKER_DIR,
    )

    proposal = {
        "proposal_id": "handoffs-view-test-xyz",
        "title": "handoffs terminal view test",
        "source_path": "research/test.md",
        "source_summary": "Smoke test for handoffs view.",
        "extracted_capabilities": ["smoke"],
        "link_takeaways": ["handoffs view works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "none",
        "implementation_plan": ["Step one.", "Step two.", "Step three."],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        from link_core.control_plane.link_control_plane_proposals import (
            load_proposal,
            proposal_storage_dir,
        )
        update_proposal_status("handoffs-view-test-xyz", "accepted", root=td)
        accepted = load_proposal(proposal_storage_dir(td) / "handoffs-view-test-xyz.json")
        plan = build_patch_plan_from_proposal(accepted)
        hf = build_worker_handoff_from_plan(plan)

        hf_dir = Path(td) / _HANDOFF_WORKER_DIR
        write_worker_handoff(hf, root=hf_dir)

        data = collect_handoffs_data(root=td)
        _require(data.get("count") == 1,
                 f"must find 1 handoff, got {data.get('count')}")
        handoffs = data.get("handoffs", [])
        _require(len(handoffs) == 1, "handoffs list must have 1 entry")

        h = handoffs[0]
        _require(h.get("handoff_id") == hf["handoff_id"],
                 "handoff_id must match written value")
        _require(h.get("proposal_id") == "handoffs-view-test-xyz",
                 "proposal_id must match source proposal")
        _require(h.get("status") == "queued",
                 f"handoff status must be 'queued', got {h.get('status')!r}")
        _require(h.get("stage") == "PatchWorker",
                 f"handoff stage must be 'PatchWorker', got {h.get('stage')!r}")
        _require(isinstance(h.get("allowed_files"), list),
                 "allowed_files must be a list")

    print("growth handoffs populated OK")


# ---------------------------------------------------------------------------
# 22. Growth execute -- dry-run builds receipt, writes nothing
# ---------------------------------------------------------------------------

def check_growth_execute_dry_run() -> None:
    """collect_execute_data builds a verifier receipt without writing files."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )
    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )

    proposal = {
        "proposal_id": "execute-dr-test-xyz",
        "title": "execute dry-run smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for execute dry-run.",
        "extracted_capabilities": ["smoke"],
        "link_takeaways": ["execute dry-run works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "none",
        "implementation_plan": ["Build receipt.", "Write receipt."],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        update_proposal_status("execute-dr-test-xyz", "accepted", root=td)
        accepted = load_proposal(proposal_storage_dir(td) / "execute-dr-test-xyz.json")
        plan = build_patch_plan_from_proposal(accepted)
        hf = build_worker_handoff_from_plan(plan)

        hf_dir = Path(td) / ".agents/control_plane/worker_handoffs"
        write_worker_handoff(hf, root=hf_dir)

        from link_modes.growth.link_growth_console import collect_execute_data

        data = collect_execute_data(hf["handoff_id"], write=False, root=td)
        _require(data.get("ok") is True, "execute dry-run must set ok=True")
        _require(data.get("dry_run") is True, "execute default must be dry_run=True")
        _require(data.get("written_paths") == [],
                 "execute dry-run must have empty written_paths")
        _require(data["handoff_id"] == hf["handoff_id"],
                 "execute must return correct handoff_id")
        _require(data["handoff_status"] == "queued",
                 f"handoff_status must be 'queued', got {data['handoff_status']!r}")

        receipt = data.get("receipt")
        _require(receipt is not None, "execute must build a receipt dict")
        _require(bool(receipt.get("verification_id")),
                 "verification_id must be non-empty")
        _require(receipt.get("stage") == "Verifier",
                 f"receipt stage must be 'Verifier', got {receipt.get('stage')!r}")
        _require(receipt.get("status") == "pending",
                 f"receipt status must be 'pending', got {receipt.get('status')!r}")
        _require(data.get("verification_id") == receipt["verification_id"],
                 "verification_id in top-level must match receipt dict")

        # Verify no files written
        receipt_dir = Path(td) / ".agents" / "control_plane" / "verifier_receipts"
        r_files = list(receipt_dir.glob("*.json")) if receipt_dir.exists() else []
        _require(len(r_files) == 0,
                 f"execute dry-run must not write receipt files, found {len(r_files)}")

    print("growth execute dry-run OK")


# ---------------------------------------------------------------------------
# 23. Growth execute -- --write persists verifier receipt
# ---------------------------------------------------------------------------

def check_growth_execute_write() -> None:
    """collect_execute_data with write=True persists the verifier receipt."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )
    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )

    proposal = {
        "proposal_id": "execute-wr-test-xyz",
        "title": "execute write smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for execute --write.",
        "extracted_capabilities": ["write"],
        "link_takeaways": ["write receipt works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "medium",
        "expected_behavior_change": "none",
        "implementation_plan": ["Step 1", "Step 2"],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        update_proposal_status("execute-wr-test-xyz", "accepted", root=td)
        accepted = load_proposal(proposal_storage_dir(td) / "execute-wr-test-xyz.json")
        plan = build_patch_plan_from_proposal(accepted)
        hf = build_worker_handoff_from_plan(plan)

        hf_dir = Path(td) / ".agents/control_plane/worker_handoffs"
        write_worker_handoff(hf, root=hf_dir)

        from link_modes.growth.link_growth_console import collect_execute_data

        data = collect_execute_data(hf["handoff_id"], write=True, root=td)
        _require(data.get("ok") is True, "execute --write must set ok=True")
        _require(data.get("dry_run") is False, "execute --write must set dry_run=False")
        _require(len(data.get("written_paths", [])) == 1,
                 f"execute --write must have 1 written path, got {len(data.get('written_paths', []))}")

        receipt = data.get("receipt")
        _require(receipt is not None, "execute --write must build a receipt dict")
        vid = receipt.get("verification_id", "")

        receipt_dir = Path(td) / ".agents" / "control_plane" / "verifier_receipts"
        receipt_file = receipt_dir / f"{vid}.json"
        _require(receipt_file.exists(), f"receipt file must exist: {receipt_file}")

        loaded = json.loads(receipt_file.read_text(encoding="utf-8"))
        _require(loaded["verification_id"] == vid,
                 "verification_id must match on-disk content")
        _require(loaded["status"] == "pending",
                 f"on-disk status must be 'pending', got {loaded['status']!r}")

    print("growth execute write OK")


# ---------------------------------------------------------------------------
# 24. Growth execute -- error states
# ---------------------------------------------------------------------------

def check_growth_execute_errors() -> None:
    """collect_execute_data returns ok=False for missing or invalid handoffs."""
    from link_modes.growth.link_growth_console import collect_execute_data

    with tempfile.TemporaryDirectory() as td:
        # Not found
        data_nf = collect_execute_data("nonexistent-execute-xyz", root=td)
        _require(data_nf.get("ok") is False, "not-found must set ok=False")
        _require(isinstance(data_nf.get("error"), str), "not-found must set error")
        _require("not found" in data_nf.get("error", "").lower(),
                 "not-found error must mention 'not found'")

    print("growth execute errors OK")


# ---------------------------------------------------------------------------
# 25. Growth receipts -- empty state
# ---------------------------------------------------------------------------

def check_growth_receipts_empty() -> None:
    """collect_receipts_data returns count=0 when no receipts exist."""
    from link_modes.growth.link_growth_console import collect_receipts_data

    with tempfile.TemporaryDirectory() as td:
        data = collect_receipts_data(root=td)
        _require(isinstance(data, dict), "collect_receipts_data must return a dict")
        _require(data.get("count") == 0,
                 f"empty dir must have count=0, got {data.get('count')}")
        _require(data.get("receipts") == [],
                 "empty dir must have receipts=[]")
        _require(isinstance(data.get("storage_path"), str),
                 "storage_path must be a string")
        _require(bool(data.get("storage_path", "")),
                 "storage_path must be non-empty")

    print("growth receipts empty OK")


# ---------------------------------------------------------------------------
# 26. Growth receipts -- populated state
# ---------------------------------------------------------------------------

def check_growth_receipts_populated() -> None:
    """collect_receipts_data returns receipts when they exist on disk."""
    from pathlib import Path
    from link_core.control_plane import write_proposal, update_proposal_status
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )
    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )
    from link_core.control_plane.link_control_plane_verifier_receipt import (
        build_verifier_receipt_from_handoff,
        write_verifier_receipt,
    )
    from link_modes.growth.link_growth_console import (
        collect_receipts_data,
        _VERIFIER_RECEIPT_DIR,
    )

    proposal = {
        "proposal_id": "receipts-pop-smoke-xyz",
        "title": "receipts populated smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for receipts view.",
        "extracted_capabilities": ["smoke"],
        "link_takeaways": ["receipts view works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "none",
        "implementation_plan": ["Step one.", "Step two."],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-29T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        write_proposal(proposal, root=td)
        update_proposal_status("receipts-pop-smoke-xyz", "accepted", root=td)
        accepted = load_proposal(proposal_storage_dir(td) / "receipts-pop-smoke-xyz.json")
        plan = build_patch_plan_from_proposal(accepted)
        hf = build_worker_handoff_from_plan(plan)
        hf_dir = Path(td) / ".agents/control_plane/worker_handoffs"
        write_worker_handoff(hf, root=hf_dir)

        receipt = build_verifier_receipt_from_handoff(hf)
        receipt_dir = Path(td) / _VERIFIER_RECEIPT_DIR
        write_verifier_receipt(receipt, root=receipt_dir)

        data = collect_receipts_data(root=td)
        _require(data.get("count") == 1,
                 f"must find 1 receipt, got {data.get('count')}")
        receipts = data.get("receipts", [])
        _require(len(receipts) == 1, "receipts list must have 1 entry")

        r = receipts[0]
        _require(r.get("verification_id") == receipt["verification_id"],
                 "verification_id must match written value")
        _require(r.get("handoff_id") == hf["handoff_id"],
                 "handoff_id must match")
        _require(r.get("stage") == "Verifier",
                 f"receipt stage must be 'Verifier', got {r.get('stage')!r}")
        _require(r.get("status") == "pending",
                 f"receipt status must be 'pending', got {r.get('status')!r}")
        _require(isinstance(r.get("verification_commands"), list),
                 "verification_commands must be a list")

    print("growth receipts populated OK")



# ---------------------------------------------------------------------------
# 27. Growth finalize -- verifier receipt to finalizer receipt
# ---------------------------------------------------------------------------

def check_growth_finalize_command() -> None:
    """collect_finalize_data previews and writes finalizer receipts safely."""
    from pathlib import Path

    from link_core.control_plane import write_proposal, update_proposal_status
    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
    )
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )
    from link_core.control_plane.link_control_plane_verifier_receipt import (
        build_verifier_receipt_from_handoff,
        write_verifier_receipt,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )
    from link_modes.growth.link_growth_console import (
        _FINALIZER_RECEIPT_DIR,
        _VERIFIER_RECEIPT_DIR,
        collect_finalize_data,
    )

    proposal = {
        "proposal_id": "finalize-smoke-xyz",
        "title": "finalize smoke test",
        "source_path": "research/smoke.md",
        "source_summary": "Smoke test for Growth finalize.",
        "extracted_capabilities": ["finalizer"],
        "link_takeaways": ["finalizer receipt works"],
        "affected_files": ["link_growth_console.py"],
        "risk_level": "low",
        "expected_behavior_change": "none",
        "implementation_plan": ["Step one.", "Step two."],
        "verification_commands": ["echo ok"],
        "rollback_plan": "Revert patch branch.",
        "recommendation": "accept",
        "status": "pending",
        "created_at": "2026-05-31T00:00:00",
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        write_proposal(proposal, root=td)
        update_proposal_status("finalize-smoke-xyz", "accepted", root=td)
        accepted = load_proposal(proposal_storage_dir(td) / "finalize-smoke-xyz.json")
        plan = build_patch_plan_from_proposal(accepted)
        handoff = build_worker_handoff_from_plan(plan)
        handoff_dir = root / ".agents/control_plane/worker_handoffs"
        write_worker_handoff(handoff, root=handoff_dir)
        verifier = build_verifier_receipt_from_handoff(
            handoff,
            status="passed",
            evidence_paths=["tests/test_growth_pipeline.py"],
            findings=["verification passed"],
        )
        verifier_dir = root / _VERIFIER_RECEIPT_DIR
        verifier_path = write_verifier_receipt(verifier, root=verifier_dir)
        finalizer_dir = root / _FINALIZER_RECEIPT_DIR

        dry = collect_finalize_data(verifier["verification_id"], write=False, root=td)
        _require(dry.get("ok") is True, "finalize dry-run must set ok=True")
        _require(dry.get("dry_run") is True, "finalize dry-run must report dry_run=True")
        _require(dry.get("written_paths") == [], "finalize dry-run must not write paths")
        _require(not finalizer_dir.exists(), "finalize dry-run must not create finalizer dir")
        finalizer = dry.get("finalizer_receipt") or {}
        _require(finalizer.get("verification_id") == verifier["verification_id"],
                 "finalizer must reference verifier id")
        _require(finalizer.get("status") == "finalized",
                 "finalizer status must default to finalized")
        _require(finalizer.get("stage") == "Finalizer",
                 "finalizer stage must be Finalizer")

        by_path = collect_finalize_data(str(verifier_path), write=False, root=td)
        _require(by_path.get("ok") is True, "finalize must accept verifier receipt path")
        _require(by_path.get("verification_id") == verifier["verification_id"],
                 "path finalize must load the same verifier")

        missing = collect_finalize_data("missing-verifier-id", write=False, root=td)
        _require(missing.get("ok") is False, "missing verifier must return ok=False")
        _require("not found" in str(missing.get("error", "")),
                 "missing verifier error must be clear")

        written = collect_finalize_data(verifier["verification_id"], write=True, root=td)
        _require(written.get("ok") is True, "finalize --write must set ok=True")
        _require(written.get("dry_run") is False, "finalize --write must report dry_run=False")
        paths = written.get("written_paths", [])
        _require(len(paths) == 1, "finalize --write must write one finalizer receipt")
        written_path = Path(paths[0])
        _require(written_path.exists(), "finalize --write path must exist")
        _require(written_path.parent == finalizer_dir,
                 "finalize --write must use finalizer receipt dir")

        again = collect_finalize_data(verifier["verification_id"], write=True, root=td)
        _require(again.get("ok") is True, "already finalized must be safe ok=True")
        _require(again.get("already_finalized") is True,
                 "already finalized must report already_finalized=True")
        _require(again.get("written_paths") == [],
                 "already finalized must not write a duplicate")
        _require(len(list(finalizer_dir.glob("*.json"))) == 1,
                 "already finalized must leave one finalizer file")

    print("growth finalize command OK")


# ---------------------------------------------------------------------------
# 27. Growth archive-inventory -- empty state
# ---------------------------------------------------------------------------

def check_growth_archive_inventory_empty() -> None:
    """collect_archive_inventory returns count=0 when no archives exist."""
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_inventory

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        research_dir = root / "research"
        research_dir.mkdir()

        data = collect_archive_inventory(root=str(root))
        _require(isinstance(data, dict), "collect_archive_inventory must return a dict")
        _require(data.get("count") == 0,
                 f"empty dir must have count=0, got {data.get('count')}")
        _require(data.get("archives") == [],
                 "empty dir must have archives=[]")
        _require(isinstance(data.get("scan_dir"), str),
                 "scan_dir must be a string")

    print("growth archive-inventory empty OK")


# ---------------------------------------------------------------------------
# 28. Growth archive-inventory -- populated state
# ---------------------------------------------------------------------------

def check_growth_archive_inventory_populated() -> None:
    """collect_archive_inventory discovers and inspects a synthetic zip file."""
    import zipfile
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_inventory

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        research_dir = root / "research"
        research_dir.mkdir()

        archive_path = research_dir / "test_research.zip"
        with zipfile.ZipFile(str(archive_path), "w") as zf:
            zf.writestr("test-project/README.md", "# Test Research Archive\n")
            zf.writestr("test-project/src/main.py", "print('hello')\n")
            zf.writestr("test-project/docs/notes.md", "# Docs\n")

        data = collect_archive_inventory(root=str(root))
        _require(data.get("count") == 1,
                 f"must find 1 archive, got {data.get('count')}")
        archives = data.get("archives", [])
        _require(len(archives) == 1, "archives list must have 1 entry")

        a = archives[0]
        _require(a.get("name") == "test_research.zip",
                 f"name must be 'test_research.zip', got {a.get('name')!r}")
        _require(a.get("archive_type") == "zip",
                 f"archive_type must be 'zip', got {a.get('archive_type')!r}")
        _require(a.get("file_count") == 3,
                 f"file_count must be 3, got {a.get('file_count')}")
        _require(a.get("top_dir") == "test-project",
                 f"top_dir must be 'test-project', got {a.get('top_dir')!r}")
        _require(a.get("is_clean") is True,
                 "synthetic zip must be clean")
        _require(a.get("safety_flags") == [],
                 "synthetic zip must have no safety flags")
        _require(a.get("error") is None,
                 "synthetic zip must have no error")
        _require(bool(a.get("estimated_extracted_bytes")) is True,
                 "estimated_extracted_bytes must be non-zero")
        _require(isinstance(a.get("relative_path"), str),
                 "relative_path must be a string")

    print("growth archive-inventory populated OK")


# ---------------------------------------------------------------------------
# 29. Growth archive-extract -- dry-run previews, writes nothing
# ---------------------------------------------------------------------------

def check_growth_archive_extract_dry_run() -> None:
    """archive-extract dry-run pre-checks and previews without writing files."""
    import zipfile
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_extraction_data

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        research_dir = root / "research"
        research_dir.mkdir()

        archive_path = research_dir / "test_dry_extract.zip"
        with zipfile.ZipFile(str(archive_path), "w") as zf:
            zf.writestr("project-dry/README.md", "# Dry run test\n")
            zf.writestr("project-dry/src/lib.py", "def foo(): pass\n")
            zf.writestr("project-dry/docs/api.md", "# API\n")

        data = collect_extraction_data(
            "research/test_dry_extract.zip", write=False, root=str(root)
        )
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("extracted_count") == 0,
                 "dry-run must have extracted_count=0")
        _require(data.get("archive_name") == "test_dry_extract.zip",
                 f"archive_name mismatch: {data.get('archive_name')}")

        # Verify no files were written
        output_dir = root / "research/_extracted" / "test_dry_extract"
        _require(not output_dir.exists(),
                 f"dry-run must not create output dir: {output_dir}")
        receipt_dir = root / "research/_catalog/extraction_receipts"
        _require(not receipt_dir.exists(),
                 f"dry-run must not create receipt dir: {receipt_dir}")

    print("growth archive-extract dry-run OK")


# ---------------------------------------------------------------------------
# 30. Growth archive-extract -- --write extracts and writes receipt
# ---------------------------------------------------------------------------

def check_growth_archive_extract_write() -> None:
    """archive-extract --write extracts files and writes a receipt."""
    import json as _json
    import zipfile
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_extraction_data

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        research_dir = root / "research"
        research_dir.mkdir()

        archive_path = research_dir / "test_write_extract.zip"
        with zipfile.ZipFile(str(archive_path), "w") as zf:
            zf.writestr("project-write/README.md", "# Write test\n")
            zf.writestr("project-write/src/main.py", "print('hello')\n")
            zf.writestr("project-write/tests/test_main.py", "# test\n")

        data = collect_extraction_data(
            "research/test_write_extract.zip", write=True, root=str(root)
        )
        _require(data.get("ok") is True, "write must set ok=True")
        _require(data.get("dry_run") is False, "write must set dry_run=False")
        _require(data.get("extracted_count") == 3,
                 f"expected 3 extracted, got {data.get('extracted_count')}")
        _require(data.get("skipped_unsafe") == 0,
                 "clean archive must have skipped_unsafe=0")
        _require(data.get("skipped_macosx") == 0,
                 "clean archive must have skipped_macosx=0")

        # Verify files on disk
        output_dir = root / "research/_extracted" / "test_write_extract"
        _require(output_dir.exists(), "output dir must exist after --write")
        _require((output_dir / "project-write/README.md").exists(),
                 "README.md must exist on disk")
        _require((output_dir / "project-write/src/main.py").exists(),
                 "src/main.py must exist on disk")
        _require((output_dir / "project-write/tests/test_main.py").exists(),
                 "tests/test_main.py must exist on disk")

        # Verify receipt
        receipt_path = Path(data.get("receipt_path", ""))
        _require(receipt_path.exists(), f"receipt must exist: {receipt_path}")
        receipt_data = _json.loads(receipt_path.read_text(encoding="utf-8"))
        _require(receipt_data.get("receipt_version") == "link-archive-extract-v1",
                 "receipt must have correct version")
        _require(receipt_data.get("archive_stem") == "test_write_extract",
                 "receipt must have correct archive_stem")
        _require(receipt_data.get("extracted_count") == 3,
                 f"receipt extracted_count must be 3, got {receipt_data.get('extracted_count')}")

        # Originals should still exist
        _require(archive_path.exists(), "original archive must not be touched")

    print("growth archive-extract write OK")


# ---------------------------------------------------------------------------
# 31. Growth archive-extract -- blocked for unsafe archives
# ---------------------------------------------------------------------------

def check_growth_archive_extract_blocked() -> None:
    """archive-extract blocks archives with unsafe paths."""
    import zipfile
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_extraction_data

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        research_dir = root / "research"
        research_dir.mkdir()

        # Archive with ../ traversal
        archive_path = research_dir / "dangerous_traversal.zip"
        with zipfile.ZipFile(str(archive_path), "w") as zf:
            zf.writestr("normal-file.md", "# safe\n")
            zf.writestr("../outside-escape.txt", "dangerous\n")

        data = collect_extraction_data(
            "research/dangerous_traversal.zip", write=False, root=str(root)
        )
        _require(data.get("ok") is False,
                 "archive with ../ traversal must be blocked")
        _require(isinstance(data.get("error"), str),
                 "blocked archive must have error string")
        _require("traversal" in data.get("error", "").lower() or
                 "safety" in data.get("error", "").lower(),
                 "error must mention safety/traversal")

        # Archive with absolute path
        archive_path2 = research_dir / "dangerous_absolute.zip"
        with zipfile.ZipFile(str(archive_path2), "w") as zf:
            zf.writestr("safe-file.md", "# safe\n")
            zf.writestr("/etc/malicious.conf", "bad\n")

        data2 = collect_extraction_data(
            "research/dangerous_absolute.zip", write=False, root=str(root)
        )
        _require(data2.get("ok") is False,
                 "archive with absolute path must be blocked")

    print("growth archive-extract blocked OK")


# ---------------------------------------------------------------------------
# 32. Growth archive-catalog -- dry-run scans, writes nothing
# ---------------------------------------------------------------------------

def check_growth_archive_catalog_dry_run() -> None:
    """archive-catalog dry-run scans a directory without writing a catalog file."""
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_catalog

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        extracted = root / "research/_extracted/test_project"
        extracted.mkdir(parents=True)

        (extracted / "README.md").write_text("# Test Project\nContent here.\n", encoding="utf-8")
        (extracted / "pyproject.toml").write_text("[tool]\nname = \"test\"\n", encoding="utf-8")
        (extracted / "src").mkdir(parents=True, exist_ok=True)
        (extracted / "src/main.py").write_text("def main():\n    print('hello')  # test\n\n\n\n\n\n\n", encoding="utf-8")
        (extracted / "docs").mkdir(parents=True, exist_ok=True)
        (extracted / "docs/notes.md").write_text("# Notes\nResearch findings.\n", encoding="utf-8")

        data = collect_archive_catalog(
            "research/_extracted/test_project", write=False, root=str(root)
        )
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("catalog_path") == "",
                 "dry-run must have empty catalog_path")
        _require(data.get("file_count", 0) >= 3,
                 f"file_count must be >= 3, got {data.get('file_count')}")
        _require(data.get("source_name") == "test_project",
                 f"source_name mismatch: {data.get('source_name')}")

        counts = data.get("file_type_counts", {})
        _require(counts.get("markdown", 0) >= 2,
                 f"must have >= 2 markdown files, got {counts.get('markdown', 0)}")
        _require(counts.get("python", 0) >= 1,
                 f"must have >= 1 python file, got {counts.get('python', 0)}")

        imp = data.get("important_files", [])
        imp_types = {i["type"] for i in imp}
        _require("readme" in imp_types, "readme must be in important_files")
        _require("pyproject_toml" in imp_types, "pyproject_toml must be in important_files")

        recs = data.get("recommendations", [])
        _require(len(recs) >= 1, "must have >= 1 recommendation")

        catalog_dir = root / "research/_catalog/archive_catalogs"
        _require(not catalog_dir.exists(),
                 f"dry-run must not create catalog dir: {catalog_dir}")

    print("growth archive-catalog dry-run OK")


# ---------------------------------------------------------------------------
# 33. Growth archive-catalog -- --write persists catalog
# ---------------------------------------------------------------------------

def check_growth_archive_catalog_write() -> None:
    """archive-catalog --write persists the catalog JSON file."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_catalog

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        extracted = root / "research/_extracted/catalog_write_test"
        extracted.mkdir(parents=True)

        (extracted / "README.md").write_text("# Catalog write test\n", encoding="utf-8")
        (extracted / "setup.py").write_text(
            "from setuptools import setup\nsetup(name='test')\n", encoding="utf-8"
        )
        (extracted / "src").mkdir(parents=True, exist_ok=True)
        (extracted / "src/module.py").write_text(
            "def foo():\n    return 42\n\n\n\n\n\n\n\n", encoding="utf-8"
        )

        data = collect_archive_catalog(
            "research/_extracted/catalog_write_test", write=True, root=str(root)
        )
        _require(data.get("ok") is True, "write must set ok=True")
        _require(data.get("dry_run") is False, "write must set dry_run=False")
        _require(bool(data.get("catalog_path")),
                 "catalog_path must be non-empty after write")
        _require(data.get("source_name") == "catalog_write_test",
                 "source_name must match directory name")

        catalog_file = Path(data.get("catalog_path", ""))
        _require(catalog_file.exists(), f"catalog file must exist: {catalog_file}")

        catalog_data = _json.loads(catalog_file.read_text(encoding="utf-8"))
        _require(catalog_data.get("catalog_version") == "link-archive-catalog-v1",
                 "catalog must have correct version")
        _require(catalog_data.get("source_name") == "catalog_write_test",
                 "catalog on-disk source_name must match")
        _require(catalog_data.get("file_count") >= 2,
                 f"catalog on-disk file_count must be >= 2, got {catalog_data.get('file_count')}")

        # Verify extracted files are untouched
        _require((extracted / "README.md").exists(),
                 "original README.md must remain untouched")

    print("growth archive-catalog write OK")


# ---------------------------------------------------------------------------
# 34. Growth archive-catalog -- refuses existing catalog
# ---------------------------------------------------------------------------

def check_growth_archive_catalog_refuses_existing() -> None:
    """archive-catalog --write refuses to overwrite an existing catalog file."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_catalog

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        extracted = root / "research/_extracted/refuse_test"
        extracted.mkdir(parents=True)
        (extracted / "README.md").write_text("# Refuse test\n", encoding="utf-8")

        # First write succeeds
        data1 = collect_archive_catalog(
            "research/_extracted/refuse_test", write=True, root=str(root)
        )
        _require(data1.get("ok") is True, "first write must succeed")

        # Second write must fail
        data2 = collect_archive_catalog(
            "research/_extracted/refuse_test", write=True, root=str(root)
        )
        _require(data2.get("ok") is False,
                 "second write must be blocked")
        _require(isinstance(data2.get("error"), str),
                 "second write must have error string")
        _require("already exists" in data2.get("error", "").lower(),
                 f"error must mention 'already exists', got {data2.get('error')!r}")

    print("growth archive-catalog refuse existing OK")


# ---------------------------------------------------------------------------
# 35. Growth archive-queue -- empty state (no catalogs)
# ---------------------------------------------------------------------------

def check_growth_archive_queue_empty() -> None:
    """collect_archive_queue returns no catalogs when none exist."""
    from link_modes.growth.link_growth_console import collect_archive_queue

    with tempfile.TemporaryDirectory() as td:
        data = collect_archive_queue(root=td)
        _require(isinstance(data, dict), "collect_archive_queue must return a dict")
        _require(data.get("catalog_count") == 0,
                 f"no catalogs must have catalog_count=0, got {data.get('catalog_count')}")
        _require(data.get("queue_count") == 0,
                 f"no catalogs must have queue_count=0, got {data.get('queue_count')}")
        _require(len(data.get("source_queue", [])) == 0,
                 "no catalogs must have empty source_queue")
        warnings = data.get("warnings", [])
        _require(len(warnings) >= 1, "no catalogs must have at least 1 warning")

    print("growth archive-queue empty OK")


# ---------------------------------------------------------------------------
# 36. Growth archive-queue -- populated with ranked entries
# ---------------------------------------------------------------------------

def check_growth_archive_queue_populated() -> None:
    """collect_archive_queue ranks sources from a catalog file."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_queue, _CATALOG_OUTPUT_DIR,
    )

    catalog_data = {
        "catalog_version": "link-archive-catalog-v1",
        "source_name": "queue_populated_test",
        "source_path": "/tmp/extracted/queue_populated_test",
        "catalog_id": "abc12345",
        "created_at": "2026-05-30T00:00:00Z",
        "total_bytes": 5000,
        "total_human": "5K",
        "file_count": 4,
        "directory_count": 2,
        "skipped_count": 0,
        "skipped_details": {},
        "file_type_counts": {"markdown": 3, "python": 1},
        "top_level_dirs": ["docs", "notes"],
        "likely_project_roots": ["."],
        "important_files": [
            {"path": "README.md", "type": "readme", "size_human": "1K"},
        ],
        "candidate_research_sources": [
            {"path": "README.md", "type": "readme_file", "size_bytes": 1024},
            {"path": "docs/design.md", "type": "markdown_doc", "size_bytes": 2048},
            {"path": "docs/research.md", "type": "markdown_doc", "size_bytes": 800},
            {"path": "notes/ideas.md", "type": "markdown_doc", "size_bytes": 600},
        ],
        "recommendations": [],
        "safety_flags": [],
    }

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)

        # Write the catalog, but source_path must point to existing files
        # Update source_path to point into our td
        extracted = root / "extracted" / "queue_populated_test"
        extracted.mkdir(parents=True)
        (extracted / "README.md").write_text("# Test\n", encoding="utf-8")
        (extracted / "docs").mkdir(parents=True, exist_ok=True)
        (extracted / "docs/design.md").write_text("# Design\n", encoding="utf-8")
        (extracted / "docs/research.md").write_text("# Research\n", encoding="utf-8")
        (extracted / "notes").mkdir(parents=True, exist_ok=True)
        (extracted / "notes/ideas.md").write_text("# Ideas\n", encoding="utf-8")

        catalog_data["source_path"] = str(extracted)
        (catalogs_dir / "queue_populated_test.json").write_text(
            _json.dumps(catalog_data), encoding="utf-8"
        )

        data = collect_archive_queue(root=str(root))
        _require(data.get("catalog_count") == 1,
                 f"catalog_count must be 1, got {data.get('catalog_count')}")
        _require(data.get("queue_count", 0) >= 3,
                 f"queue_count must be >= 3, got {data.get('queue_count')}")

        queue = data.get("source_queue", [])
        _require(len(queue) >= 3, f"source_queue must have >= 3 entries, got {len(queue)}")

        # First entry should be highest score
        first = queue[0]
        _require(first.get("rank") == 1, f"first entry rank must be 1, got {first.get('rank')}")
        _require(isinstance(first.get("score"), int),
                 "score must be an int")
        _require(first.get("estimated_value") in ("high", "medium", "low"),
                 f"estimated_value must be high/medium/low, got {first.get('estimated_value')}")
        _require(bool(first.get("reason")), "reason must be non-empty")
        _require(bool(first.get("suggested_command")), "suggested_command must be non-empty")
        _require(first.get("source_type") == "file",
                 "source_type must be 'file'")

        # Scores should be descending
        for i in range(1, len(queue)):
            _require(queue[i]["rank"] == i + 1,
                     f"rank must be sequential, expected {i + 1}, got {queue[i]['rank']}")
            _require(queue[i - 1]["score"] >= queue[i]["score"],
                     f"scores must be descending: {queue[i - 1]['score']} < {queue[i]['score']}")

        recs = data.get("recommendations", [])
        _require(len(recs) >= 1, "must have at least 1 recommendation")

    print("growth archive-queue populated OK")


# ---------------------------------------------------------------------------
# 37. Growth archive-queue -- tolerates invalid catalog JSON
# ---------------------------------------------------------------------------

def check_growth_archive_queue_invalid_catalog() -> None:
    """collect_archive_queue tolerates invalid JSON without crashing."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_queue, _CATALOG_OUTPUT_DIR,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)

        # Write a valid catalog
        valid_catalog = {
            "catalog_version": "link-archive-catalog-v1",
            "source_name": "valid_cat",
            "source_path": str(root),
            "candidate_research_sources": [],
            "important_files": [],
        }
        (catalogs_dir / "valid.json").write_text(
            _json.dumps(valid_catalog), encoding="utf-8"
        )

        # Write an invalid catalog (not JSON)
        (catalogs_dir / "invalid.json").write_text(
            "this is not valid json {{{", encoding="utf-8"
        )

        data = collect_archive_queue(root=str(root))
        _require(data.get("catalog_count") == 1,
                 f"only valid catalog should count, got {data.get('catalog_count')}")

        warnings = data.get("warnings", [])
        invalid_warnings = [w for w in warnings if w.get("type") == "catalog_invalid_json"]
        _require(len(invalid_warnings) >= 1, "must have invalid_json warning")

    print("growth archive-queue invalid catalog OK")


# ---------------------------------------------------------------------------
# 38. Growth archive-mine -- dry-run via --rank
# ---------------------------------------------------------------------------

def check_growth_archive_mine_dry_run_rank() -> None:
    """archive-mine via --rank mines a queue source without writing proposals."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_mine, _CATALOG_OUTPUT_DIR,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        extracted = root / "extracted/mine_test"
        extracted.mkdir(parents=True)
        src_content = (
            "evidence citation source research document\n"
            "missing gap upgrade not in link improve\n"
            "proposal approval candidate human oversight\n"
            "sandbox worktree isolation agent implementation\n"
        )
        (extracted / "README.md").write_text(src_content, encoding="utf-8")

        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)
        catalog = {
            "catalog_version": "link-archive-catalog-v1",
            "source_name": "mine_test",
            "source_path": str(extracted),
            "candidate_research_sources": [
                {"path": "README.md", "type": "readme_file", "size_bytes": 200},
            ],
            "important_files": [
                {"path": "README.md", "type": "readme", "size_human": "200B"},
            ],
            "file_type_counts": {"markdown": 1},
            "top_level_dirs": [],
            "likely_project_roots": [],
            "recommendations": [],
            "safety_flags": [],
            "total_bytes": 200,
            "total_human": "200B",
            "file_count": 1,
            "directory_count": 0,
            "skipped_count": 0,
            "skipped_details": {},
        }
        (catalogs_dir / "mine_test.json").write_text(
            _json.dumps(catalog), encoding="utf-8"
        )

        data = collect_archive_mine(rank="1", write=False, root=str(root))
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("rank") == 1, "rank must be 1")
        _require(data.get("queue_entry") is not None,
                 "queue_entry must be populated when --rank used")
        _require(data.get("candidate_count", 0) >= 1,
                 f"must have >= 1 candidate, got {data.get('candidate_count')}")
        _require(data.get("proposal_count", 0) >= 1,
                 f"must have >= 1 proposal, got {data.get('proposal_count')}")
        _require(data.get("written_paths") == [],
                 "dry-run must have empty written_paths")
        _require(len(data.get("proposals", [])) == data.get("proposal_count", 0),
                 "proposals list length must match proposal_count")

        # Verify no proposal files were written
        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0, f"dry-run must not write proposal files, found {len(p_files)}")

    print("growth archive-mine dry-run rank OK")


# ---------------------------------------------------------------------------
# 39. Growth archive-mine -- dry-run via --source
# ---------------------------------------------------------------------------

def check_growth_archive_mine_dry_run_source() -> None:
    """archive-mine via --source bypasses queue, returns no queue_entry."""
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_archive_mine

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src = root / "research_input.md"
        src.write_text(
            "evidence citation source research document\n"
            "missing gap upgrade not in link improve\n",
            encoding="utf-8",
        )

        data = collect_archive_mine(source=str(src), write=False, root=str(root))
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("rank") is None,
                 "rank must be None when --source used without --rank")
        _require(data.get("queue_entry") is None,
                 "queue_entry must be None when --source used")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("written_paths") == [],
                 "dry-run must have empty written_paths")

    print("growth archive-mine dry-run source OK")


# ---------------------------------------------------------------------------
# 40. Growth archive-mine -- error states
# ---------------------------------------------------------------------------

def check_growth_archive_mine_errors() -> None:
    """archive-mine returns ok=False for invalid/out-of-range ranks."""
    from link_modes.growth.link_growth_console import collect_archive_mine

    with tempfile.TemporaryDirectory() as td:
        rank_out = collect_archive_mine(rank="999", write=False, root=td)
        _require(rank_out.get("ok") is False,
                 "rank out of range must set ok=False")
        _require(isinstance(rank_out.get("error"), str),
                 "rank out of range must have error string")
        _require("out of range" in rank_out.get("error", "").lower() or
                 "no queue" in rank_out.get("error", "").lower(),
                 f"error must mention out of range/no queue, got {rank_out.get('error')!r}")

        rank_bad = collect_archive_mine(rank="abc", write=False, root=td)
        _require(rank_bad.get("ok") is False,
                 "non-integer rank must set ok=False")
        _require("integer" in rank_bad.get("error", "").lower(),
                 "non-integer rank error must mention 'integer'")

        rank_neg = collect_archive_mine(rank="-1", write=False, root=td)
        _require(rank_neg.get("ok") is False,
                 "negative rank must set ok=False")

    print("growth archive-mine errors OK")


# ---------------------------------------------------------------------------
# 41. Growth archive-batch-mine -- dry-run processes top 3
# ---------------------------------------------------------------------------

def check_growth_archive_batch_mine_dry_run() -> None:
    """archive-batch-mine dry-run processes top N sources, writes nothing."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_batch_mine, _CATALOG_OUTPUT_DIR,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)

        # Create two sources with mining-worthy content
        for name in ("source_a", "source_b"):
            ext = root / "extracted" / name
            ext.mkdir(parents=True)
            (ext / "README.md").write_text(
                "evidence citation source research document\n"
                "missing gap upgrade not in link improve\n"
                "proposal approval candidate human oversight\n",
                encoding="utf-8",
            )
            catalog = {
                "catalog_version": "link-archive-catalog-v1",
                "source_name": name,
                "source_path": str(ext),
                "candidate_research_sources": [
                    {"path": "README.md", "type": "readme_file", "size_bytes": 200},
                ],
                "important_files": [
                    {"path": "README.md", "type": "readme", "size_human": "200B"},
                ],
                "file_type_counts": {"markdown": 1},
                "top_level_dirs": [],
                "likely_project_roots": [],
                "recommendations": [],
                "safety_flags": [],
                "total_bytes": 200,
                "total_human": "200B",
                "file_count": 1,
                "directory_count": 0,
                "skipped_count": 0,
                "skipped_details": {},
            }
            (catalogs_dir / f"{name}.json").write_text(
                _json.dumps(catalog), encoding="utf-8"
            )

        data = collect_archive_batch_mine(top=2, write=False, root=str(root))
        _require(data.get("ok") is True, "batch dry-run must set ok=True")
        _require(data.get("dry_run") is True,
                 "batch dry-run must set dry_run=True")
        _require(data.get("selected_count") == 2,
                 "selected_count must be 2")
        _require(data.get("processed_count") == 2,
                 "all sources must be processed")
        _require(data.get("failed_count") == 0,
                 "no sources should fail")
        _require(data.get("candidate_count_total", 0) >= 2,
                 "must have candidates across both sources")
        _require(data.get("proposal_count_total", 0) >= 2,
                 "must have proposals across both sources")
        _require(len(data.get("written_paths", [])) == 0,
                 "dry-run must have empty written_paths")

        per_source = data.get("per_source_results", [])
        _require(len(per_source) == 2,
                 "per_source_results must have 2 entries")
        for ps in per_source:
            _require(isinstance(ps.get("ok"), bool),
                     "per-source must have ok field")
            _require(ps.get("queue_score", -1) >= 0,
                     "per-source must have queue_score >= 0")

        # Check deduplication: both sources have same content so proposals overlap
        uq = data.get("unique_proposal_count", 0)
        pr = data.get("proposal_count_total", 0)
        _require(uq <= pr,
                 f"unique proposals ({uq}) must be <= raw total ({pr})")

        # Verify no proposal files written
        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0,
                 f"dry-run must not write proposal files, found {len(p_files)}")

    print("growth archive-batch-mine dry-run OK")


# ---------------------------------------------------------------------------
# 42. Growth archive-batch-mine -- top clamping
# ---------------------------------------------------------------------------

def check_growth_archive_batch_mine_top_clamp() -> None:
    """archive-batch-mine clamps top > 10 and rejects invalid values."""
    from link_modes.growth.link_growth_console import (
        collect_archive_batch_mine, _MAX_BATCH_TOP,
    )

    with tempfile.TemporaryDirectory() as td:
        data_top15 = collect_archive_batch_mine(top=15, write=False, root=td)
        _require(data_top15.get("top") == _MAX_BATCH_TOP,
                 f"top 15 must be clamped to {_MAX_BATCH_TOP}, got {data_top15.get('top')}")
        warnings = data_top15.get("warnings", [])
        cap_warnings = [w for w in warnings if "capped" in w.lower()]
        _require(len(cap_warnings) >= 1, "must have capped warning")

        data_top0 = collect_archive_batch_mine(top=0, write=False, root=td)
        _require(data_top0.get("ok") is False,
                 "top 0 must set ok=False")
        _require("must be >= 1" in data_top0.get("error", "").lower(),
                 "top 0 error must mention 'must be >= 1'")

    print("growth archive-batch-mine top clamp OK")


# ---------------------------------------------------------------------------
# 43. Growth archive-batch-mine -- partial failure
# ---------------------------------------------------------------------------

def check_growth_archive_batch_mine_partial_failure() -> None:
    """archive-batch-mine continues on per-source failures."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_batch_mine, _CATALOG_OUTPUT_DIR,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)

        # Source 1: valid
        ext1 = root / "extracted/good_source"
        ext1.mkdir(parents=True)
        (ext1 / "README.md").write_text(
            "evidence citation source research document\n"
            "missing gap upgrade not in link improve\n",
            encoding="utf-8",
        )

        # Source 2: empty content — likely produces zero candidates
        ext2 = root / "extracted/empty_source"
        ext2.mkdir(parents=True)
        (ext2 / "README.md").write_text("just random text nothing relevant", encoding="utf-8")

        for name, ext_path in [("good_source", ext1), ("empty_source", ext2)]:
            catalog = {
                "catalog_version": "link-archive-catalog-v1",
                "source_name": name,
                "source_path": str(ext_path),
                "candidate_research_sources": [
                    {"path": "README.md", "type": "readme_file", "size_bytes": 50},
                ],
                "important_files": [],
                "file_type_counts": {},
                "top_level_dirs": [],
                "likely_project_roots": [],
                "recommendations": [],
                "safety_flags": [],
                "total_bytes": 50,
                "total_human": "50B",
                "file_count": 1,
                "directory_count": 0,
                "skipped_count": 0,
                "skipped_details": {},
            }
            (catalogs_dir / f"{name}.json").write_text(
                _json.dumps(catalog), encoding="utf-8"
            )

        data = collect_archive_batch_mine(top=2, write=False, root=str(root))
        _require(data.get("ok") is True,
                 "batch must be ok even with partial failure")
        _require(data.get("processed_count", 0) >= 1,
                 "at least one source must be processed")
        _require(data.get("selected_count") == 2,
                 "both sources must be selected")

        per_source = data.get("per_source_results", [])
        _require(len(per_source) == 2,
                 "per_source_results must have 2 entries")

    print("growth archive-batch-mine partial failure OK")


# ---------------------------------------------------------------------------
# 44. Growth archive-code-queue -- empty state
# ---------------------------------------------------------------------------

def check_growth_archive_code_queue_empty() -> None:
    """archive-code-queue returns empty state when no catalogs exist."""
    from link_modes.growth.link_growth_console import collect_archive_code_queue

    with tempfile.TemporaryDirectory() as td:
        data = collect_archive_code_queue(root=td)
        _require(isinstance(data, dict), "must return dict")
        _require(data.get("catalog_count") == 0,
                 f"catalog_count must be 0, got {data.get('catalog_count')}")
        _require(data.get("queue_count") == 0, "queue_count must be 0")
        warnings = data.get("warnings", [])
        _require(len(warnings) >= 1, "must have warnings")

    print("growth archive-code-queue empty OK")


# ---------------------------------------------------------------------------
# 45. Growth archive-code-queue -- populated with ranked code files
# ---------------------------------------------------------------------------

def check_growth_archive_code_queue_populated() -> None:
    """archive-code-queue ranks TypeScript/JS files by architecture value."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_archive_code_queue, _CATALOG_OUTPUT_DIR,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ext = root / "extracted/ts_proj"
        ext.mkdir(parents=True)
        (ext / "src").mkdir(parents=True)
        (ext / "src/agent.ts").write_text(
            "// Linked agent orchestrator implementation\n"
            "// This file configures the agent dispatch pipeline.\n",
            encoding="utf-8",
        )
        (ext / "src/router.ts").write_text(
            "// Tool routing dispatch table\n"
            "// Maps tool names to registered handler functions.\n",
            encoding="utf-8",
        )
        (ext / "src/utils").mkdir(parents=True, exist_ok=True)
        (ext / "src/utils/helper.ts").write_text(
            "// Shared utility functions\n"
            "// Used by agent, router, and pipeline modules.\n",
            encoding="utf-8",
        )
        wrapper_dir = ext / "commands/foo"
        wrapper_dir.mkdir(parents=True)
        (wrapper_dir / "index.ts").write_text(
            "// Foo command index wrapper with sibling implementation files.\n"
            "export const fooCommandName = 'foo';\n",
            encoding="utf-8",
        )
        (wrapper_dir / "run.ts").write_text(
            "// Foo command handler with agent workflow routing.\n"
            "export function runFooCommand() { return 'foo'; }\n",
            encoding="utf-8",
        )
        (wrapper_dir / "schema.ts").write_text(
            "// Foo command schema and validation metadata.\n"
            "export const fooSchema = { command: 'foo' };\n",
            encoding="utf-8",
        )
        resolve_dir = ext / "commands/bar"
        resolve_dir.mkdir(parents=True)
        (resolve_dir / "index.js").write_text(
            "// Bar command wrapper with local implementation target.\n"
            "export { runBarCommand } from './main.js';\n",
            encoding="utf-8",
        )
        (resolve_dir / "main.js").write_text(
            "// Bar command main implementation with agent workflow routing.\n"
            "export function runBarCommand() { return 'bar'; }\n",
            encoding="utf-8",
        )
        trivial_dir = ext / "commands/empty"
        trivial_dir.mkdir(parents=True)
        (trivial_dir / "index.js").write_text(
            "export const empty = true;\n",
            encoding="utf-8",
        )
        (ext / "package.json").write_text(
            '{"name":"test-project","scripts":{"build":"tsc"}}',
            encoding="utf-8",
        )
        (ext / "tsconfig.json").write_text(
            '{"compilerOptions":{"target":"es2020","module":"commonjs"}}',
            encoding="utf-8",
        )
        # Low-value / skipped
        (ext / "src/node_modules").mkdir(parents=True, exist_ok=True)
        (ext / "src/node_modules/skip.ts").write_text(
            "// This file should be skipped because it is in node_modules\n"
            "// It is in a directory excluded by the skip-dir list.\n",
            encoding="utf-8",
        )

        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)
        catalog = {
            "catalog_version": "link-archive-catalog-v1",
            "source_name": "ts_proj",
            "source_path": str(ext),
            "candidate_research_sources": [],
            "important_files": [
                {"path": "package.json", "type": "package_json", "size_human": "17B"},
                {"path": "tsconfig.json", "type": "tsconfig_json", "size_human": "2B"},
            ],
            "file_type_counts": {"typescript": 5, "json": 2},
            "top_level_dirs": ["src"],
            "likely_project_roots": [],
            "recommendations": [],
            "safety_flags": [],
            "total_bytes": 200,
            "total_human": "200B",
            "file_count": 7,
            "directory_count": 3,
            "skipped_count": 0,
            "skipped_details": {},
        }
        (catalogs_dir / "ts_proj.json").write_text(
            _json.dumps(catalog), encoding="utf-8"
        )

        data = collect_archive_code_queue(top=10, root=str(root))
        _require(data.get("catalog_count") == 1,
                 f"catalog_count must be 1, got {data.get('catalog_count')}")
        _require(data.get("queue_count", 0) >= 3,
                 f"queue_count must be >= 3, got {data.get('queue_count')}")

        queue = data.get("source_queue", [])
        _require(len(queue) >= 3, "source_queue must have >= 3 entries")

        # agent.ts or router.ts should be top-ranked
        first = queue[0]
        _require(first.get("rank") == 1, "first entry rank must be 1")
        _require(first.get("score", 0) >= 10,
                 f"top file should score >= 10, got {first.get('score')}")
        _require(first.get("estimated_value") in ("high", "medium"),
                 "top file should be high or medium value")
        _require("archive-code-brief --source" in first.get("suggested_command", ""),
                 "code queue suggested_command must route to archive-code-brief")
        _require("archive-mine --source" not in first.get("suggested_command", ""),
                 "code queue suggested_command must not route directly to archive-mine")
        recs = data.get("recommendations", [])
        _require(recs and "archive-code-brief --source" in recs[0],
                 "code queue recommendations must route to archive-code-brief")

        for entry in queue:
            recommended = entry.get("recommended_source_path")
            _require(bool(recommended), "queue entry must include recommended_source_path")
            _require(entry.get("recommended_source_type") in ("file", "directory"),
                     "queue entry must include recommended_source_type")
            _require(recommended in entry.get("suggested_command", ""),
                     "suggested_command must use recommended_source_path")

        index_entry = next(
            e for e in queue
            if e.get("source_path", "").endswith("commands/foo/index.ts")
        )
        _require(index_entry.get("is_index_wrapper") is True,
                 "tiny index.ts must be marked as index wrapper")
        _require(index_entry.get("sibling_code_file_count") == 2,
                 "index wrapper must count sibling code files")
        _require(index_entry.get("recommended_source_path") == str(wrapper_dir),
                 "index wrapper with siblings must recommend parent directory")
        _require(index_entry.get("recommended_source_type") == "directory",
                 "index wrapper with siblings must recommend directory source type")
        _require(
            index_entry.get("suggested_command") ==
            f"python3 link.py growth archive-code-brief --source {wrapper_dir} --write",
            "index wrapper suggested_command must brief the parent directory",
        )
        _require(index_entry.get("resolved_target_path") == "",
                 "directory fallback wrapper must have empty resolved_target_path")
        _require(index_entry.get("resolved_target_type") == "",
                 "directory fallback wrapper must have empty resolved_target_type")

        resolved_entry = next(
            e for e in queue
            if e.get("source_path", "").endswith("commands/bar/index.js")
        )
        resolved_target = str(resolve_dir / "main.js")
        _require(resolved_entry.get("is_index_wrapper") is True,
                 "tiny index.js must be marked as index wrapper")
        _require(resolved_entry.get("resolved_target_path") == resolved_target,
                 "tiny index.js must resolve local main.js target")
        _require(resolved_entry.get("resolved_target_type") == "file",
                 "resolved target type must be file")
        _require(resolved_entry.get("recommended_source_path") == resolved_target,
                 "resolved wrapper must recommend target file")
        _require(
            resolved_entry.get("suggested_command") ==
            f"python3 link.py growth archive-code-brief --source {resolved_target} --write",
            "resolved wrapper suggested_command must brief resolved target",
        )

        unresolved = [
            e for e in queue
            if e.get("source_path", "").endswith("commands/empty/index.js")
        ]
        _require(not unresolved,
                 "tiny index.js with no safe local target must not stay in source_queue")

        agent_entry = next(
            e for e in queue
            if e.get("source_path", "").endswith("src/agent.ts")
        )
        _require(agent_entry.get("is_index_wrapper") is False,
                 "non-index code file must not be marked as index wrapper")
        _require(agent_entry.get("recommended_source_path") == agent_entry.get("source_path"),
                 "standalone non-index code file must recommend itself")
        _require(agent_entry.get("recommended_source_type") == "file",
                 "standalone non-index code file must recommend file source type")

        # Verify skipped contains node_modules and unresolved tiny wrappers
        skipped = data.get("skipped_entries", [])
        node_skipped = [s for s in skipped if "node_modules" in s.get("path", "")]
        _require(len(node_skipped) >= 1, "node_modules file must be skipped")
        unresolved_skipped = [
            s for s in skipped
            if s.get("path", "").endswith("commands/empty/index.js")
        ]
        _require(unresolved_skipped,
                 "tiny index wrapper with no target must appear in skipped_entries")

        # Verify no proposal files written
        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0, "must not write proposal files")

    print("growth archive-code-queue populated OK")


# ---------------------------------------------------------------------------
# 46. Growth archive-code-queue -- top clamping
# ---------------------------------------------------------------------------

def check_growth_archive_code_queue_top_clamp() -> None:
    """archive-code-queue clamps top > max and rejects invalid values."""
    from link_modes.growth.link_growth_console import (
        collect_archive_code_queue, _MAX_CODE_QUEUE_TOP,
    )

    with tempfile.TemporaryDirectory() as td:
        data = collect_archive_code_queue(top=25, root=td)
        _require(data.get("top_requested") == _MAX_CODE_QUEUE_TOP,
                 f"top 25 must be clamped to {_MAX_CODE_QUEUE_TOP}")
        warnings = data.get("warnings", [])
        cap = [w for w in warnings if "capped" in str(w).lower()]
        _require(len(cap) >= 1, "must have capped warning")

    print("growth archive-code-queue top clamp OK")



# ---------------------------------------------------------------------------
# 47. Growth code-brief-propose-batch -- dry-run preview
# ---------------------------------------------------------------------------

def check_growth_code_brief_propose_batch() -> None:
    """code-brief-propose-batch previews top code queue proposals without writes."""
    import contextlib
    import io
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import (
        collect_code_brief_propose_batch,
        code_brief_propose_batch_main,
        _CATALOG_OUTPUT_DIR,
        _MAX_CODE_QUEUE_TOP,
    )

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        ext = root / "extracted/batch_proj"
        (ext / "src").mkdir(parents=True)
        (ext / "src/agent.ts").write_text(
            "// Agent tool orchestration workflow.\n"
            "export function agentToolRouter() { return 'agent'; }\n",
            encoding="utf-8",
        )
        (ext / "src/router.ts").write_text(
            "// Router dispatch table for command handlers.\n"
            "export function routeCommand() { return 'router'; }\n",
            encoding="utf-8",
        )
        catalogs_dir = root / _CATALOG_OUTPUT_DIR
        catalogs_dir.mkdir(parents=True)
        catalog = {
            "catalog_version": "link-archive-catalog-v1",
            "source_name": "batch_proj",
            "source_path": str(ext),
            "candidate_research_sources": [],
            "important_files": [],
            "file_type_counts": {"typescript": 2},
            "top_level_dirs": ["src"],
            "likely_project_roots": [],
            "recommendations": [],
            "safety_flags": [],
            "total_bytes": 200,
            "total_human": "200B",
            "file_count": 2,
            "directory_count": 1,
            "skipped_count": 0,
            "skipped_details": {},
        }
        (catalogs_dir / "batch_proj.json").write_text(
            _json.dumps(catalog), encoding="utf-8"
        )

        data = collect_code_brief_propose_batch(top=2, root=td)
        _require(data.get("ok") is True, "batch preview must set ok=True")
        _require(data.get("dry_run") is True, "batch preview must be dry-run")
        _require(data.get("queued_source_count") == 2,
                 f"top 2 must queue 2 sources, got {data.get('queued_source_count')}")
        _require(data.get("processed_source_count") == 2,
                 "top 2 must process 2 sources")
        _require(data.get("candidate_count", 0) >= 2,
                 "batch preview must produce candidate previews")
        _require(data.get("proposal_count") == data.get("candidate_count"),
                 "proposal_count must match candidate_count")
        _require(isinstance(data.get("sources"), list) and len(data["sources"]) == 2,
                 "batch preview must include two per-source summaries")
        for source in data["sources"]:
            _require(bool(source.get("source_path")), "source summary must include source_path")
            _require("archive-code-brief --source" in source.get("suggested_brief_command", ""),
                     "source summary must include brief command")
            _require(isinstance(source.get("warnings"), list),
                     "source summary warnings must be a list")

        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0, "batch preview must not write proposal files")
        briefs_dir = root / "research/_catalog/code_briefs"
        b_files = list(briefs_dir.glob("*.md")) if briefs_dir.exists() else []
        _require(len(b_files) == 0, "batch preview must not write code brief files")

        written = collect_code_brief_propose_batch(top=2, root=td, write=True)
        _require(written.get("ok") is True, "batch --write must set ok=True")
        _require(written.get("dry_run") is False, "batch --write must report dry_run=False")
        written_paths = written.get("written_paths", [])
        _require(len(written_paths) == written.get("proposal_count"),
                 "batch --write written_paths must match proposal_count")
        for written_path in written_paths:
            _require(Path(written_path).exists(),
                     f"batch --write path must exist: {written_path}")
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == len(set(written_paths)),
                 "batch --write must persist proposal files without extra files")
        b_files = list(briefs_dir.glob("*.md")) if briefs_dir.exists() else []
        _require(len(b_files) == 0, "batch --write must not write code brief files")

        write_json_out = io.StringIO()
        with contextlib.redirect_stdout(write_json_out):
            write_rc = code_brief_propose_batch_main([
                "--top", "2", "--write", "--json", "--root", td,
            ])
        _require(write_rc == 0, f"batch --write --json command must return 0, got {write_rc}")
        write_rendered = _json.loads(write_json_out.getvalue())
        _require(write_rendered.get("dry_run") is False,
                 "batch --write --json output must report dry_run=False")
        _require(len(write_rendered.get("written_paths", [])) == write_rendered.get("proposal_count"),
                 "batch --write --json output must include written_paths")

        clamped = collect_code_brief_propose_batch(top=25, root=td)
        _require(clamped.get("top_requested") == _MAX_CODE_QUEUE_TOP,
                 "batch preview top value must clamp to max code queue top")
        clamp_warnings = [w for w in clamped.get("warnings", []) if "capped" in str(w)]
        _require(clamp_warnings, "clamped batch preview must include capped warning")

        json_out = io.StringIO()
        with contextlib.redirect_stdout(json_out):
            rc = code_brief_propose_batch_main([
                "--top", "2", "--json", "--root", td,
            ])
        _require(rc == 0, f"batch --json command must return 0, got {rc}")
        rendered = _json.loads(json_out.getvalue())
        _require(rendered.get("queued_source_count") == 2,
                 "batch --json output must include queued_source_count")
        _require(isinstance(rendered.get("sources"), list) and len(rendered["sources"]) == 2,
                 "batch --json output must include per-source summaries")

    with tempfile.TemporaryDirectory() as empty_td:
        empty = collect_code_brief_propose_batch(top=2, root=empty_td)
        _require(empty.get("ok") is True, "empty batch preview must still be ok")
        _require(empty.get("queued_source_count") == 0,
                 "empty batch preview must have 0 queued sources")
        _require(empty.get("processed_source_count") == 0,
                 "empty batch preview must have 0 processed sources")
        _require(empty.get("next_commands") and "archive-code-queue" in empty["next_commands"][0],
                 "empty batch preview must suggest archive-code-queue next")
        _require(empty.get("warnings"), "empty batch preview must include helpful warning")

    print("growth code-brief-propose-batch OK")



# ---------------------------------------------------------------------------
# 47. Ruflo upgrade intake -- pure ranking foundation
# ---------------------------------------------------------------------------

def check_ruflo_upgrade_intake_helper() -> None:
    """Ruflo-derived findings normalize into deterministic ranked candidates."""
    from link_modes.growth.link_growth_console import (
        RUFLO_RECOMMENDATIONS,
        RUFLO_RISK_LABELS,
        RUFLO_UPGRADE_CATEGORIES,
        RUFLO_UPGRADE_INTAKE_VERSION,
        build_ruflo_upgrade_intake,
        ruflo_upgrade_intake_from_json,
        ruflo_upgrade_intake_to_json,
        score_ruflo_upgrade_candidate,
        validate_ruflo_upgrade_candidate,
        validate_ruflo_upgrade_intake,
    )

    findings = [
        {
            "title": "Profile-gated worker dispatch",
            "category": "worker_routing",
            "risk_level": "low",
            "summary": "Ruflo routes work through dispatch profiles before tool use.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/orchestrator.ts",
            "source_kind": "code_brief",
            "evidence": ["worker dispatcher", "profile gate"],
        },
        {
            "title": "Lifecycle hook pipeline receipts",
            "description": "Hook pipeline records preflight and postflight decisions.",
            "risk": "medium",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/hooks/index.ts",
            "source_kind": "code_brief",
            "signals": ["hook", "pipeline"],
        },
        {
            "title": "Large autonomous swarm executor",
            "category": "swarm_orchestration",
            "risk": "high",
            "summary": "A broad swarm executor pattern needs review before Link adoption.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/v3/swarm.ts",
            "source_kind": "research",
        },
    ]

    intake = build_ruflo_upgrade_intake(findings, source_label="ruflo")
    _require(intake["intake_version"] == RUFLO_UPGRADE_INTAKE_VERSION,
             "Ruflo intake version mismatch")
    _require(intake["candidate_count"] == 3,
             "Ruflo intake candidate_count must match findings")
    _require(set(intake["categories"]) == set(RUFLO_UPGRADE_CATEGORIES),
             "Ruflo intake must expose stable categories")
    validate_ruflo_upgrade_intake(intake)

    candidates = intake["candidates"]
    scores = [candidate["score"] for candidate in candidates]
    _require(scores == sorted(scores, reverse=True),
             "Ruflo candidates must be sorted by descending score")
    top = candidates[0]
    _require(top["category"] == "worker_routing",
             "low-risk worker routing candidate should rank first")
    _require(top["recommendation"] == "accept",
             "strong low-risk Ruflo candidate should recommend accept")
    _require(top["risk_level"] in RUFLO_RISK_LABELS,
             "Ruflo risk label must be stable")
    _require(top["recommendation"] in RUFLO_RECOMMENDATIONS,
             "Ruflo recommendation must be stable")
    _require(top["reason"], "Ruflo candidate must include a Link need reason")
    _require(top["source_path"].endswith("orchestrator.ts"),
             "Ruflo candidate must preserve source_path")
    _require(top["source_kind"] == "code_brief",
             "Ruflo candidate must preserve source_kind")

    same = score_ruflo_upgrade_candidate(findings[0], source_label="ruflo")
    _require(same["candidate_id"] == top["candidate_id"],
             "Ruflo candidate id must be deterministic")

    encoded = ruflo_upgrade_intake_to_json(intake)
    _require(encoded == ruflo_upgrade_intake_to_json(intake),
             "Ruflo intake JSON serialization must be stable")
    decoded = ruflo_upgrade_intake_from_json(encoded)
    _require(decoded == intake, "Ruflo intake JSON round-trip must preserve data")

    inferred = score_ruflo_upgrade_candidate({
        "title": "Security approval sandbox",
        "summary": "Approval policy gate for sandboxed tool use.",
        "source_path": "research/_extracted/ruflo-main/security.ts",
        "risk": "safe",
    })
    _require(inferred["category"] == "security_gate",
             "Ruflo category inference must detect security gate patterns")
    _require(inferred["risk_level"] == "low",
             "Ruflo risk normalization must map safe to low")
    validate_ruflo_upgrade_candidate(inferred)

    limited = build_ruflo_upgrade_intake(findings, limit=2)
    _require(limited["candidate_count"] == 2,
             "Ruflo intake limit must clamp result count")

    bad = dict(top)
    bad["category"] = "not_a_category"
    try:
        validate_ruflo_upgrade_candidate(bad)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid Ruflo category must be rejected")

    print("ruflo upgrade intake helper OK")


def check_ruflo_upgrade_plan_helper() -> None:
    """Ruflo intake candidates group into an auditor-gated implementation plan."""
    from link_modes.growth.link_growth_console import (
        RUFLO_UPGRADE_PLAN_MAX_TOP,
        RUFLO_UPGRADE_PLAN_VERSION,
        build_ruflo_upgrade_intake,
        collect_ruflo_upgrade_plan,
        ruflo_upgrade_plan_from_json,
        ruflo_upgrade_plan_to_json,
        validate_ruflo_upgrade_plan,
    )

    findings = [
        {
            "title": "Self-learning feedback receipts",
            "summary": "Reflection hooks can turn run results into future Growth ranking signals.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/reflection.ts",
            "source_kind": "code_brief",
            "risk": "low",
            "signals": ["self-learning", "feedback", "reflection"],
        },
        {
            "title": "Self-learning feedback receipts",
            "summary": "Duplicate with the same title/category/source should collapse.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/reflection.ts",
            "source_kind": "code_brief",
            "risk": "low",
            "signals": ["self-learning"],
        },
        {
            "title": "Profile gate before dispatch",
            "category": "security_gate",
            "risk_level": "low",
            "summary": "Route every worker dispatch through profile and permission gates.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/security/gate.ts",
            "source_kind": "code_brief",
            "evidence": ["approval gate", "sandbox policy"],
        },
        {
            "title": "Swarm coordinator review",
            "category": "swarm_orchestration",
            "risk": "high",
            "summary": "Broad swarm orchestration requires design review before implementation.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/v3/swarm.ts",
            "source_kind": "research",
        },
        {
            "title": "Dashboard latency metrics",
            "category": "performance",
            "risk": "medium",
            "summary": "Metrics can reveal slow Growth queue and mining stages.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/metrics.ts",
            "source_kind": "research",
        },
    ]
    intake = build_ruflo_upgrade_intake(findings, source_label="ruflo")
    plan = collect_ruflo_upgrade_plan(intake, top=10, source_label="ruflo")
    same_plan = collect_ruflo_upgrade_plan(intake, top=10, source_label="ruflo")

    _require(plan["plan_version"] == RUFLO_UPGRADE_PLAN_VERSION,
             "Ruflo plan version mismatch")
    _require(plan["plan_id"] == same_plan["plan_id"],
             "Ruflo plan_id must be deterministic")
    _require(plan["dry_run"] is True and plan["write_allowed"] is False,
             "Ruflo plan must remain read-only")
    _require(plan["automation_allowed"] is False,
             "Ruflo plan must not allow automation")
    _require(plan["auditor_gate"]["required"] is True,
             "Ruflo plan must require auditor gate")
    _require(plan["candidate_count"] == 5,
             "Ruflo plan candidate_count must include input candidates")
    _require(plan["duplicate_count"] == 1,
             "Ruflo plan must report duplicate candidates")
    _require(plan["unique_candidate_count"] == 4,
             "Ruflo plan must dedupe title/category/source duplicates")
    _require(len(plan["ranked_candidates"]) == 4,
             "Ruflo plan must rank unique candidates")

    sections = plan["sections"]
    _require(sections["self_learning_upgrades"],
             "Ruflo plan must group self-learning candidates")
    _require(sections["safety_control_plane_upgrades"],
             "Ruflo plan must group safety/control-plane candidates")
    _require(sections["workflow_parallelism_upgrades"],
             "Ruflo plan must group workflow/parallelism candidates")
    _require(sections["observability_dashboard_upgrades"],
             "Ruflo plan must group observability/performance candidates")
    _require(sections["fast_wins"],
             "Ruflo plan must identify fast wins")
    _require(plan["recommended_next_slice"].get("candidate_id"),
             "Ruflo plan must recommend a next audited slice")
    _require(plan["rollback_guidance"], "Ruflo plan must include rollback guidance")
    _require(plan["verification_commands"],
             "Ruflo plan must include verification commands")

    encoded = ruflo_upgrade_plan_to_json(plan)
    _require(encoded == ruflo_upgrade_plan_to_json(plan),
             "Ruflo plan JSON serialization must be stable")
    decoded = ruflo_upgrade_plan_from_json(encoded)
    _require(decoded == plan, "Ruflo plan JSON round-trip must preserve data")
    validate_ruflo_upgrade_plan(plan)

    clamped = collect_ruflo_upgrade_plan(findings, top=99, source_label="ruflo")
    _require(clamped["top_used"] == RUFLO_UPGRADE_PLAN_MAX_TOP,
             "Ruflo plan top must clamp to max")
    _require(clamped["warnings"], "Ruflo plan top clamp must emit warning")

    raised = collect_ruflo_upgrade_plan(findings, top=0, source_label="ruflo")
    _require(raised["top_used"] == 1, "Ruflo plan top below 1 must raise to 1")
    _require(raised["warnings"], "Ruflo plan low top must emit warning")

    try:
        collect_ruflo_upgrade_plan({"not_candidates": []})
    except ValueError:
        pass
    else:
        raise AssertionError("Ruflo plan invalid input must be rejected")

    bad_plan = dict(plan)
    bad_plan["automation_allowed"] = True
    try:
        validate_ruflo_upgrade_plan(bad_plan)
    except ValueError:
        pass
    else:
        raise AssertionError("Ruflo plan must reject automation_allowed=True")

    print("ruflo upgrade plan helper OK")


def check_self_learning_feedback_receipt_helper() -> None:
    """Self-learning feedback receipts are deterministic and aggregatable."""
    from link_modes.growth.link_growth_console import (
        SELF_LEARNING_FEEDBACK_STATUSES,
        SELF_LEARNING_FEEDBACK_VERSION,
        build_self_learning_feedback_receipt,
        self_learning_feedback_from_json,
        self_learning_feedback_to_json,
        summarize_self_learning_feedback,
        validate_self_learning_feedback_receipt,
    )

    candidate = {
        "candidate_id": "ruflo-profile-dispatch-123",
        "proposal_id": "profile-dispatch-proposal",
        "title": "Profile-gated worker dispatch",
        "category": "worker_routing",
        "risk_level": "low",
        "recommendation": "accept",
        "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/orchestrator.ts",
    }
    accepted = build_self_learning_feedback_receipt(
        candidate,
        status="accepted",
        reason="High leverage and already matches Link profile gate direction.",
        confidence=0.92,
        tags=["Ruflo", "Worker Routing", "ruflo"],
        metadata={"reviewer": "auditor", "slice": "feedback"},
        reviewed_at="2026-05-31T00:00:00Z",
    )
    accepted_same = build_self_learning_feedback_receipt(
        candidate,
        status="accept",
        reason="High leverage and already matches Link profile gate direction.",
        confidence=0.92,
        tags=["ruflo", "worker_routing"],
        metadata={"reviewer": "different"},
        reviewed_at="2026-05-31T00:00:01Z",
    )

    _require(accepted["feedback_version"] == SELF_LEARNING_FEEDBACK_VERSION,
             "feedback version mismatch")
    _require(accepted["feedback_id"] == accepted_same["feedback_id"],
             "feedback_id must be deterministic from candidate/status/reason/confidence/tags")
    _require(accepted["status"] == "accepted", "accepted status must be preserved")
    _require(accepted["confidence"] == 0.92, "confidence must be normalized")
    _require(accepted["candidate_id"] == candidate["candidate_id"],
             "candidate_id must be preserved")
    _require(accepted["proposal_id"] == candidate["proposal_id"],
             "proposal_id must be preserved")
    _require(accepted["tags"] == ["ruflo", "worker_routing"],
             "tags must be normalized and deduplicated")
    _require(accepted["metadata"]["reviewer"] == "auditor",
             "metadata must be preserved")
    validate_self_learning_feedback_receipt(accepted)

    encoded = self_learning_feedback_to_json(accepted)
    _require(encoded == self_learning_feedback_to_json(accepted),
             "feedback JSON serialization must be stable")
    decoded = self_learning_feedback_from_json(encoded)
    _require(decoded == accepted, "feedback JSON round-trip must preserve data")

    rejected = build_self_learning_feedback_receipt(
        {
            "candidate_id": "ruflo-swarm-999",
            "title": "Large swarm executor",
            "category": "swarm_orchestration",
            "risk_level": "high",
            "recommendation": "review",
        },
        status="rejected",
        reason="Too broad for current safe slice.",
        confidence=1.0,
        tags=["too_large"],
    )
    deferred = build_self_learning_feedback_receipt(
        {
            "proposal_id": "metrics-dashboard-proposal",
            "title": "Dashboard latency metrics",
            "category": "performance",
            "risk_level": "medium",
            "recommendation": "review",
        },
        status="defer",
        reason="Needs a smaller dashboard-only plan first.",
        confidence=0.5,
        tags=["observability"],
    )
    _require(rejected["status"] == "rejected", "rejected status must be supported")
    _require(deferred["status"] == "deferred", "deferred status alias must normalize")
    _require(set(SELF_LEARNING_FEEDBACK_STATUSES) == {"accepted", "rejected", "deferred"},
             "feedback statuses must stay stable")

    summary = summarize_self_learning_feedback([accepted, rejected, deferred])
    _require(summary["feedback_count"] == 3, "feedback summary must count receipts")
    _require(summary["by_status"]["accepted"] == 1, "summary must count accepted")
    _require(summary["by_status"]["rejected"] == 1, "summary must count rejected")
    _require(summary["by_status"]["deferred"] == 1, "summary must count deferred")
    _require(summary["by_category"]["worker_routing"] == 1,
             "summary must count category")
    _require(summary["by_category"]["swarm_orchestration"] == 1,
             "summary must count swarm category")
    _require(summary["by_risk"]["low"] == 1, "summary must count low risk")
    _require(summary["by_risk"]["medium"] == 1, "summary must count medium risk")
    _require(summary["by_risk"]["high"] == 1, "summary must count high risk")
    _require(summary["dry_run"] is True and summary["writes"] == [],
             "feedback summary must remain read-only")

    try:
        build_self_learning_feedback_receipt(candidate, status="maybe", reason="bad", confidence=0.1)
    except ValueError:
        pass
    else:
        raise AssertionError("invalid feedback status must be rejected")

    for bad_confidence in (-0.1, 1.1, "high"):
        try:
            build_self_learning_feedback_receipt(
                candidate,
                status="accepted",
                reason="bad confidence",
                confidence=bad_confidence,
            )
        except ValueError:
            pass
        else:
            raise AssertionError(f"invalid confidence must be rejected: {bad_confidence!r}")

    print("self-learning feedback receipt helper OK")


# ---------------------------------------------------------------------------
# 47. Self-learning next-step recommendations
# ---------------------------------------------------------------------------

def check_self_learning_next_step_recommendations_helper() -> None:
    """Feedback-adjusted next steps are deterministic, safe, and JSON-stable."""
    from link_modes.growth.link_growth_console import (
        SELF_LEARNING_NEXT_STEP_MAX_TOP,
        SELF_LEARNING_NEXT_STEP_VERSION,
        build_ruflo_upgrade_intake,
        build_self_learning_feedback_receipt,
        collect_ruflo_upgrade_plan,
        collect_self_learning_next_step_recommendations,
        self_learning_next_step_from_json,
        self_learning_next_step_to_json,
        validate_self_learning_next_step_recommendations,
    )

    findings = [
        {
            "title": "Profile-gated worker dispatch",
            "category": "worker_routing",
            "risk_level": "low",
            "summary": "Route worker dispatch through profile gates.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/orchestrator.ts",
            "source_kind": "code_brief",
            "evidence": ["profile gate"],
        },
        {
            "title": "Large swarm executor",
            "category": "swarm_orchestration",
            "risk": "high",
            "summary": "Broad swarm execution is too large for the next safe slice.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/v3/swarm.ts",
            "source_kind": "research",
        },
        {
            "title": "Dashboard latency metrics",
            "category": "performance",
            "risk": "medium",
            "summary": "Expose slow Growth queue stages in a dashboard card.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/metrics.ts",
            "source_kind": "research",
        },
        {
            "title": "Profile-gated worker dispatch",
            "category": "worker_routing",
            "risk_level": "low",
            "summary": "Duplicate should collapse before next-step ranking.",
            "source_path": "research/_extracted/ruflo-main/ruflo-main/ruflo/src/orchestrator.ts",
            "source_kind": "code_brief",
        },
    ]
    intake = build_ruflo_upgrade_intake(findings, source_label="ruflo")
    plan = collect_ruflo_upgrade_plan(intake, top=10, source_label="ruflo")
    candidates = {candidate["title"]: candidate for candidate in plan["ranked_candidates"]}

    accepted = build_self_learning_feedback_receipt(
        candidates["Profile-gated worker dispatch"],
        status="accepted",
        reason="This is a small safety improvement with clear tests.",
        confidence=0.95,
        tags=["routing", "safe"],
    )
    rejected = build_self_learning_feedback_receipt(
        candidates["Large swarm executor"],
        status="rejected",
        reason="Too much automation surface for this stage.",
        confidence=0.9,
        tags=["too_large"],
    )
    deferred = build_self_learning_feedback_receipt(
        candidates["Dashboard latency metrics"],
        status="deferred",
        reason="Needs a narrower dashboard-only design first.",
        confidence=0.6,
        tags=["observability"],
    )
    unmatched = build_self_learning_feedback_receipt(
        {
            "candidate_id": "ruflo-unmatched-feedback",
            "title": "Unmatched feedback",
            "category": "memory_retrieval",
            "risk_level": "low",
            "recommendation": "review",
            "source_path": "research/_extracted/ruflo-main/unknown.ts",
        },
        status="accepted",
        reason="Should be reported as unmatched, not written anywhere.",
        confidence=0.8,
    )

    data = collect_self_learning_next_step_recommendations(
        plan,
        [accepted, rejected, deferred, unmatched],
        top=5,
        source_label="ruflo",
    )
    same = collect_self_learning_next_step_recommendations(
        plan,
        [accepted, rejected, deferred, unmatched],
        top=5,
        source_label="ruflo",
    )

    _require(data["next_step_version"] == SELF_LEARNING_NEXT_STEP_VERSION,
             "next-step version mismatch")
    _require(data["recommendation_id"] == same["recommendation_id"],
             "next-step recommendation_id must be deterministic")
    _require(data["dry_run"] is True and data["write_allowed"] is False,
             "next-step recommendations must remain read-only")
    _require(data["automation_allowed"] is False,
             "next-step recommendations must not allow automation")
    _require(data["writes"] == [], "next-step recommendations must not write files")
    _require(data["duplicate_count"] == 1,
             "next-step recommendations must preserve candidate dedupe count")
    _require(data["feedback_count"] == 4,
             "next-step recommendations must count feedback receipts")
    _require(data["unmatched_feedback_count"] == 1,
             "unmatched feedback must be reported")
    _require(data["warnings"], "unmatched feedback must emit a warning")
    _require(data["feedback_summary"]["by_status"]["accepted"] == 2,
             "feedback summary must count accepted receipts")

    ranked = data["recommendations"]
    _require(ranked[0]["title"] == "Profile-gated worker dispatch",
             "accepted low-risk candidate should rank first")
    _require(ranked[0]["safe_recommendation"] == "accept",
             "accepted low-risk candidate should remain acceptable")
    _require(ranked[0]["feedback_adjustment"] > 0,
             "accepted feedback should boost adjusted score")

    by_title = {item["title"]: item for item in ranked}
    _require(by_title["Large swarm executor"]["safe_recommendation"] == "reject",
             "rejected high-risk candidate should be safely rejected")
    _require(by_title["Large swarm executor"]["feedback_adjustment"] < 0,
             "rejected feedback should lower adjusted score")
    _require(by_title["Dashboard latency metrics"]["safe_recommendation"] == "review",
             "deferred candidate should stay in review")
    _require("deferred" in by_title["Dashboard latency metrics"]["reason"].lower(),
             "deferred feedback reason must be visible")

    encoded = self_learning_next_step_to_json(data)
    _require(encoded == self_learning_next_step_to_json(data),
             "next-step JSON serialization must be stable")
    decoded = self_learning_next_step_from_json(encoded)
    _require(decoded == data, "next-step JSON round-trip must preserve data")
    validate_self_learning_next_step_recommendations(data)

    clamped = collect_self_learning_next_step_recommendations(
        plan,
        [accepted],
        top=99,
        source_label="ruflo",
    )
    _require(clamped["top_used"] == SELF_LEARNING_NEXT_STEP_MAX_TOP,
             "next-step top must clamp to max")
    _require(clamped["warnings"], "next-step top clamp must warn")

    raised = collect_self_learning_next_step_recommendations(plan, [], top=0)
    _require(raised["top_used"] == 1, "next-step top below 1 must raise to 1")
    _require(raised["warnings"], "empty feedback and low top must warn")

    try:
        collect_self_learning_next_step_recommendations({"bad": []}, [])
    except ValueError:
        pass
    else:
        raise AssertionError("invalid next-step candidate source must be rejected")

    bad_payload = dict(data)
    bad_payload["automation_allowed"] = True
    try:
        validate_self_learning_next_step_recommendations(bad_payload)
    except ValueError:
        pass
    else:
        raise AssertionError("next-step recommendations must reject automation_allowed=True")

    print("self-learning next-step recommendations helper OK")


# ---------------------------------------------------------------------------
# 47. Repo value scanner planning layer
# ---------------------------------------------------------------------------

def check_repo_value_scan_helper() -> None:
    """Repo inventory items rank into deterministic Link-value findings."""
    from link_modes.growth.link_growth_console import (
        REPO_VALUE_CATEGORIES,
        REPO_VALUE_SCAN_MAX_TOP,
        REPO_VALUE_SCAN_VERSION,
        collect_repo_value_scan,
        repo_value_scan_from_json,
        repo_value_scan_to_json,
        score_repo_value_inventory_item,
        validate_repo_value_finding,
        validate_repo_value_scan,
    )

    inventory = [
        {
            "path": "sota-scan-master/SKILL.md",
            "title": "Grounded repo benchmark workflow",
            "summary": "Skill inventories a repo, compares grounded capabilities, and ranks the next gaps.",
            "source_kind": "skill",
            "tags": ["repo scanning", "benchmark", "workflow"],
        },
        {
            "path": "sota-scan-master/lib/cluster.mjs",
            "title": "Deterministic peer clustering",
            "summary": "Dependency-free orchestration clustering groups peer approaches before ranking gaps.",
            "source_kind": "code",
            "signals": ["orchestration", "coordinator"],
        },
        {
            "path": "sota-scan-master/workflows/sota-scan-fanout.js",
            "title": "Fanout workflow routing",
            "summary": "Workflow dispatches comparator analysis while keeping synthesis separate.",
            "source_kind": "workflow",
            "keywords": ["task routing", "worker", "dispatch"],
        },
        {
            "path": "sota-scan-master/test/cluster.test.mjs",
            "title": "Cluster regression tests",
            "summary": "Tests verify deterministic clustering, maturity scoring, and gap partitioning.",
            "source_kind": "test",
            "tags": ["verification", "fixture"],
        },
        {
            "path": "sota-scan-master/.sota/last-scan.json",
            "title": "Scan receipt snapshot",
            "summary": "Stored scan output acts as progress evidence and audit trail.",
            "source_kind": "receipt",
            "tags": ["receipt", "audit"],
        },
        {
            "path": "sota-scan-master/SKILL.md",
            "title": "Grounded repo benchmark workflow duplicate",
            "summary": "Duplicate path/category should collapse.",
            "source_kind": "skill",
            "tags": ["repo scanning"],
        },
        {
            "path": "misc/unknown.txt",
            "title": "Unknown notes",
            "source_kind": "text",
        },
    ]

    scan = collect_repo_value_scan(inventory, top=10, source_label="sota-scan")
    same = collect_repo_value_scan(inventory, top=10, source_label="sota-scan")
    _require(scan["scan_version"] == REPO_VALUE_SCAN_VERSION,
             "repo value scan version mismatch")
    _require(scan["scan_id"] == same["scan_id"],
             "repo value scan_id must be deterministic")
    _require(scan["dry_run"] is True and scan["write_allowed"] is False,
             "repo value scan must remain read-only")
    _require(scan["automation_allowed"] is False,
             "repo value scan must not allow automation")
    _require(scan["writes"] == [], "repo value scan must not write runtime state")
    _require(set(scan["categories"]) == set(REPO_VALUE_CATEGORIES),
             "repo value scan must expose stable categories")
    _require(scan["item_count"] == len(inventory),
             "repo value scan must count inventory items")
    _require(scan["duplicate_count"] == 1,
             "repo value scan must collapse duplicate path/category findings")
    _require(scan["weak_finding_count"] >= 1,
             "repo value scan must count weak findings")
    _require(scan["warnings"], "duplicates/weak findings must emit warnings")

    findings = scan["findings"]
    _require(findings[0]["weak_finding"] is False,
             "strong findings must rank ahead of weak findings")
    categories = {finding["category"] for finding in findings}
    _require("repo_scanning" in categories,
             "repo scanning category must be inferred")
    _require("orchestration" in categories,
             "orchestration category must be inferred")
    _require("task_routing" in categories,
             "task routing category must be inferred")
    _require("tests_verification" in categories,
             "tests/verification category must be inferred")
    _require("receipts_auditability" in categories,
             "receipts/auditability category must be inferred")
    for finding in findings:
        validate_repo_value_finding(finding)
        _require(finding["finding_id"].startswith("repo-value-"),
                 "repo value finding_id must use stable prefix")
        _require(finding["value_reason"], "repo value finding must explain value")

    direct = score_repo_value_inventory_item(inventory[0], source_label="sota-scan")
    again = score_repo_value_inventory_item(inventory[0], source_label="sota-scan")
    _require(direct["finding_id"] == again["finding_id"],
             "repo value finding_id must be deterministic")

    encoded = repo_value_scan_to_json(scan)
    _require(encoded == repo_value_scan_to_json(scan),
             "repo value scan JSON serialization must be stable")
    decoded = repo_value_scan_from_json(encoded)
    _require(decoded == scan, "repo value scan JSON round-trip must preserve data")
    validate_repo_value_scan(scan)

    clamped = collect_repo_value_scan(inventory, top=99, source_label="sota-scan")
    _require(clamped["top_used"] == REPO_VALUE_SCAN_MAX_TOP,
             "repo value scan top must clamp to max")
    _require(clamped["warnings"], "repo value scan top clamp must warn")

    raised = collect_repo_value_scan(inventory, top=0, source_label="sota-scan")
    _require(raised["top_used"] == 1, "repo value scan top below 1 must raise to 1")
    _require(raised["warnings"], "repo value scan low top must warn")

    for bad_inventory in ({"path": "x"}, ["not-a-dict"], [{"title": "missing path"}]):
        try:
            collect_repo_value_scan(bad_inventory)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"invalid repo value input must be rejected: {bad_inventory!r}")

    bad_scan = dict(scan)
    bad_scan["write_allowed"] = True
    try:
        validate_repo_value_scan(bad_scan)
    except ValueError:
        pass
    else:
        raise AssertionError("repo value scan must reject write_allowed=True")

    print("repo value scan helper OK")


# ---------------------------------------------------------------------------
# 47. Link capability inventory
# ---------------------------------------------------------------------------

def check_link_capability_inventory_helper() -> None:
    """Link capabilities normalize into deterministic read-only inventory data."""
    from link_modes.growth.link_growth_console import (
        LINK_CAPABILITY_CATEGORIES,
        LINK_CAPABILITY_INVENTORY_VERSION,
        collect_link_capability_inventory,
        link_capability_inventory_from_json,
        link_capability_inventory_to_json,
        make_link_capability_id,
        normalize_link_capability_entry,
        validate_link_capability_entry,
        validate_link_capability_inventory,
    )

    inventory = collect_link_capability_inventory()
    same = collect_link_capability_inventory()
    _require(inventory["inventory_version"] == LINK_CAPABILITY_INVENTORY_VERSION,
             "Link capability inventory version mismatch")
    _require(inventory["inventory_id"] == same["inventory_id"],
             "Link capability inventory_id must be deterministic")
    _require(inventory["dry_run"] is True and inventory["write_allowed"] is False,
             "Link capability inventory must remain read-only")
    _require(inventory["automation_allowed"] is False,
             "Link capability inventory must not allow automation")
    _require(inventory["writes"] == [], "Link capability inventory must not write files")
    _require(set(inventory["categories"]) == set(LINK_CAPABILITY_CATEGORIES),
             "Link capability inventory must expose stable categories")
    _require(inventory["capability_count"] >= 12,
             "Link capability inventory must include current core capabilities")
    _require(inventory["capability_count"] == len(inventory["capabilities"]),
             "capability_count must match capabilities length")

    capabilities = inventory["capabilities"]
    by_name = {capability["name"]: capability for capability in capabilities}
    for expected in (
        "Growth archive inventory",
        "Repo value scan helper",
        "Self-learning next-step recommendations",
        "Receipt helpers",
        "Link healthcheck",
    ):
        _require(expected in by_name, f"missing expected Link capability: {expected}")
    categories = {capability["category"] for capability in capabilities}
    for expected_category in ("research_mining", "repo_value_scan", "self_learning", "receipts", "tests"):
        _require(expected_category in categories,
                 f"missing expected Link capability category: {expected_category}")
    for capability in capabilities:
        validate_link_capability_entry(capability)
        _require(capability["capability_id"].startswith("link-capability-"),
                 "capability_id must use stable prefix")
        _require(capability["confidence"] in {"low", "medium", "high"},
                 "confidence must be normalized")
        _require(isinstance(capability["tags"], list),
                 "tags must be a list")

    encoded = link_capability_inventory_to_json(inventory)
    _require(encoded == link_capability_inventory_to_json(inventory),
             "Link capability inventory JSON serialization must be stable")
    decoded = link_capability_inventory_from_json(encoded)
    _require(decoded == inventory,
             "Link capability inventory JSON round-trip must preserve data")
    validate_link_capability_inventory(inventory)

    custom = {
        "name": "Custom Safety Gate",
        "category": "safety",
        "description": "A synthetic capability for normalization tests.",
        "source": "tests/test_growth_pipeline.py",
        "confidence": "HIGH",
        "tags": ["Safety", "safety", "Policy Check"],
        "risk_level": "LOW",
        "maturity_level": "VERIFIED",
    }
    normalized = normalize_link_capability_entry(custom)
    _require(normalized["confidence"] == "high", "confidence must normalize casing")
    _require(normalized["risk_level"] == "low", "risk_level must normalize casing")
    _require(normalized["maturity_level"] == "verified", "maturity_level must normalize casing")
    _require(normalized["tags"] == ["safety", "policy_check"],
             "tags must normalize and dedupe")
    expected_id = make_link_capability_id(
        normalized["name"], normalized["category"], normalized["source"]
    )
    _require(normalized["capability_id"] == expected_id,
             "capability_id must be deterministic from name/category/source")

    duplicate_inventory = collect_link_capability_inventory([
        custom,
        dict(custom),
        {
            "name": "Custom Repo Scanner",
            "category": "repo_value_scan",
            "description": "A second synthetic capability.",
            "source": "tests/test_growth_pipeline.py:scanner",
            "confidence": "medium",
            "tags": "scanner",
            "risk_level": "low",
            "maturity_level": "partial",
        },
    ])
    _require(duplicate_inventory["input_count"] == 3,
             "custom inventory must report input_count")
    _require(duplicate_inventory["capability_count"] == 2,
             "duplicate capabilities must collapse by capability_id")
    _require(duplicate_inventory["duplicate_count"] == 1,
             "duplicate capabilities must be counted")
    _require(duplicate_inventory["writes"] == [],
             "custom inventory must remain read-only")

    for bad_entry in (
        {"name": "Missing category"},
        dict(custom, category="not-a-category"),
        dict(custom, confidence="certain"),
        dict(custom, tags={"bad": "tags"}),
    ):
        try:
            normalize_link_capability_entry(bad_entry)
        except (TypeError, ValueError):
            pass
        else:
            raise AssertionError(f"malformed capability entry must be rejected: {bad_entry!r}")

    bad_inventory = dict(inventory)
    bad_inventory["automation_allowed"] = True
    try:
        validate_link_capability_inventory(bad_inventory)
    except ValueError:
        pass
    else:
        raise AssertionError("Link capability inventory must reject automation_allowed=True")

    print("link capability inventory helper OK")


# ---------------------------------------------------------------------------
# 47. Capability gap preview
# ---------------------------------------------------------------------------

def check_capability_gap_preview_helper() -> None:
    """Link capability inventory and repo-value findings produce read-only gap previews."""
    from link_modes.growth.link_growth_console import (
        CAPABILITY_GAP_PREVIEW_VERSION,
        capability_gap_preview_from_json,
        capability_gap_preview_to_json,
        collect_capability_gap_preview,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        validate_capability_gap_preview,
    )

    link_inventory = collect_link_capability_inventory([
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Repo value scanner",
            "category": "repo_value_scan",
            "description": "Ranks repo files and concepts for Link relevance.",
            "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
            "confidence": "high",
            "tags": ["repo", "scan", "value"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
        {
            "name": "Command dashboard UX",
            "category": "workflow_ux",
            "description": "Shows Growth commands and local workflow state.",
            "source": "link_modes/growth/link_growth_console.py:collect_run_data",
            "confidence": "high",
            "tags": ["cli", "dashboard", "integration"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/SKILL.md",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "skill",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
        {
            "path": "sota/policy.md",
            "title": "Verified approval policy gate",
            "category": "safety_approval_gates",
            "summary": "Scanner requires policy gates before risky work.",
            "source_kind": "docs",
            "tags": ["safety", "policy", "gate"],
        },
        {
            "path": "sota/README.md",
            "title": "Discoverable command onboarding",
            "category": "cli_workflow_ux",
            "summary": "Documents CLI integration, quickstart examples, and dashboard discoverability.",
            "source_kind": "readme",
            "tags": ["cli", "integration", "docs"],
        },
        {
            "path": "sota/notes.txt",
            "title": "Weak scanner note",
            "category": "repo_scanning",
            "source_kind": "text",
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        if finding["title"] == "Verified approval policy gate":
            finding["required_maturity_level"] = "verified"

    preview = collect_capability_gap_preview(
        link_inventory,
        findings,
        metadata={"source": "unit-test"},
    )
    same = collect_capability_gap_preview(link_inventory, findings, metadata={"source": "unit-test"})

    _require(preview["preview_version"] == CAPABILITY_GAP_PREVIEW_VERSION,
             "capability gap preview version mismatch")
    _require(preview["preview_id"] == same["preview_id"],
             "capability gap preview_id must be deterministic")
    _require(preview["dry_run"] is True and preview["write_allowed"] is False,
             "capability gap preview must remain read-only")
    _require(preview["automation_allowed"] is False,
             "capability gap preview must not allow automation")
    _require(preview["writes"] == [], "capability gap preview must not write files")
    _require(preview["metadata"]["source"] == "unit-test",
             "capability gap preview must preserve metadata")

    counts = preview["counts"]
    _require(counts["direct_gap_count"] == 1,
             f"expected 1 direct gap, got {counts['direct_gap_count']}")
    _require(counts["maturity_gap_count"] == 1,
             f"expected 1 maturity gap, got {counts['maturity_gap_count']}")
    _require(counts["onboarding_gap_count"] == 1,
             f"expected 1 onboarding gap, got {counts['onboarding_gap_count']}")
    _require(counts["optional_cross_cluster_idea_count"] == 1,
             "weak related finding should become optional cross-cluster idea")
    _require(counts["matched_capability_count"] == 3,
             "three findings should match existing Link capabilities")
    _require(counts["unmatched_finding_count"] == 1,
             "one finding should remain unmatched")

    _require(preview["direct_gaps"][0]["target_category"] == "self_learning",
             "self-learning finding without Link capability must be direct gap")
    _require(preview["maturity_gaps"][0]["target_category"] == "safety",
             "safety finding with partial Link maturity must be maturity gap")
    _require(preview["onboarding_gaps"][0]["target_category"] == "workflow_ux",
             "CLI/docs finding should classify as onboarding gap")
    _require(preview["optional_cross_cluster_ideas"][0]["target_category"] == "repo_value_scan",
             "weak repo scanner finding should classify as optional idea")
    for section in ("direct_gaps", "maturity_gaps", "onboarding_gaps", "optional_cross_cluster_ideas"):
        _require(preview[section][0]["gap_id"].startswith("capability-gap-"),
                 f"{section} gap_id must use stable prefix")
        _require(preview[section][0]["recommended_action"],
                 f"{section} must include recommended_action")

    encoded = capability_gap_preview_to_json(preview)
    _require(encoded == capability_gap_preview_to_json(preview),
             "capability gap preview JSON serialization must be stable")
    decoded = capability_gap_preview_from_json(encoded)
    _require(decoded == preview, "capability gap preview JSON round-trip must preserve data")
    validate_capability_gap_preview(preview)

    try:
        collect_capability_gap_preview({"bad": "inventory"}, findings)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed Link inventory must be rejected")

    bad_finding = dict(findings[0])
    bad_finding["category"] = "not-a-repo-value-category"
    try:
        collect_capability_gap_preview(link_inventory, [bad_finding])
    except ValueError:
        pass
    else:
        raise AssertionError("malformed repo finding must be rejected")

    bad_preview = dict(preview)
    bad_preview["write_allowed"] = True
    try:
        validate_capability_gap_preview(bad_preview)
    except ValueError:
        pass
    else:
        raise AssertionError("capability gap preview must reject write_allowed=True")

    print("capability gap preview helper OK")


# ---------------------------------------------------------------------------
# 48. Growth planning preview aggregate
# ---------------------------------------------------------------------------

def check_growth_planning_preview_helper() -> None:
    """Aggregate planning preview combines inventory, repo scan, and gap summaries."""
    from link_modes.growth.link_growth_console import (
        GROWTH_PLANNING_PREVIEW_VERSION,
        collect_growth_planning_preview,
        growth_planning_preview_from_json,
        growth_planning_preview_to_json,
        validate_growth_planning_preview,
    )

    repo_items = [
        {
            "path": "sota/SKILL.md",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "skill",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
        {
            "path": "sota/policy.md",
            "title": "Verified approval policy gate",
            "category": "safety_approval_gates",
            "summary": "Scanner requires policy gates before risky work.",
            "source_kind": "docs",
            "tags": ["safety", "policy", "gate"],
        },
        {
            "path": "sota/README.md",
            "title": "Discoverable command onboarding",
            "category": "cli_workflow_ux",
            "summary": "Documents CLI integration, quickstart examples, and dashboard discoverability.",
            "source_kind": "readme",
            "tags": ["cli", "integration", "docs"],
        },
        {
            "path": "sota/notes.txt",
            "title": "Weak scanner note",
            "category": "repo_scanning",
            "source_kind": "text",
        },
    ]
    link_capabilities = [
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Repo value scanner",
            "category": "repo_value_scan",
            "description": "Ranks repo files and concepts for Link relevance.",
            "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
            "confidence": "high",
            "tags": ["repo", "scan", "value"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
        {
            "name": "Command dashboard UX",
            "category": "workflow_ux",
            "description": "Shows Growth commands and local workflow state.",
            "source": "link_modes/growth/link_growth_console.py:collect_run_data",
            "confidence": "high",
            "tags": ["cli", "dashboard", "integration"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ]

    preview = collect_growth_planning_preview(
        repo_items,
        link_capabilities=link_capabilities,
        top=10,
        source_label="sota-scan",
        metadata={"suite": "growth"},
    )
    same = collect_growth_planning_preview(
        repo_items,
        link_capabilities=link_capabilities,
        top=10,
        source_label="sota-scan",
        metadata={"suite": "growth"},
    )

    _require(preview["planning_version"] == GROWTH_PLANNING_PREVIEW_VERSION,
             "Growth planning preview version mismatch")
    _require(preview["preview_id"] == same["preview_id"],
             "Growth planning preview_id must be deterministic")
    _require(preview["dry_run"] is True and preview["write_allowed"] is False,
             "Growth planning preview must remain read-only")
    _require(preview["automation_allowed"] is False,
             "Growth planning preview must not allow automation")
    _require(preview["writes"] == [], "Growth planning preview must not write files")
    _require(preview["metadata"]["suite"] == "growth",
             "Growth planning preview must preserve metadata")
    _require(preview["source_label"] == "sota-scan",
             "Growth planning preview must preserve source_label")

    cap_summary = preview["capability_inventory_summary"]
    repo_summary = preview["repo_value_scan_summary"]
    gap_summary = preview["capability_gap_summary"]
    _require(cap_summary["capability_count"] == 3,
             "capability summary must count capabilities")
    _require(cap_summary["by_category"]["safety"] == 1,
             "capability summary must count categories")
    _require(repo_summary["item_count"] == 4,
             "repo value summary must count input items")
    _require(repo_summary["weak_finding_count"] == 1,
             "repo value summary must count weak findings")
    counts = gap_summary["counts"]
    _require(counts["direct_gap_count"] == 1,
             "gap summary must count direct gaps")
    _require(counts["maturity_gap_count"] == 1,
             "gap summary must count maturity gaps")
    _require(counts["onboarding_gap_count"] == 1,
             "gap summary must count onboarding gaps")
    _require(counts["optional_cross_cluster_idea_count"] == 1,
             "gap summary must count optional cross-cluster ideas")

    steps = preview["top_recommended_next_steps"]
    _require(len(steps) == 4, "planning preview must include top recommended next steps")
    _require(steps[0]["section"] == "direct_gaps",
             "direct gaps must be highest-priority next steps")
    _require(steps[-1]["section"] == "optional_cross_cluster_ideas",
             "optional ideas must rank after direct/maturity/onboarding gaps")
    for step in steps:
        _require(step["step_id"].startswith("growth-next-step-"),
                 "next step id must use stable prefix")
        _require(step["recommended_action"],
                 "next step must include recommended_action")

    encoded = growth_planning_preview_to_json(preview)
    _require(encoded == growth_planning_preview_to_json(preview),
             "Growth planning preview JSON serialization must be stable")
    decoded = growth_planning_preview_from_json(encoded)
    _require(decoded == preview, "Growth planning preview JSON round-trip must preserve data")
    validate_growth_planning_preview(preview)

    try:
        collect_growth_planning_preview({"bad": "repo-items"})  # type: ignore[arg-type]
    except TypeError:
        pass
    else:
        raise AssertionError("malformed repo inventory input must be rejected")

    bad_preview = dict(preview)
    bad_preview["automation_allowed"] = True
    try:
        validate_growth_planning_preview(bad_preview)
    except ValueError:
        pass
    else:
        raise AssertionError("Growth planning preview must reject automation_allowed=True")

    print("growth planning preview helper OK")


# ---------------------------------------------------------------------------
# 49. Link capability graph
# ---------------------------------------------------------------------------

def check_capability_graph_helper() -> None:
    """Capability inventory and gap preview normalize into a read-only graph."""
    from link_modes.growth.link_growth_console import (
        CAPABILITY_GRAPH_VERSION,
        collect_capability_gap_preview,
        collect_capability_graph,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        parse_capability_graph_json,
        stable_capability_graph_json,
        validate_capability_graph,
    )

    capabilities = [
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Repo value scanner",
            "category": "repo_value_scan",
            "description": "Ranks repo files and concepts for Link relevance.",
            "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
            "confidence": "high",
            "tags": ["repo", "scan", "value"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ]
    inventory = collect_link_capability_inventory(capabilities)
    _require(inventory["capability_count"] == 2,
             "duplicate capabilities must normalize before graph construction")

    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/policy.md",
            "title": "Verified approval policy gate",
            "category": "safety_approval_gates",
            "summary": "Scanner requires policy gates before risky work.",
            "source_kind": "docs",
            "tags": ["safety", "policy", "gate"],
        },
        {
            "path": "sota/scanner.py",
            "title": "Repo scanner ranking",
            "category": "repo_scanning",
            "summary": "Ranks files and identifies project-relevant modules.",
            "source_kind": "code",
            "tags": ["repo", "scan", "value"],
        },
    ], source_label="sota-scan")
    gap_preview = collect_capability_gap_preview(inventory, repo_scan)
    graph = collect_capability_graph(
        inventory,
        gap_preview=gap_preview,
        relationships=[{
            "source_id": inventory["capabilities"][0]["capability_id"],
            "target_id": inventory["capabilities"][1]["capability_id"],
            "relationship": "feeds_into",
            "confidence": 0.8,
            "reason": "Safety review feeds repo-value mining decisions.",
        }],
        metadata={"suite": "growth"},
    )
    same = collect_capability_graph(
        inventory,
        gap_preview=gap_preview,
        relationships=[{
            "source_id": inventory["capabilities"][0]["capability_id"],
            "target_id": inventory["capabilities"][1]["capability_id"],
            "relationship": "feeds_into",
            "confidence": 0.8,
            "reason": "Safety review feeds repo-value mining decisions.",
        }],
        metadata={"suite": "growth"},
    )

    _require(graph["graph_version"] == CAPABILITY_GRAPH_VERSION,
             "capability graph version mismatch")
    _require(graph["graph_id"] == same["graph_id"],
             "capability graph_id must be deterministic")
    _require(graph["dry_run"] is True and graph["write_allowed"] is False,
             "capability graph must remain read-only")
    _require(graph["automation_allowed"] is False,
             "capability graph must not allow automation")
    _require(graph["writes"] == [], "capability graph must not write files")
    _require(graph["metadata"]["suite"] == "growth",
             "capability graph must preserve metadata")
    _require(graph["node_count"] == 2, "graph must create nodes from capability inventory")
    _require(graph["node_count"] == len(graph["nodes"]),
             "node_count must match nodes length")
    _require(graph["edge_count"] == len(graph["edges"]),
             "edge_count must match edges length")

    node_ids = {node["capability_id"] for node in graph["nodes"]}
    _require(node_ids == {item["capability_id"] for item in inventory["capabilities"]},
             "graph nodes must preserve capability ids")
    by_name = {node["name"]: node for node in graph["nodes"]}
    _require(by_name["Safety policy gate"]["maturity_score"] == 0.5,
             "partial maturity must map to score 0.5")
    _require(by_name["Repo value scanner"]["maturity_score"] == 1.0,
             "verified maturity must map to score 1.0")
    for node in graph["nodes"]:
        _require(node["evidence_sources"], "node must include evidence_sources")
        _require(node["risk_label"] in {"low", "medium", "high"},
                 "node risk label must be normalized")
        _require(node["status"] in {"planned", "in_progress", "available", "verified"},
                 "node status must be normalized")

    edge_ids = [edge["edge_id"] for edge in graph["edges"]]
    _require(edge_ids == sorted(edge_ids), "edges must sort deterministically by id")
    _require(all(edge_id.startswith("capability-edge-") for edge_id in edge_ids),
             "edge ids must use stable prefix")
    relationships = {edge["relationship"] for edge in graph["edges"]}
    _require("feeds_into" in relationships,
             "manual graph relationships must be preserved")
    _require("derived_from_repo_finding" in relationships,
             "gap preview matches must create derived_from_repo_finding edges")
    for edge in graph["edges"]:
        _require(edge["source_id"] in node_ids and edge["target_id"] in node_ids,
                 "edge endpoints must reference graph nodes")
        _require(0.0 <= edge["confidence"] <= 1.0,
                 "edge confidence must be bounded")
        _require(edge["reason"], "edge must include reason")

    encoded = stable_capability_graph_json(graph)
    _require(encoded == stable_capability_graph_json(graph),
             "capability graph JSON serialization must be stable")
    decoded = parse_capability_graph_json(encoded)
    _require(decoded == graph, "capability graph JSON round-trip must preserve data")
    validate_capability_graph(graph)

    bad_source = dict(graph)
    bad_source["edges"] = [dict(graph["edges"][0], source_id="missing-node")]
    try:
        validate_capability_graph(bad_source)
    except ValueError:
        pass
    else:
        raise AssertionError("capability graph must reject invalid edge source_id")

    bad_relationship = dict(graph)
    bad_relationship["edges"] = [dict(graph["edges"][0], relationship="executes")]
    try:
        validate_capability_graph(bad_relationship)
    except ValueError:
        pass
    else:
        raise AssertionError("capability graph must reject invalid relationship")

    bad_confidence = dict(graph)
    bad_confidence["edges"] = [dict(graph["edges"][0], confidence=1.5)]
    try:
        validate_capability_graph(bad_confidence)
    except ValueError:
        pass
    else:
        raise AssertionError("capability graph must reject confidence outside 0..1")

    bad_writes = dict(graph)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_capability_graph(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("capability graph must reject writes")

    print("capability graph helper OK")


# ---------------------------------------------------------------------------
# 50. Capability evidence graph
# ---------------------------------------------------------------------------

def check_capability_evidence_graph_helper() -> None:
    """Capability graph nodes can carry normalized evidence and confidence."""
    from link_modes.growth.link_growth_console import (
        CAPABILITY_EVIDENCE_GRAPH_VERSION,
        collect_capability_evidence_graph,
        collect_capability_graph,
        collect_link_capability_inventory,
        parse_capability_evidence_graph_json,
        stable_capability_evidence_graph_json,
        validate_capability_evidence_graph,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Repo value scanner",
            "category": "repo_value_scan",
            "description": "Ranks repo files and concepts for Link relevance.",
            "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
            "confidence": "high",
            "tags": ["repo", "scan", "value"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ])
    graph = collect_capability_graph(inventory)
    safety_id = next(item["capability_id"] for item in inventory["capabilities"] if item["name"] == "Safety policy gate")
    scanner_id = next(item["capability_id"] for item in inventory["capabilities"] if item["name"] == "Repo value scanner")
    evidence_refs = [
        {
            "capability_id": safety_id,
            "commit_refs": ["abcdef1", "abcdef1"],
            "file_refs": ["link_capability_gate.py", "link_capability_gate.py"],
            "test_refs": ["tests/test_growth_pipeline.py", "tests/test_growth_pipeline.py"],
            "healthcheck_refs": ["link_healthcheck.py"],
            "proposal_refs": ["add-safety-policy-gate"],
            "source_repo_refs": ["research/sota-scan-master.zip"],
        },
        {
            "capability_id": scanner_id,
            "file_refs": ["link_modes/growth/link_growth_console.py"],
            "test_refs": ["tests/test_growth_pipeline.py"],
        },
    ]
    evidence_graph = collect_capability_evidence_graph(
        graph,
        evidence_refs=evidence_refs,
        metadata={"suite": "growth"},
    )
    same = collect_capability_evidence_graph(
        graph,
        evidence_refs=evidence_refs,
        metadata={"suite": "growth"},
    )

    _require(evidence_graph["evidence_graph_version"] == CAPABILITY_EVIDENCE_GRAPH_VERSION,
             "capability evidence graph version mismatch")
    _require(evidence_graph["evidence_graph_id"] == same["evidence_graph_id"],
             "capability evidence graph id must be deterministic")
    _require(evidence_graph["source_graph_id"] == graph["graph_id"],
             "capability evidence graph must reference source graph id")
    _require(evidence_graph["dry_run"] is True and evidence_graph["write_allowed"] is False,
             "capability evidence graph must remain read-only")
    _require(evidence_graph["automation_allowed"] is False,
             "capability evidence graph must not allow automation")
    _require(evidence_graph["writes"] == [], "capability evidence graph must not write files")
    _require(evidence_graph["metadata"]["suite"] == "growth",
             "capability evidence graph must preserve metadata")
    _require(evidence_graph["node_count"] == 2,
             "capability evidence graph must include one evidence node per graph node")

    by_name = {node["capability_name"]: node for node in evidence_graph["evidence_nodes"]}
    safety = by_name["Safety policy gate"]
    scanner = by_name["Repo value scanner"]
    _require(safety["evidence_id"].startswith("capability-evidence-"),
             "capability evidence node id must use stable prefix")
    _require(safety["commit_refs"] == ["abcdef1"],
             "duplicate commit refs must normalize")
    _require(safety["file_refs"] == ["link_capability_gate.py"],
             "duplicate file refs must normalize with graph evidence source")
    _require(safety["test_refs"] == ["tests/test_growth_pipeline.py"],
             "duplicate test refs must normalize")
    _require(safety["healthcheck_refs"] == ["link_healthcheck.py"],
             "healthcheck refs must be preserved")
    _require(safety["proposal_refs"] == ["add-safety-policy-gate"],
             "proposal refs must be preserved")
    _require(safety["source_repo_refs"] == ["research/sota-scan-master.zip"],
             "source repo refs must be preserved")
    _require(safety["confidence_score"] == 1.0,
             f"expected confidence score 1.0, got {safety['confidence_score']}")
    _require(scanner["confidence_score"] == 0.7,
             f"expected scanner confidence score 0.7, got {scanner['confidence_score']}")

    encoded = stable_capability_evidence_graph_json(evidence_graph)
    _require(encoded == stable_capability_evidence_graph_json(evidence_graph),
             "capability evidence graph JSON serialization must be stable")
    decoded = parse_capability_evidence_graph_json(encoded)
    _require(decoded == evidence_graph,
             "capability evidence graph JSON round-trip must preserve data")
    validate_capability_evidence_graph(evidence_graph)

    bad_confidence = dict(evidence_graph)
    bad_confidence["evidence_nodes"] = [dict(evidence_graph["evidence_nodes"][0], confidence_score=1.5)]
    bad_confidence["node_count"] = 1
    try:
        validate_capability_evidence_graph(bad_confidence)
    except ValueError:
        pass
    else:
        raise AssertionError("capability evidence graph must reject confidence outside 0..1")

    try:
        collect_capability_evidence_graph(graph, evidence_refs=[{
            "capability_id": safety_id,
            "commit_refs": ["not-a-commit"],
        }])
    except ValueError:
        pass
    else:
        raise AssertionError("capability evidence graph must reject invalid commit refs")

    try:
        collect_capability_evidence_graph(graph, evidence_refs=[{
            "capability_id": safety_id,
            "file_refs": ["../outside.py"],
        }])
    except ValueError:
        pass
    else:
        raise AssertionError("capability evidence graph must reject unsafe file refs")

    bad_node = dict(evidence_graph)
    bad_node["evidence_nodes"] = [dict(evidence_graph["evidence_nodes"][0], file_refs=["z.py", "a.py"])]
    bad_node["node_count"] = 1
    try:
        validate_capability_evidence_graph(bad_node)
    except ValueError:
        pass
    else:
        raise AssertionError("capability evidence graph must reject unsorted refs")

    bad_writes = dict(evidence_graph)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_capability_evidence_graph(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("capability evidence graph must reject writes")

    print("capability evidence graph helper OK")


# ---------------------------------------------------------------------------
# 51. Capability discovery
# ---------------------------------------------------------------------------

def check_capability_discovery_helper() -> None:
    """Capability discovery maps capabilities to implementation locations read-only."""
    from link_modes.growth.link_growth_console import (
        CAPABILITY_DISCOVERY_VERSION,
        collect_capability_discovery,
        collect_capability_evidence_graph,
        collect_capability_graph,
        collect_link_capability_inventory,
        parse_capability_discovery_json,
        stable_capability_discovery_json,
        validate_capability_discovery,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Capability graph helper",
            "category": "workflow_ux",
            "description": "Builds graph nodes and edges for capabilities.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["capability", "graph"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
        {
            "name": "Capability graph helper",
            "category": "workflow_ux",
            "description": "Builds graph nodes and edges for capabilities.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["capability", "graph"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
        {
            "name": "Receipt helpers",
            "category": "receipts",
            "description": "Builds stable receipt helper objects.",
            "source": "link_core/receipts/__init__.py",
            "confidence": "high",
            "tags": ["receipt", "evidence"],
            "risk_level": "low",
            "maturity_level": "available",
        },
    ])
    _require(inventory["capability_count"] == 2,
             "duplicate capabilities must normalize before discovery")
    graph = collect_capability_graph(inventory)
    graph_id = next(item["capability_id"] for item in inventory["capabilities"] if item["name"] == "Capability graph helper")
    receipt_id = next(item["capability_id"] for item in inventory["capabilities"] if item["name"] == "Receipt helpers")
    evidence = collect_capability_evidence_graph(graph, evidence_refs=[
        {
            "capability_id": graph_id,
            "file_refs": ["link_modes/growth/link_growth_console.py", "link_modes/growth/link_growth_console.py"],
            "test_refs": ["tests/test_growth_pipeline.py", "tests/test_growth_pipeline.py"],
            "healthcheck_refs": ["link_healthcheck.py"],
            "commit_refs": ["abcdef1"],
        },
        {
            "capability_id": receipt_id,
            "file_refs": ["link_core/receipts/__init__.py"],
            "test_refs": ["tests/test_growth_pipeline.py"],
        },
    ])
    discovery = collect_capability_discovery(
        inventory,
        capability_graph=graph,
        evidence_graph=evidence,
        metadata={"suite": "growth"},
    )
    same = collect_capability_discovery(
        inventory,
        capability_graph=graph,
        evidence_graph=evidence,
        metadata={"suite": "growth"},
    )

    _require(discovery["discovery_version"] == CAPABILITY_DISCOVERY_VERSION,
             "capability discovery version mismatch")
    _require(discovery["discovery_id"] == same["discovery_id"],
             "capability discovery id must be deterministic")
    _require(discovery["source_inventory_id"] == inventory["inventory_id"],
             "capability discovery must reference inventory id")
    _require(discovery["source_graph_id"] == graph["graph_id"],
             "capability discovery must reference graph id")
    _require(discovery["source_evidence_graph_id"] == evidence["evidence_graph_id"],
             "capability discovery must reference evidence graph id")
    _require(discovery["dry_run"] is True and discovery["write_allowed"] is False,
             "capability discovery must remain read-only")
    _require(discovery["automation_allowed"] is False,
             "capability discovery must not allow automation")
    _require(discovery["writes"] == [], "capability discovery must not write files")
    _require(discovery["metadata"]["suite"] == "growth",
             "capability discovery must preserve metadata")
    _require(discovery["capability_count"] == 2,
             "capability discovery must include one entry per capability")

    by_name = {entry["capability_name"]: entry for entry in discovery["discoveries"]}
    graph_entry = by_name["Capability graph helper"]
    receipt_entry = by_name["Receipt helpers"]
    _require(graph_entry["discovery_id"].startswith("capability-discovery-"),
             "discovery entry id must use stable prefix")
    _require(graph_entry["capability_id"] == graph_id,
             "discovery entry must preserve capability_id")
    _require(graph_entry["file_paths"] == ["link_modes/growth/link_growth_console.py"],
             "duplicate file paths must normalize")
    _require(graph_entry["module_paths"] == ["link_modes.growth.link_growth_console"],
             "Python file paths must map to module paths")
    _require(graph_entry["test_paths"] == ["tests/test_growth_pipeline.py"],
             "duplicate test paths must normalize")
    _require(graph_entry["evidence_refs"] == ["abcdef1", "link_healthcheck.py"],
             "evidence refs must normalize and sort")
    _require(graph_entry["confidence_score"] == 1.0,
             f"expected discovery confidence 1.0, got {graph_entry['confidence_score']}")
    _require(receipt_entry["module_paths"] == ["link_core.receipts"],
             "__init__.py file path must map to package module")
    _require(receipt_entry["confidence_score"] == 0.7919,
             f"expected receipt discovery confidence 0.7919, got {receipt_entry['confidence_score']}")

    encoded = stable_capability_discovery_json(discovery)
    _require(encoded == stable_capability_discovery_json(discovery),
             "capability discovery JSON serialization must be stable")
    decoded = parse_capability_discovery_json(encoded)
    _require(decoded == discovery, "capability discovery JSON round-trip must preserve data")
    validate_capability_discovery(discovery)

    bad_confidence = dict(discovery)
    bad_confidence["discoveries"] = [dict(discovery["discoveries"][0], confidence_score=1.5)]
    bad_confidence["capability_count"] = 1
    try:
        validate_capability_discovery(bad_confidence)
    except ValueError:
        pass
    else:
        raise AssertionError("capability discovery must reject confidence outside 0..1")

    bad_missing_id = dict(discovery)
    bad_entry = dict(discovery["discoveries"][0])
    bad_entry.pop("capability_id")
    bad_missing_id["discoveries"] = [bad_entry]
    bad_missing_id["capability_count"] = 1
    try:
        validate_capability_discovery(bad_missing_id)
    except ValueError:
        pass
    else:
        raise AssertionError("capability discovery must reject missing capability_id")

    bad_path = dict(discovery)
    bad_path["discoveries"] = [dict(discovery["discoveries"][0], file_paths=["../outside.py"])]
    bad_path["capability_count"] = 1
    try:
        validate_capability_discovery(bad_path)
    except ValueError:
        pass
    else:
        raise AssertionError("capability discovery must reject unsafe paths")

    bad_unsorted = dict(discovery)
    bad_unsorted["discoveries"] = [dict(discovery["discoveries"][0], test_paths=["z.py", "a.py"])]
    bad_unsorted["capability_count"] = 1
    try:
        validate_capability_discovery(bad_unsorted)
    except ValueError:
        pass
    else:
        raise AssertionError("capability discovery must reject unsorted duplicate-prone paths")

    bad_writes = dict(discovery)
    bad_writes["writes"] = [".link/state.json"]
    try:
        validate_capability_discovery(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("capability discovery must reject writes")

    print("capability discovery helper OK")


# ---------------------------------------------------------------------------
# 52. Capability intelligence payload
# ---------------------------------------------------------------------------

def check_capability_intelligence_payload_helper() -> None:
    """Aggregate capability intelligence payload stays deterministic and read-only."""
    from link_modes.growth.link_growth_console import (
        CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION,
        collect_capability_intelligence_payload,
        parse_capability_intelligence_payload_json,
        stable_capability_intelligence_payload_json,
        validate_capability_intelligence_payload,
    )

    repo_items = [
        {
            "path": "sota/policy.md",
            "title": "Verified approval policy gate",
            "category": "safety_approval_gates",
            "summary": "Scanner requires policy gates before risky work.",
            "source_kind": "docs",
            "tags": ["safety", "policy", "gate"],
        },
        {
            "path": "sota/README.md",
            "title": "Discoverable command onboarding",
            "category": "cli_workflow_ux",
            "summary": "Documents CLI integration, quickstart examples, and dashboard discoverability.",
            "source_kind": "readme",
            "tags": ["cli", "integration", "docs"],
        },
    ]
    capabilities = [
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Command dashboard UX",
            "category": "workflow_ux",
            "description": "Shows Growth commands and local workflow state.",
            "source": "link_modes/growth/link_growth_console.py:collect_run_data",
            "confidence": "high",
            "tags": ["cli", "dashboard", "integration"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ]
    payload = collect_capability_intelligence_payload(
        repo_items,
        link_capabilities=capabilities,
        top=5,
        source_label="sota-scan",
        metadata={"suite": "growth"},
    )
    same = collect_capability_intelligence_payload(
        repo_items,
        link_capabilities=capabilities,
        top=5,
        source_label="sota-scan",
        metadata={"suite": "growth"},
    )

    _require(payload["payload_version"] == CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION,
             "capability intelligence payload version mismatch")
    _require(payload["payload_id"] == same["payload_id"],
             "capability intelligence payload_id must be deterministic")
    _require(payload["dry_run"] is True and payload["write_allowed"] is False,
             "capability intelligence payload must remain read-only")
    _require(payload["automation_allowed"] is False,
             "capability intelligence payload must not allow automation")
    _require(payload["writes"] == [], "capability intelligence payload must not write files")
    _require(payload["metadata"]["suite"] == "growth",
             "capability intelligence payload must preserve metadata")

    for field in (
        "inventory_summary",
        "gap_summary",
        "planning_preview_summary",
        "capability_graph_summary",
        "evidence_graph_summary",
        "discovery_summary",
    ):
        _require(isinstance(payload[field], dict), f"{field} must be present")

    _require(payload["inventory_summary"]["capability_count"] == 2,
             "inventory summary must count capabilities")
    _require(payload["gap_summary"]["counts"]["repo_finding_count"] == 2,
             "gap summary must include repo finding count")
    _require(payload["planning_preview_summary"]["next_step_count"] == len(payload["top_recommended_next_steps"]),
             "planning summary must count top next steps")
    _require(payload["capability_graph_summary"]["node_count"] == 2,
             "graph summary must count nodes")
    _require(payload["evidence_graph_summary"]["node_count"] == 2,
             "evidence graph summary must count nodes")
    _require(payload["discovery_summary"]["capability_count"] == 2,
             "discovery summary must count capabilities")
    _require(0.0 <= payload["evidence_graph_summary"]["average_confidence_score"] <= 1.0,
             "evidence average confidence must be bounded")
    _require(0.0 <= payload["discovery_summary"]["average_confidence_score"] <= 1.0,
             "discovery average confidence must be bounded")
    _require(payload["top_recommended_next_steps"],
             "capability intelligence payload must include recommended next steps")

    encoded = stable_capability_intelligence_payload_json(payload)
    _require(encoded == stable_capability_intelligence_payload_json(payload),
             "capability intelligence payload JSON serialization must be stable")
    decoded = parse_capability_intelligence_payload_json(encoded)
    _require(decoded == payload,
             "capability intelligence payload JSON round-trip must preserve data")
    validate_capability_intelligence_payload(payload)

    bad_missing_id = dict(payload)
    bad_missing_id.pop("payload_id")
    try:
        validate_capability_intelligence_payload(bad_missing_id)
    except ValueError:
        pass
    else:
        raise AssertionError("capability intelligence payload must reject missing payload_id")

    bad_writes = dict(payload)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_capability_intelligence_payload(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("capability intelligence payload must reject unsafe writes")

    bad_summary = dict(payload)
    bad_summary["inventory_summary"] = {"inventory_id": "missing-counts"}
    try:
        validate_capability_intelligence_payload(bad_summary)
    except ValueError:
        pass
    else:
        raise AssertionError("capability intelligence payload must reject malformed summaries")

    bad_steps = dict(payload)
    bad_steps["top_recommended_next_steps"] = [{"step_id": "missing-fields"}]
    try:
        validate_capability_intelligence_payload(bad_steps)
    except ValueError:
        pass
    else:
        raise AssertionError("capability intelligence payload must reject malformed next steps")

    print("capability intelligence payload helper OK")


# ---------------------------------------------------------------------------
# 53. Upgrade execution planner
# ---------------------------------------------------------------------------

def check_upgrade_execution_plan_helper() -> None:
    """Capability gaps convert into deterministic read-only upgrade execution plans."""
    from link_modes.growth.link_growth_console import (
        UPGRADE_EXECUTION_PLAN_VERSION,
        collect_capability_gap_preview,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        parse_upgrade_execution_plan_json,
        stable_upgrade_execution_plan_json,
        validate_upgrade_execution_plan,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Safety policy gate",
            "category": "safety",
            "description": "Existing safety policy gate is present but still maturing.",
            "source": "link_capability_gate.py",
            "confidence": "high",
            "tags": ["safety", "policy", "gate"],
            "risk_level": "low",
            "maturity_level": "partial",
        },
        {
            "name": "Command dashboard UX",
            "category": "workflow_ux",
            "description": "Shows Growth commands and local workflow state.",
            "source": "link_modes/growth/link_growth_console.py:collect_run_data",
            "confidence": "high",
            "tags": ["cli", "dashboard", "integration"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
        {
            "name": "Repo value scanner",
            "category": "repo_value_scan",
            "description": "Ranks repo files and concepts for Link relevance.",
            "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
            "confidence": "high",
            "tags": ["repo", "scan", "value"],
            "risk_level": "low",
            "maturity_level": "verified",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/memory.py",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "code",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
        {
            "path": "sota/policy.md",
            "title": "Verified approval policy gate",
            "category": "safety_approval_gates",
            "summary": "Scanner requires policy gates before risky work.",
            "source_kind": "docs",
            "tags": ["safety", "policy", "gate"],
        },
        {
            "path": "sota/README.md",
            "title": "Discoverable command onboarding",
            "category": "cli_workflow_ux",
            "summary": "Documents CLI integration, quickstart examples, and dashboard discoverability.",
            "source_kind": "readme",
            "tags": ["cli", "integration", "docs"],
        },
        {
            "path": "sota/notes.txt",
            "title": "Weak scanner note",
            "category": "repo_scanning",
            "source_kind": "text",
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        if finding["title"] == "Verified approval policy gate":
            finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    plan = collect_upgrade_execution_plan(
        gap_preview,
        inventory,
        findings,
        metadata={"suite": "growth"},
    )
    same = collect_upgrade_execution_plan(
        gap_preview,
        inventory,
        findings,
        metadata={"suite": "growth"},
    )

    _require(plan["plan_version"] == UPGRADE_EXECUTION_PLAN_VERSION,
             "upgrade execution plan version mismatch")
    _require(plan["plan_id"] == same["plan_id"],
             "upgrade execution plan_id must be deterministic")
    _require(plan["source_gap_preview_id"] == gap_preview["preview_id"],
             "upgrade execution plan must reference gap preview id")
    _require(plan["source_inventory_id"] == inventory["inventory_id"],
             "upgrade execution plan must reference inventory id")
    _require(plan["dry_run"] is True and plan["write_allowed"] is False,
             "upgrade execution plan must remain read-only")
    _require(plan["automation_allowed"] is False,
             "upgrade execution plan must not allow automation")
    _require(plan["writes"] == [], "upgrade execution plan must not write files")
    _require(plan["metadata"]["suite"] == "growth",
             "upgrade execution plan must preserve metadata")
    _require(plan["upgrade_plan_count"] == 4,
             "upgrade execution plan must include all gap sections")

    ranks = [entry["rank"] for entry in plan["upgrade_plans"]]
    _require(ranks == sorted(ranks), "upgrade plans must rank deterministically")
    by_title = {entry["title"]: entry for entry in plan["upgrade_plans"]}
    direct = by_title["Self-learning feedback loop"]
    maturity = by_title["Verified approval policy gate"]
    onboarding = by_title["Discoverable command onboarding"]
    optional = by_title["Weak scanner note"]
    _require(direct["gap_type"] == "direct_gap", "self-learning finding must be direct gap")
    _require(direct["complexity"] == "large", "self-learning direct gap should classify as large")
    _require(direct["risk"] == "high", "self-learning direct gap should classify as high risk")
    _require(maturity["gap_type"] == "maturity_gap", "safety finding must be maturity gap")
    _require(maturity["complexity"] == "medium", "safety maturity gap should classify as medium")
    _require(maturity["risk"] == "medium", "safety maturity gap should classify as medium risk")
    _require(onboarding["gap_type"] == "onboarding_gap", "README finding must be onboarding gap")
    _require(onboarding["complexity"] == "small", "onboarding gap should classify as small")
    _require(onboarding["risk"] == "low", "workflow onboarding gap should classify as low risk")
    _require(optional["gap_type"] == "optional_cross_cluster_idea", "weak scanner note should be optional idea")
    _require(optional["complexity"] == "medium", "optional idea should classify as medium")
    _require(optional["risk"] == "medium", "optional idea should classify as medium risk")

    for entry in plan["upgrade_plans"]:
        _require(entry["upgrade_plan_id"].startswith("upgrade-plan-"),
                 "upgrade plan entry id must use stable prefix")
        _require(entry["phases"] == ["discovery", "design", "implementation", "verification", "rollout"],
                 "upgrade plan phases must be stable")
        _require(entry["target_link_subsystems"], "upgrade plan must include target subsystems")
        _require("python3 -m py_compile link.py link_modes/growth/link_growth_console.py tests/test_growth_pipeline.py" in entry["verification_requirements"],
                 "upgrade plan must include compile verification")
        _require("PYTHONDONTWRITEBYTECODE=1 python3 tests/test_growth_pipeline.py" in entry["verification_requirements"],
                 "upgrade plan must include Growth tests")
        _require("PYTHONDONTWRITEBYTECODE=1 python3 link_healthcheck.py" in entry["verification_requirements"],
                 "upgrade plan must include healthcheck")
        _require("git diff --stat" in entry["required_evidence"],
                 "upgrade plan must require diff evidence")
    _require("confirm no approval/handoff/execute behavior was added" in maturity["verification_requirements"],
             "safety plan must include no-automation verification")
    _require("manual dry-run smoke test for affected Growth command" in direct["verification_requirements"],
             "large plan must require a manual dry-run smoke test")

    encoded = stable_upgrade_execution_plan_json(plan)
    _require(encoded == stable_upgrade_execution_plan_json(plan),
             "upgrade execution plan JSON serialization must be stable")
    decoded = parse_upgrade_execution_plan_json(encoded)
    _require(decoded == plan, "upgrade execution plan JSON round-trip must preserve data")
    validate_upgrade_execution_plan(plan)

    bad_plan = dict(plan)
    bad_plan.pop("plan_id")
    try:
        validate_upgrade_execution_plan(bad_plan)
    except ValueError:
        pass
    else:
        raise AssertionError("upgrade execution plan must reject missing plan_id")

    bad_writes = dict(plan)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_upgrade_execution_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("upgrade execution plan must reject writes")

    bad_complexity = dict(plan)
    bad_complexity["upgrade_plans"] = [dict(plan["upgrade_plans"][0], complexity="tiny")]
    bad_complexity["upgrade_plan_count"] = 1
    try:
        validate_upgrade_execution_plan(bad_complexity)
    except ValueError:
        pass
    else:
        raise AssertionError("upgrade execution plan must reject invalid complexity")

    bad_phases = dict(plan)
    bad_phases["upgrade_plans"] = [dict(plan["upgrade_plans"][0], phases=["implementation"])]
    bad_phases["upgrade_plan_count"] = 1
    try:
        validate_upgrade_execution_plan(bad_phases)
    except ValueError:
        pass
    else:
        raise AssertionError("upgrade execution plan must reject malformed phases")

    try:
        collect_upgrade_execution_plan({"bad": "gap"}, inventory, findings)
    except ValueError:
        pass
    else:
        raise AssertionError("upgrade execution plan must reject malformed gap preview")

    print("upgrade execution plan helper OK")


# ---------------------------------------------------------------------------
# 54. Implementation branch planner
# ---------------------------------------------------------------------------

def check_implementation_branch_plan_helper() -> None:
    """One upgrade execution item converts into a deterministic read-only branch plan."""
    from link_modes.growth.link_growth_console import (
        IMPLEMENTATION_BRANCH_PLAN_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        parse_implementation_branch_plan_json,
        stable_implementation_branch_plan_json,
        validate_implementation_branch_plan,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Self-learning recommendations",
            "category": "self_learning",
            "description": "Existing self-learning helper is present but partial.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["self-learning", "recommendation"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/memory.py",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "code",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    upgrade_item = upgrade_plan["upgrade_plans"][0]

    branch_plan = collect_implementation_branch_plan(
        upgrade_plan,
        upgrade_item,
        evidence_refs=["git diff --stat"],
        metadata={"suite": "growth"},
    )
    same = collect_implementation_branch_plan(
        upgrade_plan,
        upgrade_item,
        evidence_refs=["git diff --stat"],
        metadata={"suite": "growth"},
    )

    _require(branch_plan["branch_plan_version"] == IMPLEMENTATION_BRANCH_PLAN_VERSION,
             "implementation branch plan version mismatch")
    _require(branch_plan["branch_plan_id"] == same["branch_plan_id"],
             "implementation branch_plan_id must be deterministic")
    _require(branch_plan["proposed_branch_name"] == same["proposed_branch_name"],
             "proposed branch name must be deterministic")
    _require(branch_plan["proposed_branch_name"].startswith("link-upgrade/self-learning-feedback-loop-"),
             "proposed branch name must use stable slug prefix")
    _require(branch_plan["source_upgrade_plan_id"] == upgrade_plan["plan_id"],
             "branch plan must preserve source upgrade plan id")
    _require(branch_plan["source_upgrade_id"] == upgrade_item["upgrade_plan_id"],
             "branch plan must preserve source upgrade id")
    _require(branch_plan["risk_level"] == upgrade_item["risk"],
             "branch plan must preserve risk")
    _require(branch_plan["complexity"] == upgrade_item["complexity"],
             "branch plan must preserve complexity")
    _require(branch_plan["dry_run"] is True and branch_plan["write_allowed"] is False,
             "branch plan must remain read-only")
    _require(branch_plan["automation_allowed"] is False,
             "branch plan must not allow automation")
    _require(branch_plan["writes"] == [], "branch plan must not write files")
    _require(branch_plan["metadata"]["suite"] == "growth",
             "branch plan must preserve metadata")

    _require(branch_plan["target_files"] == ["link_modes/growth/link_growth_console.py", "tests/test_growth_pipeline.py"],
             "branch plan must derive normalized target files")
    _require(branch_plan["target_subsystems"] == upgrade_item["target_link_subsystems"],
             "branch plan must preserve target subsystems")
    _require(branch_plan["verification_commands"] == upgrade_item["verification_requirements"],
             "branch plan must preserve verification commands")
    _require(branch_plan["required_evidence"] == sorted(upgrade_item["required_evidence"]),
             "branch plan must preserve required evidence")
    _require(branch_plan["provided_evidence"] == ["git diff --stat"],
             "branch plan must normalize provided evidence")
    _require(branch_plan["blocked"] is True,
             "branch plan must block when required evidence is missing")
    _require(branch_plan["missing_evidence"],
             "blocked branch plan must list missing evidence")
    _require(branch_plan["requires_review"] is True,
             "non-low risk or blocked branch plan must require review")
    _require(branch_plan["rollback_notes"], "branch plan must include rollback notes")

    tasks = branch_plan["ordered_implementation_tasks"]
    _require([task["order"] for task in tasks] == [1, 2, 3, 4, 5],
             "implementation tasks must be ordered")
    _require([task["phase"] for task in tasks] == ["discovery", "design", "implementation", "verification", "rollout"],
             "implementation tasks must follow stable phases")
    _require(all(task["task"] for task in tasks), "implementation tasks must be non-empty")

    unblocked = collect_implementation_branch_plan(
        upgrade_plan,
        upgrade_item,
        evidence_refs=upgrade_item["required_evidence"],
    )
    _require(unblocked["blocked"] is False,
             "branch plan must unblock when all required evidence is present")
    _require(unblocked["missing_evidence"] == [],
             "unblocked branch plan must have no missing evidence")

    from_item = collect_implementation_branch_plan(upgrade_item)
    _require(from_item["source_upgrade_plan_id"] == "standalone-upgrade-plan",
             "branch plan can be built from a standalone upgrade item")
    _require(from_item["source_upgrade_id"] == upgrade_item["upgrade_plan_id"],
             "standalone branch plan must preserve source upgrade id")

    encoded = stable_implementation_branch_plan_json(branch_plan)
    _require(encoded == stable_implementation_branch_plan_json(branch_plan),
             "implementation branch plan JSON serialization must be stable")
    decoded = parse_implementation_branch_plan_json(encoded)
    _require(decoded == branch_plan, "implementation branch plan JSON round-trip must preserve data")
    validate_implementation_branch_plan(branch_plan)

    bad_missing = dict(branch_plan)
    bad_missing.pop("branch_plan_id")
    try:
        validate_implementation_branch_plan(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation branch plan must reject missing branch_plan_id")

    bad_tasks = dict(branch_plan)
    bad_tasks["ordered_implementation_tasks"] = [dict(tasks[0], order=2)]
    try:
        validate_implementation_branch_plan(bad_tasks)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation branch plan must reject unordered tasks")

    bad_writes = dict(branch_plan)
    bad_writes["writes"] = [".link/state.json"]
    try:
        validate_implementation_branch_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation branch plan must reject writes")

    bad_branch = dict(branch_plan)
    bad_branch["proposed_branch_name"] = "../bad"
    try:
        validate_implementation_branch_plan(bad_branch)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation branch plan must reject malformed branch names")

    try:
        collect_implementation_branch_plan({"bad": "upgrade"})
    except ValueError:
        pass
    else:
        raise AssertionError("implementation branch plan must reject malformed upgrade item")

    print("implementation branch plan helper OK")


# ---------------------------------------------------------------------------
# 55. Implementation work packages
# ---------------------------------------------------------------------------

def check_implementation_work_packages_helper() -> None:
    """Implementation branch plans become deterministic read-only work packages."""
    from link_modes.growth.link_growth_console import (
        IMPLEMENTATION_WORK_PACKAGES_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        parse_implementation_work_packages_json,
        stable_implementation_work_packages_json,
        validate_implementation_work_packages,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Self-learning recommendations",
            "category": "self_learning",
            "description": "Existing self-learning helper is present but partial.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["self-learning", "recommendation"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/memory.py",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "code",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(
        upgrade_plan,
        upgrade_plan["upgrade_plans"][0],
        evidence_refs=["git diff --stat"],
    )
    work_packages = collect_implementation_work_packages(branch_plan, metadata={"suite": "growth"})
    same = collect_implementation_work_packages(branch_plan, metadata={"suite": "growth"})

    _require(work_packages["work_packages_version"] == IMPLEMENTATION_WORK_PACKAGES_VERSION,
             "implementation work packages version mismatch")
    _require(work_packages["work_packages_id"] == same["work_packages_id"],
             "implementation work packages id must be deterministic")
    _require(work_packages["dry_run"] is True and work_packages["write_allowed"] is False,
             "implementation work packages must remain read-only")
    _require(work_packages["automation_allowed"] is False,
             "implementation work packages must not allow automation")
    _require(work_packages["writes"] == [], "implementation work packages must not write files")
    _require(work_packages["metadata"]["suite"] == "growth",
             "implementation work packages must preserve metadata")
    _require(work_packages["package_count"] == 1,
             "single branch plan must produce one work package")

    package = work_packages["packages"][0]
    _require(package["package_id"] == same["packages"][0]["package_id"],
             "implementation package id must be deterministic")
    _require(package["package_id"].startswith("implementation-work-package-"),
             "implementation package id must use stable prefix")
    _require(package["branch_plan_id"] == branch_plan["branch_plan_id"],
             "work package must preserve branch_plan_id")
    _require(package["upgrade_id"] == branch_plan["source_upgrade_id"],
             "work package must preserve upgrade id")
    _require(package["target_files"] == branch_plan["target_files"],
             "work package must preserve target files")
    _require(package["target_subsystems"] == branch_plan["target_subsystems"],
             "work package must preserve target subsystems")
    _require(package["verification_commands"] == branch_plan["verification_commands"],
             "work package must preserve verification commands")
    _require(package["rollback_notes"] == branch_plan["rollback_notes"],
             "work package must preserve rollback notes")
    _require(package["risk"] == branch_plan["risk_level"],
             "work package must preserve risk")
    _require(package["complexity"] == branch_plan["complexity"],
             "work package must preserve complexity")
    _require(package["estimated_file_count"] == len(branch_plan["target_files"]),
             "work package estimated_file_count must match target files")
    _require(package["estimated_test_count"] == 1,
             "work package must count planned test files")
    _require(any("All verification commands" in criterion for criterion in package["acceptance_criteria"]),
             "work package must include verification acceptance criteria")
    _require(any("Missing required evidence" in criterion for criterion in package["acceptance_criteria"]),
             "blocked branch plan must carry evidence acceptance criteria")
    _require(any("Human review" in criterion for criterion in package["acceptance_criteria"]),
             "review-required branch plan must carry review acceptance criteria")
    _require([task.split(":", 1)[0] for task in package["implementation_tasks"]] == ["1. discovery", "2. design", "3. implementation", "4. verification", "5. rollout"],
             "work package implementation tasks must preserve order")

    standalone_branch_plan = collect_implementation_branch_plan(upgrade_plan["upgrade_plans"][0])
    multi = collect_implementation_work_packages([branch_plan, standalone_branch_plan])
    _require(multi["package_count"] == 2,
             "list input should produce one package per distinct branch plan")
    _require([pkg["package_id"] for pkg in multi["packages"]] == sorted(pkg["package_id"] for pkg in multi["packages"]),
             "work packages must sort deterministically")

    encoded = stable_implementation_work_packages_json(work_packages)
    _require(encoded == stable_implementation_work_packages_json(work_packages),
             "implementation work packages JSON serialization must be stable")
    decoded = parse_implementation_work_packages_json(encoded)
    _require(decoded == work_packages,
             "implementation work packages JSON round-trip must preserve data")
    validate_implementation_work_packages(work_packages)

    bad_missing = dict(work_packages)
    bad_missing.pop("work_packages_id")
    try:
        validate_implementation_work_packages(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation work packages must reject missing id")

    bad_writes = dict(work_packages)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_implementation_work_packages(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation work packages must reject writes")

    bad_package = dict(work_packages)
    bad_package["packages"] = [dict(package, estimated_file_count=99)]
    try:
        validate_implementation_work_packages(bad_package)
    except ValueError:
        pass
    else:
        raise AssertionError("implementation work packages must reject invalid estimated_file_count")

    bad_verification = dict(work_packages)
    bad_verification["packages"] = [dict(package, verification_commands=[])]
    try:
        validate_implementation_work_packages(bad_verification)
    except TypeError:
        pass
    else:
        raise AssertionError("implementation work packages must reject missing verification commands")

    try:
        collect_implementation_work_packages({"bad": "branch-plan"})
    except ValueError:
        pass
    else:
        raise AssertionError("implementation work packages must reject malformed branch plan input")

    print("implementation work packages helper OK")


# ---------------------------------------------------------------------------
# 56. Verification plan generator
# ---------------------------------------------------------------------------

def check_verification_plan_helper() -> None:
    """Implementation work packages convert into deterministic read-only verification plans."""
    from link_modes.growth.link_growth_console import (
        VERIFICATION_PLAN_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        collect_verification_plan,
        parse_verification_plan_json,
        stable_verification_plan_json,
        validate_verification_plan,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Self-learning recommendations",
            "category": "self_learning",
            "description": "Existing self-learning helper is present but partial.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["self-learning", "recommendation"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/memory.py",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "code",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(upgrade_plan, upgrade_plan["upgrade_plans"][0])
    work_packages = collect_implementation_work_packages(branch_plan)
    verification = collect_verification_plan(work_packages, metadata={"suite": "growth"})
    same = collect_verification_plan(work_packages, metadata={"suite": "growth"})

    _require(verification["verification_plan_version"] == VERIFICATION_PLAN_VERSION,
             "verification plan version mismatch")
    _require(verification["plan_count"] == 1,
             "single work package must produce one verification plan")
    _require(verification["plans"][0]["verification_plan_id"] == same["plans"][0]["verification_plan_id"],
             "verification plan id must be deterministic")
    _require(verification["dry_run"] is True and verification["write_allowed"] is False,
             "verification plan must remain read-only")
    _require(verification["automation_allowed"] is False,
             "verification plan must not allow automation")
    _require(verification["writes"] == [], "verification plan must not write files")
    _require(verification["metadata"]["suite"] == "growth",
             "verification plan must preserve metadata")

    package = work_packages["packages"][0]
    plan = verification["plans"][0]
    _require(plan["verification_plan_id"].startswith("verification-plan-"),
             "verification plan id must use stable prefix")
    _require(plan["package_id"] == package["package_id"],
             "verification plan must preserve package_id")
    _require(plan["branch_plan_id"] == package["branch_plan_id"],
             "verification plan must preserve branch_plan_id")
    _require(plan["upgrade_id"] == package["upgrade_id"],
             "verification plan must preserve upgrade_id")
    _require(plan["compile_commands"] == ["python3 -m py_compile link.py link_modes/growth/link_growth_console.py tests/test_growth_pipeline.py"],
             "verification plan must preserve compile command")
    _require("PYTHONDONTWRITEBYTECODE=1 python3 tests/test_growth_pipeline.py" in plan["test_commands"],
             "verification plan must preserve Growth test command")
    _require("PYTHONDONTWRITEBYTECODE=1 python3 link_healthcheck.py" in plan["healthcheck_commands"],
             "verification plan must preserve healthcheck command")
    _require(plan["expected_files"] == package["target_files"],
             "verification plan must preserve expected files")
    _require(any("work package remains read-only" in item for item in plan["expected_capabilities"]),
             "verification plan must include expected capability")
    _require(any("acceptance criterion:" in item for item in plan["expected_behaviors"]),
             "verification plan must preserve acceptance criteria as expected behaviors")
    _require("compile command fails" in plan["failure_conditions"],
             "verification plan must include compile failure condition")
    _require("read-only safety metadata is removed or weakened" in plan["rollback_triggers"],
             "verification plan must include read-only rollback trigger")
    _require(plan["estimated_verification_cost"] == "medium",
             "medium package verification cost should classify as medium")
    _require(plan["estimated_verification_risk"] == "medium",
             "large medium-risk package verification risk should classify as medium")
    _require("compile output" in plan["required_evidence"],
             "verification plan must require compile evidence")
    _require("git status --short --branch" in plan["required_evidence"],
             "verification plan must require git status evidence")

    single = collect_verification_plan(package)
    _require(single["plans"][0]["verification_plan_id"] == plan["verification_plan_id"],
             "single package input must produce same verification plan id")

    encoded = stable_verification_plan_json(verification)
    _require(encoded == stable_verification_plan_json(verification),
             "verification plan JSON serialization must be stable")
    decoded = parse_verification_plan_json(encoded)
    _require(decoded == verification, "verification plan JSON round-trip must preserve data")
    validate_verification_plan(verification)

    bad_missing = dict(verification)
    bad_missing.pop("verification_plan_version")
    try:
        validate_verification_plan(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("verification plan must reject missing version")

    bad_writes = dict(verification)
    bad_writes["writes"] = [".link/state.json"]
    try:
        validate_verification_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("verification plan must reject writes")

    bad_entry = dict(verification)
    bad_entry["plans"] = [dict(plan, compile_commands=[])]
    try:
        validate_verification_plan(bad_entry)
    except TypeError:
        pass
    else:
        raise AssertionError("verification plan must reject missing compile commands")

    bad_cost = dict(verification)
    bad_cost["plans"] = [dict(plan, estimated_verification_cost="huge")]
    try:
        validate_verification_plan(bad_cost)
    except ValueError:
        pass
    else:
        raise AssertionError("verification plan must reject invalid verification cost")

    bad_files = dict(verification)
    bad_files["plans"] = [dict(plan, expected_files=["../outside.py"])]
    try:
        validate_verification_plan(bad_files)
    except ValueError:
        pass
    else:
        raise AssertionError("verification plan must reject unsafe expected files")

    try:
        collect_verification_plan({"bad": "package"})
    except ValueError:
        pass
    else:
        raise AssertionError("verification plan must reject malformed package input")

    print("verification plan helper OK")


# ---------------------------------------------------------------------------
# 57. Verified patch plan
# ---------------------------------------------------------------------------

def check_verified_patch_plan_helper() -> None:
    """Implementation work packages produce deterministic read-only patch plans."""
    from link_modes.growth.link_growth_console import (
        VERIFIED_PATCH_PLAN_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        collect_verification_plan,
        collect_verified_patch_plan,
        parse_verified_patch_plan_json,
        stable_verified_patch_plan_json,
        validate_verified_patch_plan,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Self-learning recommendations",
            "category": "self_learning",
            "description": "Existing self-learning helper is present but partial.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["self-learning", "recommendation"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/memory.py",
            "title": "Self-learning feedback loop",
            "category": "self_learning",
            "summary": "Scanner records feedback loops and improves future recommendations.",
            "source_kind": "code",
            "tags": ["self-learning", "feedback", "recommendation"],
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(upgrade_plan, upgrade_plan["upgrade_plans"][0])
    work_packages = collect_implementation_work_packages(branch_plan)
    package = work_packages["packages"][0]
    verification = collect_verification_plan(work_packages)
    provided = ["git diff --stat", "verified patch plan JSON reviewed"]
    patch_plan = collect_verified_patch_plan(
        package,
        verification_plan=verification,
        provided_evidence=provided,
        metadata={"suite": "growth"},
    )
    same = collect_verified_patch_plan(
        package,
        verification_plan=verification,
        provided_evidence=provided,
        metadata={"suite": "growth"},
    )

    _require(patch_plan["verified_patch_plan_version"] == VERIFIED_PATCH_PLAN_VERSION,
             "verified patch plan version mismatch")
    _require(patch_plan["verified_patch_plan_id"] == same["verified_patch_plan_id"],
             "verified patch plan id must be deterministic")
    _require(patch_plan["upgrade_id"] == package["upgrade_id"],
             "verified patch plan must preserve upgrade id")
    _require(patch_plan["branch_plan_id"] == package["branch_plan_id"],
             "verified patch plan must preserve branch plan id")
    _require(patch_plan["work_package_id"] == package["package_id"],
             "verified patch plan must preserve work package id")
    _require(patch_plan["dry_run"] is True and patch_plan["write_allowed"] is False,
             "verified patch plan must remain read-only")
    _require(patch_plan["automation_allowed"] is False,
             "verified patch plan must not allow automation")
    _require(patch_plan["writes"] == [], "verified patch plan must not write files")
    _require(patch_plan["metadata"]["suite"] == "growth",
             "verified patch plan must preserve metadata")

    _require(patch_plan["target_files"] == package["target_files"],
             "verified patch plan must preserve target files")
    _require(patch_plan["estimated_files_changed"] == len(package["target_files"]),
             "estimated_files_changed must match target files")
    _require(patch_plan["estimated_tests_affected"] == package["estimated_test_count"],
             "estimated_tests_affected must match package test count")
    operations = patch_plan["patch_operations"]
    _require(len(operations) == len(package["target_files"]),
             "patch operations must cover each target file")
    by_file = {operation["file_path"]: operation for operation in operations}
    _require(by_file["link_modes/growth/link_growth_console.py"]["operation_type"] == "modify_file",
             "source file operation should be modify_file")
    _require(by_file["tests/test_growth_pipeline.py"]["operation_type"] == "update_test",
             "test file operation should be update_test")
    for operation in operations:
        _require(operation["operation_id"].startswith("patch-operation-"),
                 "patch operation id must use stable prefix")
        _require(operation["rationale"], "patch operation must include rationale")
        _require(operation["expected_result"], "patch operation must include expected_result")
        _require(operation["risk_level"] == package["risk"],
                 "patch operation must preserve package risk")

    _require(patch_plan["compile_expectations"], "compile expectations must be present")
    _require(patch_plan["test_expectations"], "test expectations must be present")
    _require(patch_plan["healthcheck_expectations"], "healthcheck expectations must be present")
    _require(any("py_compile" in item for item in patch_plan["compile_expectations"]),
             "compile expectations must include py_compile command")
    _require(any("tests/test_growth_pipeline.py" in item for item in patch_plan["test_expectations"]),
             "test expectations must include Growth tests")
    _require(any("link_healthcheck.py" in item for item in patch_plan["healthcheck_expectations"]),
             "healthcheck expectations must include healthcheck")

    _require("git diff --stat" in patch_plan["required_evidence"],
             "required evidence must include git diff stat")
    _require(patch_plan["provided_evidence"] == sorted(provided),
             "provided evidence must normalize and sort")
    _require("git diff --stat" not in patch_plan["missing_evidence"],
             "provided evidence must not appear missing")
    _require(patch_plan["missing_evidence"], "missing evidence must be accounted for")

    generated_verification = collect_verified_patch_plan(package)
    _require(generated_verification["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "generated verification plan should preserve patch plan id")

    encoded = stable_verified_patch_plan_json(patch_plan)
    _require(encoded == stable_verified_patch_plan_json(patch_plan),
             "verified patch plan JSON serialization must be stable")
    decoded = parse_verified_patch_plan_json(encoded)
    _require(decoded == patch_plan, "verified patch plan JSON round-trip must preserve data")
    validate_verified_patch_plan(patch_plan)

    bad_missing = dict(patch_plan)
    bad_missing.pop("verified_patch_plan_id")
    try:
        validate_verified_patch_plan(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject missing id")

    bad_operation = dict(patch_plan)
    bad_operation["patch_operations"] = [dict(operations[0], operation_type="execute_shell")]
    try:
        validate_verified_patch_plan(bad_operation)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject invalid operation type")

    bad_file = dict(patch_plan)
    bad_file["patch_operations"] = [dict(operations[0], file_path="outside.py")]
    try:
        validate_verified_patch_plan(bad_file)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject operation outside target files")

    bad_count = dict(patch_plan)
    bad_count["estimated_files_changed"] = 99
    try:
        validate_verified_patch_plan(bad_count)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject invalid file accounting")

    bad_writes = dict(patch_plan)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_verified_patch_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject writes")

    try:
        collect_verified_patch_plan({"bad": "package"})
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch plan must reject malformed package")

    print("verified patch plan helper OK")


# ---------------------------------------------------------------------------
# 58. Verified patch diff preview helpers
# ---------------------------------------------------------------------------

def check_verified_patch_diff_helper() -> None:
    """Verified patch plans produce deterministic read-only diff previews."""
    from link_modes.growth.link_growth_console import (
        VERIFIED_PATCH_DIFF_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        collect_verification_plan,
        collect_verified_patch_diff,
        collect_verified_patch_plan,
        parse_verified_patch_diff_json,
        stable_verified_patch_diff_json,
        validate_verified_patch_diff,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Growth planning previews",
            "category": "workflow_ux",
            "description": "Existing planning helpers are available but need patch previews.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["planning", "patch-preview"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "sota/patch_preview.py",
            "title": "Patch diff preview",
            "category": "tests/verification",
            "summary": "Scanner previews planned diffs before implementation.",
            "source_kind": "code",
            "tags": ["patch", "diff", "verification"],
        },
    ], source_label="sota-scan")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(upgrade_plan, upgrade_plan["upgrade_plans"][0])
    work_packages = collect_implementation_work_packages(branch_plan)
    package = work_packages["packages"][0]
    verification = collect_verification_plan(work_packages)
    patch_plan = collect_verified_patch_plan(package, verification_plan=verification)
    diff = collect_verified_patch_diff(patch_plan, metadata={"suite": "growth"})
    same = collect_verified_patch_diff(patch_plan, metadata={"suite": "growth"})

    _require(diff["verified_patch_diff_version"] == VERIFIED_PATCH_DIFF_VERSION,
             "verified patch diff version mismatch")
    _require(diff["verified_patch_diff_id"] == same["verified_patch_diff_id"],
             "verified patch diff id must be deterministic")
    _require(diff["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "verified patch diff must preserve patch plan id")
    _require(diff["branch_plan_id"] == patch_plan["branch_plan_id"],
             "verified patch diff must preserve branch plan id")
    _require(diff["work_package_id"] == patch_plan["work_package_id"],
             "verified patch diff must preserve work package id")
    _require(diff["upgrade_id"] == patch_plan["upgrade_id"],
             "verified patch diff must preserve upgrade id")
    _require(diff["dry_run"] is True and diff["write_allowed"] is False,
             "verified patch diff must remain read-only")
    _require(diff["automation_allowed"] is False,
             "verified patch diff must not allow automation")
    _require(diff["writes"] == [], "verified patch diff must not write files")
    _require(diff["metadata"]["suite"] == "growth",
             "verified patch diff must preserve metadata")

    entries = diff["diff_entries"]
    _require(len(entries) == len(patch_plan["patch_operations"]),
             "diff entries must cover patch operations")
    _require([entry["diff_entry_id"] for entry in entries] == sorted(entry["diff_entry_id"] for entry in entries),
             "diff entries must be deterministically sorted")
    operation_ids = {operation["operation_id"] for operation in patch_plan["patch_operations"]}
    _require({entry["operation_id"] for entry in entries} == operation_ids,
             "diff entries must preserve patch operation ids")
    by_file = {entry["file_path"]: entry for entry in entries}
    _require(by_file["link_modes/growth/link_growth_console.py"]["operation_type"] == "modify_file",
             "source file diff should be modify_file")
    _require(by_file["tests/test_growth_pipeline.py"]["operation_type"] == "update_test",
             "test file diff should be update_test")
    for entry in entries:
        _require(entry["diff_entry_id"].startswith("verified-patch-diff-entry-"),
                 "diff entry id must use stable prefix")
        _require(entry["diff_preview"].startswith("--- old\n+++ new\n@@"),
                 "diff preview must use unified-diff-style headers")
        _require("- " in entry["diff_preview"] and "+ " in entry["diff_preview"],
                 "diff preview must include before and after lines")
        _require(entry["before_summary"], "diff entry must include before_summary")
        _require(entry["after_summary"], "diff entry must include after_summary")
        _require(entry["change_description"], "diff entry must include change_description")
        _require(entry["compile_impact"], "diff entry must include compile impact")
        _require(entry["test_impact"], "diff entry must include test impact")
        _require(entry["healthcheck_impact"], "diff entry must include healthcheck impact")
        _require(0.0 <= entry["confidence_score"] <= 1.0,
                 "diff entry confidence must be bounded")
        _require(0.0 <= entry["risk_score"] <= 1.0,
                 "diff entry risk must be bounded")

    _require(diff["estimated_added_lines"] == sum(entry["estimated_added_lines"] for entry in entries),
             "added line accounting must match entries")
    _require(diff["estimated_removed_lines"] == sum(entry["estimated_removed_lines"] for entry in entries),
             "removed line accounting must match entries")
    _require(diff["estimated_modified_lines"] == sum(entry["estimated_modified_lines"] for entry in entries),
             "modified line accounting must match entries")
    _require(diff["estimated_added_lines"] > 0,
             "diff preview must estimate added lines")
    _require(diff["compile_impact"] == patch_plan["compile_expectations"],
             "diff compile impact must come from patch plan")
    _require(diff["test_impact"] == patch_plan["test_expectations"],
             "diff test impact must come from patch plan")
    _require(diff["healthcheck_impact"] == patch_plan["healthcheck_expectations"],
             "diff healthcheck impact must come from patch plan")
    _require(0.0 <= diff["confidence_score"] <= 1.0,
             "diff confidence must be bounded")
    _require(0.0 <= diff["risk_score"] <= 1.0,
             "diff risk must be bounded")

    encoded = stable_verified_patch_diff_json(diff)
    _require(encoded == stable_verified_patch_diff_json(diff),
             "verified patch diff JSON serialization must be stable")
    decoded = parse_verified_patch_diff_json(encoded)
    _require(decoded == diff, "verified patch diff JSON round-trip must preserve data")
    validate_verified_patch_diff(diff)

    bad_missing = dict(diff)
    bad_missing.pop("verified_patch_diff_id")
    try:
        validate_verified_patch_diff(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject missing id")

    bad_operation = dict(diff)
    bad_operation["diff_entries"] = [dict(entries[0], operation_type="execute_shell")]
    try:
        validate_verified_patch_diff(bad_operation)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject invalid operation type")

    bad_lines = dict(diff)
    bad_lines["estimated_added_lines"] = 999
    try:
        validate_verified_patch_diff(bad_lines)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject invalid line accounting")

    bad_confidence = dict(diff)
    bad_confidence["confidence_score"] = 1.5
    try:
        validate_verified_patch_diff(bad_confidence)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject invalid confidence")

    bad_risk = dict(diff)
    bad_risk["risk_score"] = -0.1
    try:
        validate_verified_patch_diff(bad_risk)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject invalid risk")

    bad_writes = dict(diff)
    bad_writes["writes"] = [".link/runtime.json"]
    try:
        validate_verified_patch_diff(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject writes")

    bad_patch_plan = dict(patch_plan)
    bad_patch_plan["patch_operations"] = [dict(patch_plan["patch_operations"][0], operation_type="execute_shell")]
    try:
        collect_verified_patch_diff(bad_patch_plan)
    except ValueError:
        pass
    else:
        raise AssertionError("verified patch diff must reject malformed patch plan")

    print("verified patch diff helper OK")


# ---------------------------------------------------------------------------
# 59. Patch applier boundary helper
# ---------------------------------------------------------------------------

def check_patch_applier_boundary_helper() -> None:
    """Patch applier boundary constrains future patch application read-only."""
    from link_modes.growth.link_growth_console import (
        collect_execution_approval_checklist,
        collect_execution_review,
        collect_growth_planning_chain_preview,
        collect_patch_applier_boundary,
        collect_workspace_creator_runtime_boundary,
        collect_workspace_creator_runtime_plan,
        parse_patch_applier_boundary_json,
        stable_patch_applier_boundary_json,
        validate_patch_applier_boundary,
    )

    chain = collect_growth_planning_chain_preview()
    patch_plan = chain["verified_patch_plan"]
    patch_diff = chain["verified_patch_diff"]
    gate_stack = chain["execution_gate_stack_preview"]
    approval = collect_execution_approval_checklist(chain)
    evidence_contract = chain["execution_evidence_contract"]
    workspace_boundary = collect_workspace_creator_runtime_boundary(chain)
    workspace_plan = collect_workspace_creator_runtime_plan(chain)
    boundary = collect_patch_applier_boundary(
        patch_plan,
        patch_diff,
        gate_stack,
        approval,
        evidence_contract,
        workspace_boundary,
        workspace_plan,
        planning_chain_id=chain["planning_chain_id"],
        metadata={"suite": "growth"},
    )
    same = collect_patch_applier_boundary(
        patch_plan,
        patch_diff,
        gate_stack,
        approval,
        evidence_contract,
        workspace_boundary,
        workspace_plan,
        planning_chain_id=chain["planning_chain_id"],
        metadata={"suite": "growth"},
    )
    _require(boundary["patch_applier_boundary_id"] == same["patch_applier_boundary_id"],
             "patch applier boundary id must be deterministic")
    decoded = parse_patch_applier_boundary_json(stable_patch_applier_boundary_json(boundary))
    _require(decoded == boundary, "patch applier boundary JSON must round trip")
    validate_patch_applier_boundary(
        boundary,
        patch_plan,
        patch_diff,
        gate_stack,
        approval,
        evidence_contract,
        workspace_boundary,
        workspace_plan,
    )

    _require(boundary["planning_chain_id"] == chain["planning_chain_id"],
             "patch applier boundary must reference planning chain")
    _require(boundary["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "patch applier boundary must reference patch plan")
    _require(boundary["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "patch applier boundary must reference patch diff")
    _require(boundary["execution_package_id"] == workspace_plan["execution_package_id"],
             "patch applier boundary must reference execution package")
    _require(boundary["workspace_boundary_id"] == workspace_boundary["workspace_boundary_id"],
             "patch applier boundary must reference workspace boundary")
    _require(boundary["runtime_workspace_plan_id"] == workspace_plan["runtime_workspace_plan_id"],
             "patch applier boundary must reference runtime workspace plan")
    _require(boundary["allowed_target_files"] == patch_plan["target_files"],
             "patch applier boundary must preserve target files")
    _require(boundary["max_files_changed"] == patch_plan["estimated_files_changed"],
             "patch applier boundary must preserve file limit")
    _require(boundary["max_operations"] == len(patch_plan["patch_operations"]),
             "patch applier boundary must preserve operation limit")
    _require(boundary["max_estimated_added_lines"] == patch_diff["estimated_added_lines"],
             "patch applier boundary must preserve added line limit")
    _require(boundary["max_estimated_removed_lines"] == patch_diff["estimated_removed_lines"],
             "patch applier boundary must preserve removed line limit")
    _require("modify_file" in boundary["allowed_operation_types"],
             "patch applier boundary must allow verified modify operations")
    _require("execute_shell" in boundary["forbidden_operation_types"],
             "patch applier boundary must forbid shell execution operations")
    _require(set(boundary["risky_operation_types"]).issubset(set(boundary["operation_requires_review"])),
             "risky operations must require review")
    for required in (
        "approval checklist is not pass",
        "gate stack contains block status",
        "patch target path is outside allowed workspace files",
    ):
        _require(required in boundary["fail_closed_conditions"],
                 "patch applier boundary must include fail-closed condition")
    _require(boundary["required_patch_evidence"], "patch evidence must be required")
    _require(boundary["required_diff_evidence"], "diff evidence must be required")
    _require(boundary["required_file_hash_evidence"], "file hash evidence must be required")
    _require(boundary["required_journal_evidence"], "journal evidence must be required")
    _require(boundary["required_reviewer_summary"] is True,
             "reviewer summary must be required")
    _require(boundary["dry_run"] is True and boundary["write_allowed"] is False,
             "patch applier boundary must remain read-only")
    _require(boundary["automation_allowed"] is False and boundary["writes"] == [],
             "patch applier boundary must not allow automation or writes")

    bad_missing = dict(boundary)
    bad_missing.pop("patch_applier_boundary_id")
    try:
        validate_patch_applier_boundary(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must reject missing id")

    bad_target = dict(boundary)
    bad_target["allowed_target_files"] = [".agents/runtime.json"]
    try:
        validate_patch_applier_boundary(bad_target)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must reject forbidden target paths")

    bad_ops = dict(boundary)
    bad_ops["allowed_operation_types"] = [*boundary["allowed_operation_types"], "execute_shell"]
    bad_ops["allowed_operation_types"] = sorted(set(bad_ops["allowed_operation_types"]))
    try:
        validate_patch_applier_boundary(bad_ops)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must reject forbidden allowed operation")

    bad_risky = dict(boundary)
    bad_risky["operation_requires_review"] = [item for item in boundary["operation_requires_review"] if item != "delete_file"]
    try:
        validate_patch_applier_boundary(bad_risky)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must require review for risky operations")

    bad_limit = dict(boundary)
    bad_limit["max_operations"] = 999
    try:
        validate_patch_applier_boundary(bad_limit, patch_plan)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must reject invalid operation limit")

    bad_evidence = dict(boundary)
    bad_evidence["required_patch_evidence"] = []
    try:
        validate_patch_applier_boundary(bad_evidence)
    except TypeError:
        pass
    else:
        raise AssertionError("patch applier boundary must require patch evidence")

    bad_fail_closed = dict(boundary)
    bad_fail_closed["fail_closed_conditions"] = [
        item for item in boundary["fail_closed_conditions"]
        if item != "gate stack contains block status"
    ]
    try:
        validate_patch_applier_boundary(bad_fail_closed)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must require fail-closed gate condition")

    bad_writes = dict(boundary)
    bad_writes["writes"] = ["link_modes/growth/link_growth_console.py"]
    try:
        validate_patch_applier_boundary(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("patch applier boundary must reject writes")

    print("patch applier boundary helper OK")


# ---------------------------------------------------------------------------
# 59. Patch behavior quality gate helpers
# ---------------------------------------------------------------------------

def check_patch_behavior_quality_gate_helper() -> None:
    """Patch behavior quality gates score plans/diffs without writes."""
    from link_modes.growth.link_growth_console import (
        PATCH_BEHAVIOR_QUALITY_GATE_VERSION,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_patch_behavior_quality_gate,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        collect_verification_plan,
        collect_verified_patch_diff,
        collect_verified_patch_plan,
        parse_patch_behavior_quality_gate_json,
        stable_patch_behavior_quality_gate_json,
        validate_patch_behavior_quality_gate,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Verified patch planning",
            "category": "workflow_ux",
            "description": "Verified patch plans exist but need behavior quality gates.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["patch", "quality-gate"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "karpathy/CLAUDE.md",
            "title": "Surgical patch behavior",
            "category": "CLI/workflow UX",
            "summary": "Guidelines require assumptions, small diffs, and verification loops.",
            "source_kind": "doc",
            "tags": ["assumptions", "surgical", "verification"],
        },
    ], source_label="karpathy-skills")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(upgrade_plan, upgrade_plan["upgrade_plans"][0])
    work_packages = collect_implementation_work_packages(branch_plan)
    package = work_packages["packages"][0]
    verification = collect_verification_plan(work_packages)
    initial_plan = collect_verified_patch_plan(package, verification_plan=verification)
    complete_evidence = list(initial_plan["required_evidence"])
    patch_plan = collect_verified_patch_plan(
        package,
        verification_plan=verification,
        provided_evidence=complete_evidence,
    )
    patch_diff = collect_verified_patch_diff(patch_plan)
    assumptions = ["Scope is limited to Growth planning helpers and tests."]
    gate = collect_patch_behavior_quality_gate(
        patch_plan,
        patch_diff=patch_diff,
        assumptions=assumptions,
        metadata={"suite": "growth"},
    )
    same = collect_patch_behavior_quality_gate(
        patch_plan,
        patch_diff=patch_diff,
        assumptions=assumptions,
        metadata={"suite": "growth"},
    )

    _require(gate["quality_gate_version"] == PATCH_BEHAVIOR_QUALITY_GATE_VERSION,
             "patch behavior quality gate version mismatch")
    _require(gate["quality_gate_id"] == same["quality_gate_id"],
             "patch behavior quality gate id must be deterministic")
    _require(gate["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "quality gate must preserve patch plan id")
    _require(gate["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "quality gate must preserve patch diff id")
    _require(gate["pass_status"] == "pass", "clean quality gate should pass")
    _require(gate["findings"] == [], "passing quality gate should not have findings")
    _require(gate["required_clarifications"] == [], "passing quality gate should not need clarification")
    _require(0.0 <= gate["quality_score"] <= 1.0, "quality score must be bounded")
    _require(0.0 <= gate["risk_score"] <= 1.0, "risk score must be bounded")
    _require(gate["dry_run"] is True and gate["write_allowed"] is False,
             "quality gate must remain read-only")
    _require(gate["automation_allowed"] is False, "quality gate must not allow automation")
    _require(gate["writes"] == [], "quality gate must not write files")
    _require(gate["metadata"]["suite"] == "growth", "quality gate must preserve metadata")

    encoded = stable_patch_behavior_quality_gate_json(gate)
    _require(encoded == stable_patch_behavior_quality_gate_json(gate),
             "patch behavior quality gate JSON serialization must be stable")
    decoded = parse_patch_behavior_quality_gate_json(encoded)
    _require(decoded == gate, "patch behavior quality gate JSON round-trip must preserve data")
    validate_patch_behavior_quality_gate(gate)

    missing_evidence_gate = collect_patch_behavior_quality_gate(
        initial_plan,
        assumptions=assumptions,
    )
    _require(missing_evidence_gate["pass_status"] in {"review", "block"},
             "missing evidence must prevent pass status")
    _require(missing_evidence_gate["quality_score"] < gate["quality_score"],
             "missing evidence must lower quality score")
    _require(any(item["category"] == "missing_evidence" for item in missing_evidence_gate["findings"]),
             "missing evidence finding must be present")

    no_assumptions_gate = collect_patch_behavior_quality_gate(patch_plan, patch_diff=patch_diff)
    _require(no_assumptions_gate["pass_status"] == "review",
             "missing assumptions should require review")
    _require(any(item["category"] == "assumptions" for item in no_assumptions_gate["findings"]),
             "assumption finding must be present")
    _require(no_assumptions_gate["required_clarifications"],
             "missing assumptions must require clarification")

    risky_plan = dict(patch_plan)
    risky_ops = [dict(operation) for operation in patch_plan["patch_operations"]]
    risky_ops[0]["operation_type"] = "delete_file"
    risky_ops[0]["expected_result"] = "The obsolete target is removed after approval and verification."
    risky_plan["patch_operations"] = risky_ops
    risky_gate = collect_patch_behavior_quality_gate(risky_plan, assumptions=assumptions)
    _require(risky_gate["pass_status"] == "block",
             "delete operations should block before explicit review")
    _require(any(item["category"] == "risky_operations" for item in risky_gate["findings"]),
             "risky operation finding must be present")

    unclear_plan = dict(patch_plan)
    unclear_ops = [dict(operation) for operation in patch_plan["patch_operations"]]
    unclear_ops[0]["rationale"] = "todo"
    unclear_ops[0]["expected_result"] = "tbd"
    unclear_plan["patch_operations"] = unclear_ops
    unclear_gate = collect_patch_behavior_quality_gate(unclear_plan, assumptions=assumptions)
    _require(unclear_gate["pass_status"] == "review",
             "unclear operation should require review")
    _require(any(item["category"] == "clarity" for item in unclear_gate["findings"]),
             "clarity finding must be present")
    _require(unclear_gate["required_clarifications"],
             "unclear operation must require clarification")

    broad_plan = dict(patch_plan)
    extra_files = [f"link_modes/growth/extra_{index}.py" for index in range(12)]
    broad_plan["target_files"] = sorted(set(patch_plan["target_files"] + extra_files))
    broad_plan["estimated_files_changed"] = len(broad_plan["target_files"])
    broad_plan["estimated_tests_affected"] = len([path for path in broad_plan["target_files"] if path.startswith("tests/")])
    base_operation = dict(patch_plan["patch_operations"][0])
    broad_ops = [dict(operation) for operation in patch_plan["patch_operations"]]
    for file_path in extra_files:
        operation = dict(base_operation)
        operation["operation_id"] = f"patch-operation-extra-{file_path.rsplit('_', 1)[-1].replace('.py', '')}"
        operation["file_path"] = file_path
        operation["operation_type"] = "modify_file"
        operation["rationale"] = f"Update {file_path} only if this broader patch is explicitly approved."
        operation["expected_result"] = f"{file_path} contains a reviewed implementation change."
        broad_ops.append(operation)
    broad_plan["patch_operations"] = broad_ops
    broad_gate = collect_patch_behavior_quality_gate(broad_plan, assumptions=assumptions)
    _require(broad_gate["pass_status"] == "block",
             "overbroad file count should block")
    _require(any(item["category"] == "surgicality" for item in broad_gate["findings"]),
             "surgicality finding must be present")

    bad_missing = dict(gate)
    bad_missing.pop("quality_gate_id")
    try:
        validate_patch_behavior_quality_gate(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("quality gate must reject missing id")

    bad_writes = dict(gate)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_patch_behavior_quality_gate(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("quality gate must reject writes")

    mismatched_diff = dict(patch_diff)
    mismatched_diff["verified_patch_plan_id"] = "verified-patch-plan-other"
    try:
        collect_patch_behavior_quality_gate(patch_plan, patch_diff=mismatched_diff, assumptions=assumptions)
    except ValueError:
        pass
    else:
        raise AssertionError("quality gate must reject mismatched diff")

    print("patch behavior quality gate helper OK")


# ---------------------------------------------------------------------------
# 60. Autonomous execution package helpers
# ---------------------------------------------------------------------------

def check_autonomous_execution_package_helper() -> None:
    """Autonomous execution packages describe future execution without doing it."""
    from link_modes.growth.link_growth_console import (
        AUTONOMOUS_EXECUTION_PACKAGE_VERSION,
        collect_autonomous_execution_package,
        collect_capability_gap_preview,
        collect_implementation_branch_plan,
        collect_implementation_work_packages,
        collect_link_capability_inventory,
        collect_patch_behavior_quality_gate,
        collect_repo_value_scan,
        collect_upgrade_execution_plan,
        collect_verification_plan,
        collect_verified_patch_diff,
        collect_verified_patch_plan,
        parse_autonomous_execution_package_json,
        stable_autonomous_execution_package_json,
        validate_autonomous_execution_package,
    )

    inventory = collect_link_capability_inventory([
        {
            "name": "Autonomous execution planning",
            "category": "workflow_ux",
            "description": "Execution is not enabled, but Link can describe future execution safely.",
            "source": "link_modes/growth/link_growth_console.py",
            "confidence": "high",
            "tags": ["execution", "planning", "safety"],
            "risk_level": "medium",
            "maturity_level": "partial",
        },
    ])
    repo_scan = collect_repo_value_scan([
        {
            "path": "karpathy/execution-loop.md",
            "title": "Verified execution loop",
            "category": "CLI/workflow UX",
            "summary": "Describe workspace, branch, patch, verify, and review steps before execution.",
            "source_kind": "doc",
            "tags": ["execution", "verification", "review"],
        },
    ], source_label="karpathy-skills")
    findings = [dict(item) for item in repo_scan["findings"]]
    for finding in findings:
        finding["required_maturity_level"] = "verified"
    gap_preview = collect_capability_gap_preview(inventory, findings)
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings)
    branch_plan = collect_implementation_branch_plan(upgrade_plan, upgrade_plan["upgrade_plans"][0])
    work_packages = collect_implementation_work_packages(branch_plan)
    package = work_packages["packages"][0]
    verification = collect_verification_plan(work_packages)
    initial_plan = collect_verified_patch_plan(package, verification_plan=verification)
    patch_plan = collect_verified_patch_plan(
        package,
        verification_plan=verification,
        provided_evidence=list(initial_plan["required_evidence"]),
    )
    patch_diff = collect_verified_patch_diff(patch_plan)
    quality_gate = collect_patch_behavior_quality_gate(
        patch_plan,
        patch_diff=patch_diff,
        assumptions=["Execution remains disabled; this package is only a preview."],
    )
    execution = collect_autonomous_execution_package(
        patch_plan,
        verification_plan=verification,
        patch_diff=patch_diff,
        quality_gate=quality_gate,
        metadata={"suite": "growth"},
    )
    same = collect_autonomous_execution_package(
        patch_plan,
        verification_plan=verification,
        patch_diff=patch_diff,
        quality_gate=quality_gate,
        metadata={"suite": "growth"},
    )

    _require(execution["execution_package_version"] == AUTONOMOUS_EXECUTION_PACKAGE_VERSION,
             "autonomous execution package version mismatch")
    _require(execution["execution_package_id"] == same["execution_package_id"],
             "autonomous execution package id must be deterministic")
    _require(execution["upgrade_id"] == patch_plan["upgrade_id"],
             "execution package must preserve upgrade id")
    _require(execution["branch_plan_id"] == patch_plan["branch_plan_id"],
             "execution package must preserve branch plan id")
    _require(execution["work_package_id"] == patch_plan["work_package_id"],
             "execution package must preserve work package id")
    _require(execution["verification_plan_id"] == verification["plans"][0]["verification_plan_id"],
             "execution package must preserve verification plan id")
    _require(execution["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "execution package must preserve patch plan id")
    _require(execution["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "execution package must preserve patch diff id")
    _require(execution["quality_gate_id"] == quality_gate["quality_gate_id"],
             "execution package must preserve quality gate id")
    _require(execution["dry_run"] is True and execution["write_allowed"] is False,
             "execution package must remain read-only")
    _require(execution["automation_allowed"] is False,
             "execution package must not allow automation")
    _require(execution["writes"] == [], "execution package must not write files")
    _require(execution["metadata"]["suite"] == "growth", "execution package must preserve metadata")

    expected_stage_names = [
        "create workspace",
        "create branch",
        "apply patch operations",
        "run compile",
        "run tests",
        "run healthcheck",
        "evaluate quality gate",
        "produce review bundle",
    ]
    stages = execution["execution_stages"]
    _require(execution["stage_count"] == len(expected_stage_names),
             "execution package must contain canonical stages")
    _require([stage["stage_name"] for stage in stages] == expected_stage_names,
             "execution stages must be in canonical order")
    _require([stage["order"] for stage in stages] == list(range(1, len(stages) + 1)),
             "execution stages must be ordered from 1")
    _require(len({stage["stage_id"] for stage in stages}) == len(stages),
             "execution stage ids must be unique")
    for stage in stages:
        _require(stage["inputs"], "execution stage must include inputs")
        _require(stage["outputs"], "execution stage must include outputs")
        _require(stage["success_criteria"], "execution stage must include success criteria")
        _require(stage["failure_criteria"], "execution stage must include failure criteria")
        _require(stage["rollback_action"], "execution stage must include rollback action")
    by_name = {stage["stage_name"]: stage for stage in stages}
    _require(any("uncreated" in output for output in by_name["create workspace"]["outputs"]),
             "workspace stage must explicitly avoid creating workspace")
    _require(any("uncreated" in output for output in by_name["create branch"]["outputs"]),
             "branch stage must explicitly avoid creating branch")
    _require(any("no files modified" in output for output in by_name["apply patch operations"]["outputs"]),
             "patch stage must explicitly avoid modifying files")
    _require(any("unexecuted" in output for output in by_name["run compile"]["outputs"]),
             "compile stage must remain unexecuted")
    _require(any("unexecuted" in output for output in by_name["run tests"]["outputs"]),
             "test stage must remain unexecuted")
    _require(any("unexecuted" in output for output in by_name["run healthcheck"]["outputs"]),
             "healthcheck stage must remain unexecuted")
    _require(quality_gate["quality_gate_id"] in by_name["evaluate quality gate"]["inputs"],
             "quality gate stage must reference quality gate")

    encoded = stable_autonomous_execution_package_json(execution)
    _require(encoded == stable_autonomous_execution_package_json(execution),
             "autonomous execution package JSON serialization must be stable")
    decoded = parse_autonomous_execution_package_json(encoded)
    _require(decoded == execution, "autonomous execution package JSON round-trip must preserve data")
    validate_autonomous_execution_package(execution)

    generated = collect_autonomous_execution_package(
        patch_plan,
        verification_plan=verification,
        assumptions=["Execution remains disabled; this package is only a preview."],
    )
    _require(generated["upgrade_id"] == execution["upgrade_id"],
             "generated diff/gate package must preserve upgrade id")
    _require(generated["stage_count"] == execution["stage_count"],
             "generated diff/gate package must preserve stage count")

    bad_missing = dict(execution)
    bad_missing.pop("execution_package_id")
    try:
        validate_autonomous_execution_package(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject missing id")

    bad_writes = dict(execution)
    bad_writes["writes"] = [".link/runtime.json"]
    try:
        validate_autonomous_execution_package(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject writes")

    bad_stage_order = dict(execution)
    bad_stages = [dict(stage) for stage in stages]
    bad_stages[0]["stage_name"] = "run tests"
    bad_stage_order["execution_stages"] = bad_stages
    try:
        validate_autonomous_execution_package(bad_stage_order)
    except ValueError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject invalid stage order")

    bad_stage = dict(execution)
    bad_stage_entries = [dict(stage) for stage in stages]
    bad_stage_entries[0]["inputs"] = []
    bad_stage["execution_stages"] = bad_stage_entries
    try:
        validate_autonomous_execution_package(bad_stage)
    except TypeError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject malformed stage")

    mismatched_diff = dict(patch_diff)
    mismatched_diff["verified_patch_plan_id"] = "verified-patch-plan-other"
    try:
        collect_autonomous_execution_package(patch_plan, verification_plan=verification, patch_diff=mismatched_diff)
    except ValueError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject mismatched diff")

    mismatched_gate = dict(quality_gate)
    mismatched_gate["verified_patch_plan_id"] = "verified-patch-plan-other"
    try:
        collect_autonomous_execution_package(
            patch_plan,
            verification_plan=verification,
            patch_diff=patch_diff,
            quality_gate=mismatched_gate,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("autonomous execution package must reject mismatched quality gate")

    print("autonomous execution package helper OK")


# ---------------------------------------------------------------------------
# 61. Growth planning-chain CLI preview
# ---------------------------------------------------------------------------

def check_growth_planning_chain_cli() -> None:
    """planning-chain exposes the full read-only planning chain via CLI."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_execution_attempt_history,
        collect_execution_evidence_contract,
        collect_execution_gate_stack_preview,
        collect_execution_readiness_dashboard_summary,
        collect_execution_journal_plan,
        collect_execution_preflight_checklist,
        collect_growth_planning_chain_preview,
        collect_planning_chain_review_bundle,
        parse_growth_planning_chain_json,
        planning_chain_main,
        validate_growth_planning_chain_preview,
        validate_planning_chain_review_bundle,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("planning-chain" in help_out.getvalue(), "growth help must include planning-chain")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = planning_chain_main(["--json"])
    _require(json_rc == 0, "planning-chain --json must return 0")
    parsed = parse_growth_planning_chain_json(json_out.getvalue())
    validate_growth_planning_chain_preview(parsed)
    again = collect_growth_planning_chain_preview()
    _require(parsed["planning_chain_id"] == again["planning_chain_id"],
             "planning_chain_id must be deterministic")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "planning chain must remain read-only")
    _require(parsed["automation_allowed"] is False,
             "planning chain must not allow automation")
    _require(parsed["writes"] == [], "planning chain must not write files")

    for key in (
        "verified_patch_plan",
        "verified_patch_diff",
        "patch_behavior_quality_gate",
        "autonomous_execution_package",
        "execution_workspace_plan",
        "execution_retry_policy",
        "execution_event_timeline",
        "execution_journal_plan",
        "execution_evidence_contract",
        "execution_preflight_checklist",
        "execution_attempt_history",
        "execution_readiness_dashboard_summary",
        "execution_gate_stack_preview",
        "witness_manifest_plan",
        "human_approval_package",
        "execution_readiness_bundle",
        "planning_chain_review_bundle",
        "stage_summary",
    ):
        _require(key in parsed, f"planning-chain JSON must include {key}")

    top_upgrade = parsed["upgrade_execution_plan"]["upgrade_plans"][0]
    branch_plan = parsed["implementation_branch_plan"]
    work_package = parsed["implementation_work_packages"]["packages"][0]
    verification = parsed["verification_plan"]["plans"][0]
    patch_plan = parsed["verified_patch_plan"]
    patch_diff = parsed["verified_patch_diff"]
    quality_gate = parsed["patch_behavior_quality_gate"]
    execution_package = parsed["autonomous_execution_package"]
    workspace = parsed["execution_workspace_plan"]
    retry_policy = parsed["execution_retry_policy"]
    event_timeline = parsed["execution_event_timeline"]
    journal_plan = parsed["execution_journal_plan"]
    evidence_contract = parsed["execution_evidence_contract"]
    preflight_checklist = parsed["execution_preflight_checklist"]
    attempt_history = parsed["execution_attempt_history"]
    dashboard_summary = parsed["execution_readiness_dashboard_summary"]
    gate_stack = parsed["execution_gate_stack_preview"]
    witness_manifest = parsed["witness_manifest_plan"]
    human_approval = parsed["human_approval_package"]
    readiness_bundle = parsed["execution_readiness_bundle"]
    review_bundle = parsed["planning_chain_review_bundle"]
    stage_summary = parsed["stage_summary"]
    action = parsed["top_recommended_next_action"]
    validate_planning_chain_review_bundle(review_bundle, parsed)
    same_bundle = collect_planning_chain_review_bundle(parsed)
    _require(review_bundle["review_bundle_id"] == same_bundle["review_bundle_id"],
             "planning-chain review bundle id must be deterministic inside JSON")
    _require(branch_plan["source_upgrade_id"] == top_upgrade["upgrade_plan_id"],
             "top upgrade must flow into branch plan")
    _require(work_package["branch_plan_id"] == branch_plan["branch_plan_id"],
             "branch plan must flow into work package")
    _require(verification["package_id"] == work_package["package_id"],
             "work package must flow into verification plan")
    _require(patch_plan["upgrade_id"] == top_upgrade["upgrade_plan_id"],
             "top upgrade must flow into verified patch plan")
    _require(patch_plan["branch_plan_id"] == branch_plan["branch_plan_id"],
             "branch plan must flow into verified patch plan")
    _require(patch_plan["work_package_id"] == work_package["package_id"],
             "work package must flow into verified patch plan")
    _require(patch_diff["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "verified patch plan must flow into patch diff")
    _require(quality_gate["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "verified patch plan must flow into quality gate")
    _require(quality_gate["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "verified patch diff must flow into quality gate")
    _require(execution_package["verification_plan_id"] == verification["verification_plan_id"],
             "verification plan must flow into autonomous execution package")
    _require(execution_package["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "verified patch plan must flow into autonomous execution package")
    _require(execution_package["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "verified patch diff must flow into autonomous execution package")
    _require(execution_package["quality_gate_id"] == quality_gate["quality_gate_id"],
             "quality gate must flow into autonomous execution package")
    _require(workspace["execution_package_id"] == execution_package["execution_package_id"],
             "autonomous execution package must flow into workspace plan")
    _require(event_timeline["workspace_id"] == workspace["workspace_id"],
             "workspace plan must flow into event timeline")
    _require(retry_policy["execution_event_timeline_id"] == event_timeline["execution_event_timeline_id"],
             "event timeline must flow into retry policy")
    _require(witness_manifest["expected_execution_package_id"] == execution_package["execution_package_id"],
             "autonomous execution package must flow into witness manifest")
    _require(human_approval["workspace_id"] == workspace["workspace_id"],
             "workspace plan must flow into human approval package")
    _require(readiness_bundle["execution_workspace_plan"]["workspace_id"] == workspace["workspace_id"],
             "workspace plan must flow into readiness bundle")
    _require(readiness_bundle["execution_event_timeline"]["execution_event_timeline_id"] == event_timeline["execution_event_timeline_id"],
             "event timeline must flow into readiness bundle")
    _require(readiness_bundle["retry_policy"]["retry_policy_id"] == retry_policy["retry_policy_id"],
             "retry policy must flow into readiness bundle")
    _require(readiness_bundle["witness_manifest_plan"]["witness_manifest_id"] == witness_manifest["witness_manifest_id"],
             "witness manifest must flow into readiness bundle")
    _require(readiness_bundle["human_approval_package"]["approval_package_id"] == human_approval["approval_package_id"],
             "human approval package must flow into readiness bundle")
    _require(journal_plan["execution_package_id"] == execution_package["execution_package_id"],
             "autonomous execution package must flow into execution journal plan")
    _require(journal_plan["execution_readiness_bundle_id"] == readiness_bundle["execution_readiness_bundle_id"],
             "readiness bundle must flow into execution journal plan")
    _require(readiness_bundle["execution_journal_plan_id"] == journal_plan["execution_journal_id"],
             "readiness bundle must reference execution journal plan")
    same_journal = collect_execution_journal_plan(readiness_bundle)
    _require(journal_plan["execution_journal_id"] == same_journal["execution_journal_id"],
             "execution journal id must be deterministic inside planning-chain JSON")
    _require(evidence_contract["execution_journal_id"] == journal_plan["execution_journal_id"],
             "execution journal must flow into evidence contract")
    _require(evidence_contract["execution_package_id"] == execution_package["execution_package_id"],
             "autonomous execution package must flow into evidence contract")
    _require(readiness_bundle["execution_evidence_contract_id"] == evidence_contract["execution_evidence_contract_id"],
             "readiness bundle must reference evidence contract")
    same_contract = collect_execution_evidence_contract(journal_plan)
    _require(evidence_contract["execution_evidence_contract_id"] == same_contract["execution_evidence_contract_id"],
             "evidence contract id must be deterministic inside planning-chain JSON")
    _require(preflight_checklist["planning_chain_id"] == parsed["planning_chain_id"],
             "preflight checklist must reference planning chain")
    _require(preflight_checklist["execution_package_id"] == execution_package["execution_package_id"],
             "execution package must flow into preflight checklist")
    _require(preflight_checklist["execution_readiness_bundle_id"] == readiness_bundle["execution_readiness_bundle_id"],
             "readiness bundle must flow into preflight checklist")
    _require(preflight_checklist["execution_evidence_contract_id"] == evidence_contract["execution_evidence_contract_id"],
             "evidence contract must flow into preflight checklist")
    same_preflight = collect_execution_preflight_checklist(parsed)
    _require(preflight_checklist["preflight_checklist_id"] == same_preflight["preflight_checklist_id"],
             "preflight checklist id must be deterministic inside planning-chain JSON")
    _require(attempt_history["execution_package_id"] == execution_package["execution_package_id"],
             "execution package must flow into attempt history")
    _require(attempt_history["execution_journal_plan_id"] == journal_plan["execution_journal_id"],
             "execution journal must flow into attempt history")
    _require(attempt_history["retry_policy_id"] == retry_policy["retry_policy_id"],
             "retry policy must flow into attempt history")
    same_attempt_history = collect_execution_attempt_history(journal_plan, retry_policy=retry_policy, execution_package=execution_package)
    _require(attempt_history["attempt_history_id"] == same_attempt_history["attempt_history_id"],
             "attempt history id must be deterministic inside planning-chain JSON")
    _require(dashboard_summary["planning_chain_id"] == parsed["planning_chain_id"],
             "dashboard summary must reference planning chain")
    _require(dashboard_summary["execution_readiness_bundle_id"] == readiness_bundle["execution_readiness_bundle_id"],
             "readiness bundle must flow into dashboard summary")
    same_dashboard = collect_execution_readiness_dashboard_summary(parsed)
    _require(dashboard_summary["dashboard_summary_id"] == same_dashboard["dashboard_summary_id"],
             "dashboard summary id must be deterministic inside planning-chain JSON")
    _require(dashboard_summary["dry_run"] is True and dashboard_summary["write_allowed"] is False,
             "dashboard summary must remain read-only inside planning-chain JSON")
    _require(dashboard_summary["automation_allowed"] is False and dashboard_summary["writes"] == [],
             "dashboard summary must not allow automation or writes inside planning-chain JSON")
    _require(gate_stack["planning_chain_id"] == parsed["planning_chain_id"],
             "gate stack must reference planning chain")
    _require(gate_stack["execution_package_id"] == execution_package["execution_package_id"],
             "execution package must flow into gate stack")
    same_gate_stack = collect_execution_gate_stack_preview(parsed)
    _require(gate_stack["gate_stack_preview_id"] == same_gate_stack["gate_stack_preview_id"],
             "gate stack preview id must be deterministic inside planning-chain JSON")
    _require(dashboard_summary["gate_stack_preview_id"] == gate_stack["gate_stack_preview_id"],
             "dashboard summary must reference gate stack")
    _require(dashboard_summary["gate_count"] == gate_stack["gate_count"],
             "dashboard summary must summarize gate count")
    _require(dashboard_summary["pass_count"] == gate_stack["pass_count"],
             "dashboard summary must summarize gate pass count")
    _require(dashboard_summary["review_count"] == gate_stack["review_count"],
             "dashboard summary must summarize gate review count")
    _require(dashboard_summary["block_count"] == gate_stack["block_count"],
             "dashboard summary must summarize gate block count")
    _require(gate_stack["dry_run"] is True and gate_stack["write_allowed"] is False,
             "gate stack must remain read-only inside planning-chain JSON")
    _require(gate_stack["automation_allowed"] is False and gate_stack["writes"] == [],
             "gate stack must not allow automation or writes inside planning-chain JSON")
    _require(review_bundle["planning_chain_id"] == parsed["planning_chain_id"],
             "review bundle must reference planning_chain_id")
    _require(review_bundle["verification_plan_id"] == verification["verification_plan_id"],
             "review bundle must reference verification plan")
    _require(review_bundle["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "review bundle must reference verified patch plan")
    _require(review_bundle["patch_behavior_quality_gate"]["quality_gate_id"] == quality_gate["quality_gate_id"],
             "review bundle must reference quality gate")
    _require(review_bundle["autonomous_execution_package_id"] == execution_package["execution_package_id"],
             "review bundle must reference autonomous execution package")
    _require(review_bundle["execution_readiness_bundle_id"] == readiness_bundle["execution_readiness_bundle_id"],
             "review bundle must reference readiness bundle")
    _require(review_bundle["execution_evidence_contract_id"] == evidence_contract["execution_evidence_contract_id"],
             "review bundle must reference evidence contract")
    _require(review_bundle["evidence_item_count"] == evidence_contract["evidence_item_count"],
             "review bundle must summarize evidence item count")
    _require(review_bundle["evidence_required_types"] == sorted(item["evidence_type"] for item in evidence_contract["evidence_items"]),
             "review bundle must summarize evidence required types")
    _require(review_bundle["dry_run"] is True and review_bundle["write_allowed"] is False,
             "review bundle must remain read-only inside planning-chain JSON")
    _require(review_bundle["automation_allowed"] is False and review_bundle["writes"] == [],
             "review bundle must not allow automation or writes inside planning-chain JSON")
    _require(stage_summary["verification_plan_id"] == verification["verification_plan_id"],
             "stage summary must reference verification plan")
    _require(stage_summary["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "stage summary must reference verified patch plan")
    _require(stage_summary["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "stage summary must reference verified patch diff")
    _require(stage_summary["quality_gate_id"] == quality_gate["quality_gate_id"],
             "stage summary must reference quality gate")
    _require(stage_summary["execution_package_id"] == execution_package["execution_package_id"],
             "stage summary must reference autonomous execution package")
    _require(stage_summary["execution_stage_count"] == execution_package["stage_count"],
             "stage summary must preserve execution stage count")
    _require(stage_summary["next_stage"] == "human review before any execution",
             "stage summary must point to human review")
    _require(action["upgrade_id"] == top_upgrade["upgrade_plan_id"],
             "next action must reference top upgrade")
    _require(action["branch_plan_id"] == branch_plan["branch_plan_id"],
             "next action must reference branch plan")
    _require(action["package_id"] == work_package["package_id"],
             "next action must reference work package")
    _require(action["verification_plan_id"] == verification["verification_plan_id"],
             "next action must reference verification plan")
    _require(action["verified_patch_plan_id"] == patch_plan["verified_patch_plan_id"],
             "next action must reference verified patch plan")
    _require(action["verified_patch_diff_id"] == patch_diff["verified_patch_diff_id"],
             "next action must reference verified patch diff")
    _require(action["quality_gate_id"] == quality_gate["quality_gate_id"],
             "next action must reference quality gate")
    _require(action["execution_package_id"] == execution_package["execution_package_id"],
             "next action must reference autonomous execution package")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = planning_chain_main(["--write"])
    _require(write_rc != 0, "planning-chain --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "planning-chain --write must print clear error")
    _require(write_out.getvalue() == "", "planning-chain --write must not print normal output")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = planning_chain_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "planning-chain human mode must return 0")
    _require("Growth planning-chain preview" in human,
             "planning-chain human mode must print concise summary title")
    _require("planning_chain_id:" in human,
             "planning-chain human mode must include planning_chain_id")
    _require("verification_plans:" in human,
             "planning-chain human mode must include verification summary")
    _require("quality_gate:" in human,
             "planning-chain human mode must include quality gate summary")
    _require("execution_stages:" in human,
             "planning-chain human mode must include execution stage summary")
    _require("readiness_bundle:" in human,
             "planning-chain human mode must include readiness bundle summary")
    _require("execution_journal:" in human,
             "planning-chain human mode must include execution journal summary")
    _require("evidence_contract:" in human,
             "planning-chain human mode must include evidence contract summary")
    _require("dashboard:" in human and "blockers=" in human and "warnings=" in human and "next=" in human,
             "planning-chain human mode must include dashboard status, blockers, warnings, and next action")
    _require("review_bundle:" in human,
             "planning-chain human mode must include review bundle summary")
    _require(review_bundle["review_bundle_id"] in human,
             "planning-chain human mode must include review bundle id")
    _require(review_bundle["recommended_next_action"] in human,
             "planning-chain human mode must include review bundle recommended next action")
    _require(len(human.splitlines()) <= 16,
             "planning-chain human mode must stay concise")

    print("growth planning-chain CLI OK")


# ---------------------------------------------------------------------------
# 62. Growth execution-readiness CLI preview
# ---------------------------------------------------------------------------

def check_growth_execution_readiness_cli() -> None:
    """execution-readiness exposes only the compact readiness dashboard."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_execution_readiness_dashboard_summary,
        collect_growth_planning_chain_preview,
        execution_readiness_main,
        parse_execution_readiness_dashboard_summary_json,
        validate_execution_readiness_dashboard_summary,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("execution-readiness" in help_out.getvalue(),
             "growth help must include execution-readiness")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = execution_readiness_main(["--json"])
    _require(json_rc == 0, "execution-readiness --json must return 0")
    parsed = parse_execution_readiness_dashboard_summary_json(json_out.getvalue())
    validate_execution_readiness_dashboard_summary(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_execution_readiness_dashboard_summary(chain)
    _require(parsed["dashboard_summary_id"] == expected["dashboard_summary_id"],
             "execution-readiness dashboard_summary_id must be deterministic")
    _require(parsed["planning_chain_id"] == expected["planning_chain_id"],
             "execution-readiness summary must reference planning chain")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "execution-readiness summary must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "execution-readiness summary must not allow automation or writes")
    gate_stack = chain["execution_gate_stack_preview"]
    _require(parsed["gate_stack_preview_id"] == gate_stack["gate_stack_preview_id"],
             "execution-readiness summary must include gate stack id")
    _require(parsed["gate_count"] == gate_stack["gate_count"],
             "execution-readiness summary must include gate count")
    _require(parsed["pass_count"] == gate_stack["pass_count"],
             "execution-readiness summary must include gate pass count")
    _require(parsed["review_count"] == gate_stack["review_count"],
             "execution-readiness summary must include gate review count")
    _require(parsed["block_count"] == gate_stack["block_count"],
             "execution-readiness summary must include gate block count")
    _require(isinstance(parsed["gate_stack_top_blockers"], list),
             "execution-readiness summary must include gate stack top blockers")
    _require(isinstance(parsed["gate_stack_top_warnings"], list),
             "execution-readiness summary must include gate stack top warnings")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "execution_workspace_plan",
        "execution_readiness_bundle",
        "execution_gate_stack_preview",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "execution-readiness --json must output only dashboard summary")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["execution-readiness", "--json"])
    routed = parse_execution_readiness_dashboard_summary_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth execution-readiness --json route must return 0")
    _require(routed["dashboard_summary_id"] == parsed["dashboard_summary_id"],
             "growth execution-readiness route must preserve deterministic summary id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = execution_readiness_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "execution-readiness human mode must return 0")
    for needle in (
        "Growth execution readiness",
        "dashboard_summary_id:",
        "planning_chain_id:",
        "top_upgrade:",
        "quality_gate:",
        "preflight:",
        "blockers:",
        "warnings:",
        "planned_attempts:",
        "gate stack:",
        "next_action:",
    ):
        _require(needle in human, f"execution-readiness human mode must include {needle}")
    _require(len(human.splitlines()) <= 11,
             "execution-readiness human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = execution_readiness_main(["--write"])
    _require(write_rc != 0, "execution-readiness --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "execution-readiness --write must print clear error")
    _require(write_out.getvalue() == "",
             "execution-readiness --write must not print normal output")

    print("growth execution-readiness CLI OK")


# ---------------------------------------------------------------------------
# 62. Growth execution-gates CLI preview
# ---------------------------------------------------------------------------

def check_growth_execution_gates_cli() -> None:
    """execution-gates exposes only the read-only gate stack preview."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_execution_gate_stack_preview,
        collect_growth_planning_chain_preview,
        execution_gates_main,
        parse_execution_gate_stack_preview_json,
        validate_execution_gate_stack_preview,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("execution-gates" in help_out.getvalue(),
             "growth help must include execution-gates")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = execution_gates_main(["--json"])
    _require(json_rc == 0, "execution-gates --json must return 0")
    parsed = parse_execution_gate_stack_preview_json(json_out.getvalue())
    validate_execution_gate_stack_preview(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_execution_gate_stack_preview(chain)
    validate_execution_gate_stack_preview(parsed, chain)
    _require(parsed["gate_stack_preview_id"] == expected["gate_stack_preview_id"],
             "execution-gates gate stack id must be deterministic")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "execution-gates preview must reference planning chain")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "execution-gates preview must reference execution package")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "execution-gates preview must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "execution-gates preview must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "execution_readiness_dashboard_summary",
        "planning_chain_review_bundle",
        "execution_readiness_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "execution-gates --json must output only gate stack preview")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["execution-gates", "--json"])
    routed = parse_execution_gate_stack_preview_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth execution-gates --json route must return 0")
    _require(routed["gate_stack_preview_id"] == parsed["gate_stack_preview_id"],
             "growth execution-gates route must preserve deterministic gate stack id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = execution_gates_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "execution-gates human mode must return 0")
    for needle in (
        "Growth execution gates",
        "gate_stack_preview_id:",
        "planning_chain_id:",
        "execution_package_id:",
        "gate_count:",
        "pass_count:",
        "review_count:",
        "block_count:",
        "top_blocker_count:",
        "top_warning_count:",
        "next_action:",
    ):
        _require(needle in human, f"execution-gates human mode must include {needle}")
    _require(len(human.splitlines()) <= 11,
             "execution-gates human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = execution_gates_main(["--write"])
    _require(write_rc != 0, "execution-gates --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "execution-gates --write must print clear error")
    _require(write_out.getvalue() == "",
             "execution-gates --write must not print normal output")

    print("growth execution-gates CLI OK")


# ---------------------------------------------------------------------------
# 62. Growth execution-approval-checklist CLI preview
# ---------------------------------------------------------------------------

def check_growth_execution_approval_checklist_cli() -> None:
    """execution-approval-checklist exposes only human approval state."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_execution_approval_checklist,
        collect_growth_planning_chain_preview,
        execution_approval_checklist_main,
        parse_execution_approval_checklist_json,
        stable_execution_approval_checklist_json,
        validate_execution_approval_checklist,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("execution-approval-checklist" in help_out.getvalue(),
             "growth help must include execution-approval-checklist")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = execution_approval_checklist_main(["--json"])
    _require(json_rc == 0, "execution-approval-checklist --json must return 0")
    parsed = parse_execution_approval_checklist_json(json_out.getvalue())
    validate_execution_approval_checklist(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_execution_approval_checklist(chain)
    validate_execution_approval_checklist(parsed, chain)
    _require(parsed["approval_checklist_id"] == expected["approval_checklist_id"],
             "execution approval checklist id must be deterministic")
    _require(parsed == parse_execution_approval_checklist_json(stable_execution_approval_checklist_json(parsed)),
             "execution approval checklist JSON must round trip")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "execution approval checklist must reference planning chain")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "execution approval checklist must reference execution package")
    _require(parsed["human_approval_package_id"] == chain["human_approval_package"]["approval_package_id"],
             "execution approval checklist must reference human approval package")
    _require(parsed["gate_stack_preview_id"] == chain["execution_gate_stack_preview"]["gate_stack_preview_id"],
             "execution approval checklist must reference gate stack")
    _require(parsed["required_approvals"] == sorted(chain["human_approval_package"]["required_approvals"]),
             "execution approval checklist must preserve required approvals")
    _require(parsed["approval_status"] in {"pass", "review", "block"},
             "execution approval checklist status must be bounded")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "execution approval checklist must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "execution approval checklist must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "execution_gate_stack_preview",
        "human_approval_package",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "execution-approval-checklist --json must output only approval checklist")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["execution-approval-checklist", "--json"])
    routed = parse_execution_approval_checklist_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth execution-approval-checklist --json route must return 0")
    _require(routed["approval_checklist_id"] == parsed["approval_checklist_id"],
             "growth execution-approval-checklist route must preserve deterministic checklist id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = execution_approval_checklist_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "execution-approval-checklist human mode must return 0")
    for needle in (
        "Growth execution approval checklist",
        "approval_checklist_id:",
        "planning_chain_id:",
        "execution_package_id:",
        "required_approval_count:",
        "blocker_count:",
        "warning_count:",
        "approval_status:",
        "next_action:",
    ):
        _require(needle in human, f"execution-approval-checklist human mode must include {needle}")
    _require(len(human.splitlines()) <= 9,
             "execution-approval-checklist human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = execution_approval_checklist_main(["--write"])
    _require(write_rc != 0, "execution-approval-checklist --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "execution-approval-checklist --write must print clear error")
    _require(write_out.getvalue() == "",
             "execution-approval-checklist --write must not print normal output")

    bad_missing = dict(parsed)
    bad_missing.pop("approval_checklist_id")
    try:
        validate_execution_approval_checklist(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("execution approval checklist must reject missing id")

    bad_writes = dict(parsed)
    bad_writes["writes"] = [".link/execution-approval-checklist.json"]
    try:
        validate_execution_approval_checklist(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("execution approval checklist must reject writes")

    print("growth execution-approval-checklist CLI OK")


# ---------------------------------------------------------------------------
# 62. Growth execution-review CLI preview
# ---------------------------------------------------------------------------

def check_growth_execution_review_cli() -> None:
    """execution-review exposes compact reviewer-facing execution state."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_execution_review,
        collect_growth_planning_chain_preview,
        execution_review_main,
        parse_execution_review_json,
        stable_execution_review_json,
        validate_execution_review,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("execution-review" in help_out.getvalue(),
             "growth help must include execution-review")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = execution_review_main(["--json"])
    _require(json_rc == 0, "execution-review --json must return 0")
    parsed = parse_execution_review_json(json_out.getvalue())
    validate_execution_review(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_execution_review(chain)
    validate_execution_review(parsed, chain)
    _require(parsed["execution_review_id"] == expected["execution_review_id"],
             "execution review id must be deterministic")
    _require(parsed == parse_execution_review_json(stable_execution_review_json(parsed)),
             "execution review JSON must round trip")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "execution review must reference planning chain")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "execution review must reference execution package")
    _require(parsed["dashboard_summary_id"] == chain["execution_readiness_dashboard_summary"]["dashboard_summary_id"],
             "execution review must reference dashboard summary")
    _require(parsed["gate_stack_preview_id"] == chain["execution_gate_stack_preview"]["gate_stack_preview_id"],
             "execution review must reference gate stack")
    _require(parsed["approval_checklist_id"] == expected["approval_checklist_id"],
             "execution review must reference approval checklist")
    _require(parsed["readiness_summary"]["top_upgrade_id"] == chain["top_recommended_next_action"]["upgrade_id"],
             "execution review must summarize top upgrade")
    _require(parsed["gate_summary"]["gate_count"] == chain["execution_gate_stack_preview"]["gate_count"],
             "execution review must summarize gate count")
    _require(parsed["approval_summary"]["required_approval_count"] == len(chain["human_approval_package"]["required_approvals"]),
             "execution review must summarize required approvals")
    _require(parsed["attempt_summary"]["planned_attempt_count"] == chain["execution_attempt_history"]["attempt_count"],
             "execution review must summarize attempts")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "execution review must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "execution review must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "execution_gate_stack_preview",
        "execution_readiness_dashboard_summary",
        "execution_approval_checklist",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "execution-review --json must output only compact review")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["execution-review", "--json"])
    routed = parse_execution_review_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth execution-review --json route must return 0")
    _require(routed["execution_review_id"] == parsed["execution_review_id"],
             "growth execution-review route must preserve deterministic review id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = execution_review_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "execution-review human mode must return 0")
    for needle in (
        "Growth execution review",
        "review_id:",
        "planning_chain_id:",
        "top_upgrade:",
        "readiness_status:",
        "quality_gate:",
        "gate_counts:",
        "approval_status:",
        "required_approval_count:",
        "blocker_count:",
        "warning_count:",
        "planned_attempt_count:",
        "next_action:",
    ):
        _require(needle in human, f"execution-review human mode must include {needle}")
    _require(len(human.splitlines()) <= 13,
             "execution-review human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = execution_review_main(["--write"])
    _require(write_rc != 0, "execution-review --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "execution-review --write must print clear error")
    _require(write_out.getvalue() == "",
             "execution-review --write must not print normal output")

    bad_missing = dict(parsed)
    bad_missing.pop("execution_review_id")
    try:
        validate_execution_review(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("execution review must reject missing id")

    bad_writes = dict(parsed)
    bad_writes["writes"] = [".link/execution-review.json"]
    try:
        validate_execution_review(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("execution review must reject writes")

    print("growth execution-review CLI OK")


# ---------------------------------------------------------------------------
# 62. Workspace creator runtime boundary helper
# ---------------------------------------------------------------------------

def check_workspace_creator_runtime_boundary_helper() -> None:
    """workspace creator boundary stays read-only before runtime creation."""
    from link_modes.growth.link_growth_console import (
        collect_execution_approval_checklist,
        collect_execution_review,
        collect_growth_planning_chain_preview,
        collect_workspace_creator_runtime_boundary,
        parse_workspace_creator_runtime_boundary_json,
        stable_workspace_creator_runtime_boundary_json,
        validate_workspace_creator_runtime_boundary,
    )

    chain = collect_growth_planning_chain_preview()
    boundary = collect_workspace_creator_runtime_boundary(chain, metadata={"suite": "growth"})
    same = collect_workspace_creator_runtime_boundary(chain, metadata={"suite": "growth"})
    _require(boundary["workspace_boundary_id"] == same["workspace_boundary_id"],
             "workspace boundary id must be deterministic")
    decoded = parse_workspace_creator_runtime_boundary_json(stable_workspace_creator_runtime_boundary_json(boundary))
    _require(decoded == boundary, "workspace boundary JSON must round trip")
    validate_workspace_creator_runtime_boundary(boundary, chain)

    review = collect_execution_review(chain)
    approval = collect_execution_approval_checklist(chain)
    _require(boundary["planning_chain_id"] == chain["planning_chain_id"],
             "workspace boundary must reference planning chain")
    _require(boundary["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "workspace boundary must reference execution package")
    _require(boundary["branch_plan_id"] == chain["implementation_branch_plan"]["branch_plan_id"],
             "workspace boundary must reference branch plan")
    _require(boundary["execution_review_id"] == review["execution_review_id"],
             "workspace boundary must reference execution review")
    _require(boundary["gate_stack_preview_id"] == chain["execution_gate_stack_preview"]["gate_stack_preview_id"],
             "workspace boundary must reference gate stack")
    _require(boundary["preflight_checklist_id"] == chain["execution_preflight_checklist"]["preflight_checklist_id"],
             "workspace boundary must reference preflight checklist")
    _require(boundary["approval_checklist_id"] == approval["approval_checklist_id"],
             "workspace boundary must reference approval checklist")
    _require(boundary["attempt_history_id"] == chain["execution_attempt_history"]["attempt_history_id"],
             "workspace boundary must reference attempt history")
    _require(boundary["execution_evidence_contract_id"] == chain["execution_evidence_contract"]["execution_evidence_contract_id"],
             "workspace boundary must reference evidence contract")
    _require(boundary["target_branch_name"] == chain["execution_workspace_plan"]["proposed_branch_name"],
             "workspace boundary must preserve target branch name")
    _require(boundary["cleanup_policy"] == chain["execution_workspace_plan"]["cleanup_policy"],
             "workspace boundary must preserve cleanup policy")
    _require(boundary["rollback_policy"] == chain["execution_workspace_plan"]["rollback_policy"],
             "workspace boundary must preserve rollback policy")
    _require(boundary["required_approvals"] == approval["required_approvals"],
             "workspace boundary must preserve required approvals")
    evidence_types = sorted({item["evidence_type"] for item in chain["execution_evidence_contract"]["evidence_items"]})
    _require(boundary["required_evidence"] == evidence_types,
             "workspace boundary must preserve required evidence types")
    _require(boundary["isolation_rules"], "workspace boundary must include isolation rules")
    _require(boundary["pre_creation_checks"], "workspace boundary must include pre-creation checks")
    for forbidden in (
        "apply patches",
        "create branches",
        "create directories",
        "create git worktrees",
        "execute verification commands",
        "modify runtime state",
        "run subprocesses",
    ):
        _require(forbidden in boundary["forbidden_operations"],
                 f"workspace boundary must forbid {forbidden}")
    _require(not (set(boundary["allowed_operations"]) & set(boundary["forbidden_operations"])),
             "workspace boundary allowed operations must not overlap forbidden operations")
    _require(boundary["boundary_status"] in {"pass", "review", "block"},
             "workspace boundary status must be bounded")
    _require(boundary["blocker_count"] >= 0 and boundary["warning_count"] >= 0,
             "workspace boundary must count blockers and warnings")
    _require(boundary["dry_run"] is True and boundary["write_allowed"] is False,
             "workspace boundary must remain read-only")
    _require(boundary["automation_allowed"] is False and boundary["writes"] == [],
             "workspace boundary must not allow automation or writes")

    bad_missing = dict(boundary)
    bad_missing.pop("workspace_boundary_id")
    try:
        validate_workspace_creator_runtime_boundary(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace boundary must reject missing id")

    bad_overlap = dict(boundary)
    bad_overlap["allowed_operations"] = sorted([*boundary["allowed_operations"], "create directories"])
    try:
        validate_workspace_creator_runtime_boundary(bad_overlap)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace boundary must reject allowed/forbidden overlap")

    bad_status = dict(boundary)
    bad_status["boundary_status"] = "maybe"
    try:
        validate_workspace_creator_runtime_boundary(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace boundary must reject invalid status")

    bad_writes = dict(boundary)
    bad_writes["writes"] = [".link/worktrees/generated"]
    try:
        validate_workspace_creator_runtime_boundary(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace boundary must reject writes")

    bad_link = dict(boundary)
    bad_link["execution_package_id"] = "wrong-package"
    try:
        validate_workspace_creator_runtime_boundary(bad_link, chain)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace boundary must reject ID flow mismatch")

    print("workspace creator runtime boundary helper OK")


# ---------------------------------------------------------------------------
# 62. Growth workspace-boundary CLI preview
# ---------------------------------------------------------------------------

def check_growth_workspace_boundary_cli() -> None:
    """workspace-boundary exposes only the workspace creator boundary."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_growth_planning_chain_preview,
        collect_workspace_creator_runtime_boundary,
        parse_workspace_creator_runtime_boundary_json,
        stable_workspace_creator_runtime_boundary_json,
        validate_workspace_creator_runtime_boundary,
        workspace_boundary_main,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("workspace-boundary" in help_out.getvalue(),
             "growth help must include workspace-boundary")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = workspace_boundary_main(["--json"])
    _require(json_rc == 0, "workspace-boundary --json must return 0")
    parsed = parse_workspace_creator_runtime_boundary_json(json_out.getvalue())
    validate_workspace_creator_runtime_boundary(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_workspace_creator_runtime_boundary(chain)
    validate_workspace_creator_runtime_boundary(parsed, chain)
    _require(parsed["workspace_boundary_id"] == expected["workspace_boundary_id"],
             "workspace-boundary id must be deterministic")
    _require(parsed == parse_workspace_creator_runtime_boundary_json(stable_workspace_creator_runtime_boundary_json(parsed)),
             "workspace-boundary JSON must round trip")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "workspace-boundary must reference planning chain")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "workspace-boundary must reference execution package")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "workspace-boundary must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "workspace-boundary must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "execution_gate_stack_preview",
        "execution_review",
        "execution_preflight_checklist",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "workspace-boundary --json must output only boundary payload")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["workspace-boundary", "--json"])
    routed = parse_workspace_creator_runtime_boundary_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth workspace-boundary --json route must return 0")
    _require(routed["workspace_boundary_id"] == parsed["workspace_boundary_id"],
             "growth workspace-boundary route must preserve deterministic boundary id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = workspace_boundary_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "workspace-boundary human mode must return 0")
    for needle in (
        "Growth workspace boundary",
        "workspace_boundary_id:",
        "planning_chain_id:",
        "execution_package_id:",
        "boundary_status:",
        "blocker_count:",
        "warning_count:",
        "required_approval_count:",
        "required_evidence_count:",
        "next_action:",
    ):
        _require(needle in human, f"workspace-boundary human mode must include {needle}")
    _require(len(human.splitlines()) <= 10,
             "workspace-boundary human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = workspace_boundary_main(["--write"])
    _require(write_rc != 0, "workspace-boundary --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "workspace-boundary --write must print clear error")
    _require(write_out.getvalue() == "",
             "workspace-boundary --write must not print normal output")

    print("growth workspace-boundary CLI OK")


# ---------------------------------------------------------------------------
# 62a. Growth patch-boundary CLI preview
# ---------------------------------------------------------------------------

def check_growth_patch_boundary_cli() -> None:
    """patch-boundary exposes only the patch applier boundary."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_growth_planning_chain_preview,
        collect_patch_boundary_preview_from_chain,
        parse_patch_applier_boundary_json,
        patch_boundary_main,
        stable_patch_applier_boundary_json,
        validate_patch_applier_boundary,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("patch-boundary" in help_out.getvalue(),
             "growth help must include patch-boundary")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = patch_boundary_main(["--json"])
    _require(json_rc == 0, "patch-boundary --json must return 0")
    parsed = parse_patch_applier_boundary_json(json_out.getvalue())
    validate_patch_applier_boundary(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_patch_boundary_preview_from_chain(chain)
    _require(parsed["patch_applier_boundary_id"] == expected["patch_applier_boundary_id"],
             "patch-boundary id must be deterministic")
    _require(parsed == parse_patch_applier_boundary_json(stable_patch_applier_boundary_json(parsed)),
             "patch-boundary JSON must round trip")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "patch-boundary must reference planning chain")
    _require(parsed["verified_patch_plan_id"] == chain["verified_patch_plan"]["verified_patch_plan_id"],
             "patch-boundary must reference verified patch plan")
    _require(parsed["verified_patch_diff_id"] == chain["verified_patch_diff"]["verified_patch_diff_id"],
             "patch-boundary must reference verified patch diff")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "patch-boundary must reference execution package")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "patch-boundary must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "patch-boundary must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "verified_patch_plan",
        "verified_patch_diff",
        "execution_gate_stack_preview",
        "execution_approval_checklist",
        "execution_evidence_contract",
        "workspace_creator_runtime_boundary",
        "workspace_runtime_plan",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "patch-boundary --json must output only boundary payload")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["patch-boundary", "--json"])
    routed = parse_patch_applier_boundary_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth patch-boundary --json route must return 0")
    _require(routed["patch_applier_boundary_id"] == parsed["patch_applier_boundary_id"],
             "growth patch-boundary route must preserve deterministic boundary id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = patch_boundary_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "patch-boundary human mode must return 0")
    for needle in (
        "Growth patch boundary",
        "patch_applier_boundary_id:",
        "planning_chain_id:",
        "verified_patch_plan_id:",
        "verified_patch_diff_id:",
        "execution_package_id:",
        "workspace_boundary_id:",
        "runtime_workspace_plan_id:",
        "allowed_target_file_count:",
        "forbidden_path_count:",
        "max_files_changed:",
        "max_operations:",
        "evidence_requirement_count:",
        "next_action:",
    ):
        _require(needle in human, f"patch-boundary human mode must include {needle}")
    _require(len(human.splitlines()) <= 14,
             "patch-boundary human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = patch_boundary_main(["--write"])
    _require(write_rc != 0, "patch-boundary --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "patch-boundary --write must print clear error")
    _require(write_out.getvalue() == "",
             "patch-boundary --write must not print normal output")

    print("growth patch-boundary CLI OK")


# ---------------------------------------------------------------------------
# 62. Workspace creator runtime plan helper
# ---------------------------------------------------------------------------

def check_workspace_creator_runtime_plan_helper() -> None:
    """workspace creator runtime plan stays disabled and read-only."""
    from link_modes.growth.link_growth_console import (
        collect_execution_approval_checklist,
        collect_execution_review,
        collect_growth_planning_chain_preview,
        collect_workspace_creator_runtime_boundary,
        collect_workspace_creator_runtime_plan,
        parse_workspace_creator_runtime_plan_json,
        stable_workspace_creator_runtime_plan_json,
        validate_workspace_creator_runtime_plan,
    )

    chain = collect_growth_planning_chain_preview()
    boundary = collect_workspace_creator_runtime_boundary(chain)
    review = collect_execution_review(chain)
    approval = collect_execution_approval_checklist(chain)
    gate_stack = chain["execution_gate_stack_preview"]
    preflight = chain["execution_preflight_checklist"]
    plan = collect_workspace_creator_runtime_plan(chain, metadata={"suite": "growth"})
    same = collect_workspace_creator_runtime_plan(chain, metadata={"suite": "growth"})
    _require(plan["runtime_workspace_plan_id"] == same["runtime_workspace_plan_id"],
             "workspace runtime plan id must be deterministic")
    decoded = parse_workspace_creator_runtime_plan_json(stable_workspace_creator_runtime_plan_json(plan))
    _require(decoded == plan, "workspace runtime plan JSON must round trip")
    validate_workspace_creator_runtime_plan(plan, boundary, review, gate_stack, approval, preflight)

    _require(plan["planning_chain_id"] == chain["planning_chain_id"],
             "workspace runtime plan must reference planning chain")
    _require(plan["execution_package_id"] == boundary["execution_package_id"],
             "workspace runtime plan must reference execution package")
    _require(plan["workspace_boundary_id"] == boundary["workspace_boundary_id"],
             "workspace runtime plan must reference boundary")
    _require(plan["execution_review_id"] == review["execution_review_id"],
             "workspace runtime plan must reference execution review")
    _require(plan["gate_stack_preview_id"] == gate_stack["gate_stack_preview_id"],
             "workspace runtime plan must reference gate stack")
    _require(plan["approval_checklist_id"] == approval["approval_checklist_id"],
             "workspace runtime plan must reference approval checklist")
    _require(plan["preflight_checklist_id"] == preflight["preflight_checklist_id"],
             "workspace runtime plan must reference preflight checklist")
    _require(plan["branch_name"] == boundary["target_branch_name"],
             "workspace runtime plan must preserve target branch")
    _require(plan["cleanup_policy"] == boundary["cleanup_policy"],
             "workspace runtime plan must preserve cleanup policy")
    _require(plan["rollback_policy"] == boundary["rollback_policy"],
             "workspace runtime plan must preserve rollback policy")
    _require(plan["approval_requirements"] == boundary["required_approvals"],
             "workspace runtime plan must preserve approval requirements")
    _require(plan["evidence_requirements"] == boundary["required_evidence"],
             "workspace runtime plan must preserve evidence requirements")
    _require(plan["required_evidence"] == boundary["required_evidence"],
             "workspace runtime plan must preserve required evidence")
    _require(plan["gate_requirements"], "workspace runtime plan must include gate requirements")
    _require(plan["clean_tree_requirements"], "workspace runtime plan must include clean tree requirements")
    _require(plan["command_allowlist_requirements"],
             "workspace runtime plan must include command allowlist requirements")
    _require(plan["rollback_triggers"], "workspace runtime plan must include rollback triggers")
    _require(plan["failure_states"], "workspace runtime plan must include failure states")
    _require(plan["expected_outputs"], "workspace runtime plan must include expected outputs")
    _require(plan["workspace_root"] == ".link/worktrees",
             "workspace runtime plan must keep reviewed workspace root policy")
    _require(plan["workspace_type"] == "git_worktree_planned",
             "workspace runtime plan must remain planned only")
    _require(plan["isolation_mode"] == "disabled_until_explicit_human_approval",
             "workspace runtime plan must stay approval gated")
    for forbidden in (
        "apply patches",
        "create branches",
        "create directories",
        "create git worktrees",
        "execute verification commands",
        "modify runtime state",
        "run subprocesses",
    ):
        _require(forbidden in plan["forbidden_runtime_actions"],
                 f"workspace runtime plan must forbid {forbidden}")
    _require(not (set(plan["allowed_runtime_actions"]) & set(plan["forbidden_runtime_actions"])),
             "workspace runtime plan allowed actions must not overlap forbidden actions")
    _require(plan["dry_run"] is True and plan["write_allowed"] is False,
             "workspace runtime plan must remain read-only")
    _require(plan["automation_allowed"] is False and plan["writes"] == [],
             "workspace runtime plan must not allow automation or writes")

    bad_missing = dict(plan)
    bad_missing.pop("runtime_workspace_plan_id")
    try:
        validate_workspace_creator_runtime_plan(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject missing id")

    bad_overlap = dict(plan)
    bad_overlap["allowed_runtime_actions"] = sorted([*plan["allowed_runtime_actions"], "create directories"])
    try:
        validate_workspace_creator_runtime_plan(bad_overlap)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject forbidden action overlap")

    bad_status = dict(plan)
    bad_status["plan_status"] = "enabled"
    try:
        validate_workspace_creator_runtime_plan(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject invalid status")

    bad_rollback = dict(plan)
    bad_rollback["rollback_triggers"] = []
    try:
        validate_workspace_creator_runtime_plan(bad_rollback)
    except TypeError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject missing rollback triggers")

    bad_writes = dict(plan)
    bad_writes["writes"] = [".link/worktrees/generated"]
    try:
        validate_workspace_creator_runtime_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject writes")

    bad_link = dict(plan)
    bad_link["workspace_boundary_id"] = "wrong-boundary"
    try:
        validate_workspace_creator_runtime_plan(bad_link, boundary)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace runtime plan must reject boundary mismatch")

    print("workspace creator runtime plan helper OK")


# ---------------------------------------------------------------------------
# 62. Guarded workspace creator runtime component
# ---------------------------------------------------------------------------

def check_guarded_workspace_creator_runtime_component() -> None:
    """guarded workspace creator writes only an approved temp workspace."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_growth_planning_chain_preview,
        collect_workspace_creator_runtime_plan,
        create_guarded_workspace,
        make_guarded_workspace_request,
        preview_guarded_workspace_creation,
        stable_workspace_creation_receipt_json,
        validate_guarded_workspace_request,
        validate_workspace_creation_receipt,
        workspace_create_main,
    )

    chain = collect_growth_planning_chain_preview()
    plan = collect_workspace_creator_runtime_plan(chain)

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("workspace-create" in help_out.getvalue(),
             "growth help must include workspace-create")

    preview_out = io.StringIO()
    with contextlib.redirect_stdout(preview_out):
        preview_rc = workspace_create_main(["--json"])
    _require(preview_rc == 0, "workspace-create --json preview must return 0")
    preview = json.loads(preview_out.getvalue())
    validate_workspace_creation_receipt(preview)
    _require(preview["status"] == "preview", "workspace-create default must preview only")
    _require("capability_gap_preview" not in preview,
             "workspace-create preview must output only receipt payload")

    denied_out = io.StringIO()
    denied_err = io.StringIO()
    with contextlib.redirect_stdout(denied_out), contextlib.redirect_stderr(denied_err):
        denied_rc = workspace_create_main(["--write", "--json"])
    _require(denied_rc != 0, "workspace-create --write without approval must fail closed")
    _require("approval" in denied_err.getvalue().lower(),
             "workspace-create --write without approval must explain approval requirement")
    _require(denied_out.getvalue() == "",
             "workspace-create denied write must not print a receipt")

    with tempfile.TemporaryDirectory() as temp_root:
        safe_plan = dict(plan)
        safe_plan["plan_status"] = "pass"
        safe_plan["recommended_next_action"] = "test-only approved temp workspace creation"
        request = make_guarded_workspace_request(
            safe_plan,
            approved=True,
            write=True,
            workspace_root=temp_root,
            metadata={"suite": "growth"},
        )
        validate_guarded_workspace_request(request, safe_plan)
        receipt = create_guarded_workspace(request, safe_plan)
        validate_workspace_creation_receipt(receipt, request)
        decoded = json.loads(stable_workspace_creation_receipt_json(receipt))
        _require(decoded == receipt, "workspace creation receipt JSON must round trip")
        workspace_path = Path(receipt["workspace_path"])
        manifest_path = workspace_path / "workspace_manifest.json"
        _require(workspace_path.exists() and workspace_path.is_dir(),
                 "guarded workspace creation must create temp workspace directory")
        _require(manifest_path.exists(), "guarded workspace creation must write manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        _require(manifest == receipt["workspace_manifest"],
                 "workspace manifest must match receipt")
        _require(receipt["workspace_id"] == manifest["workspace_id"],
                 "workspace receipt must preserve workspace id")
        _require(receipt["workspace_boundary_id"] == safe_plan["workspace_boundary_id"],
                 "workspace receipt must preserve boundary id")
        _require(receipt["status"] == "created", "guarded workspace creation must return created receipt")
        _require("modify repository files" in receipt["forbidden_actions_avoided"],
                 "workspace receipt must record repository mutation avoidance")
        _require(not (ROOT / ".link/worktrees" / safe_plan["workspace_name"]).exists(),
                 "guarded workspace test must not create repo runtime workspace")

    with tempfile.TemporaryDirectory() as temp_root:
        safe_plan = dict(plan)
        safe_plan["plan_status"] = "pass"
        safe_plan["recommended_next_action"] = "test-only approved temp workspace creation"
        request = make_guarded_workspace_request(safe_plan, approved=True, write=True, workspace_root=temp_root)
        bad_request = dict(request)
        bad_request["workspace_name"] = "../escape"
        try:
            validate_guarded_workspace_request(bad_request, safe_plan)
        except ValueError:
            pass
        else:
            raise AssertionError("guarded workspace request must reject escaping workspace name")

        preview_request = make_guarded_workspace_request(safe_plan, approved=False, write=False, workspace_root=temp_root)
        preview_receipt = preview_guarded_workspace_creation(preview_request, safe_plan)
        validate_workspace_creation_receipt(preview_receipt, preview_request)
        _require(preview_receipt["status"] == "preview", "preview helper must return preview receipt")
        _require(not Path(preview_receipt["workspace_path"]).exists(),
                 "preview helper must not create workspace directory")

        try:
            make_guarded_workspace_request(safe_plan, approved=False, write=True, workspace_root=temp_root)
        except PermissionError:
            pass
        else:
            raise AssertionError("guarded workspace request must require approval for writes")

    print("guarded workspace creator runtime component OK")


# ---------------------------------------------------------------------------
# 62b. Guarded patch applier runtime component
# ---------------------------------------------------------------------------

def check_guarded_patch_applier_runtime_component() -> None:
    """guarded patch applier writes only inside an approved temp workspace."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        apply_guarded_patch,
        collect_execution_approval_checklist,
        collect_growth_planning_chain_preview,
        collect_patch_applier_boundary,
        collect_workspace_creator_runtime_boundary,
        collect_workspace_creator_runtime_plan,
        create_guarded_workspace,
        make_execution_approval_checklist_id,
        make_execution_gate_stack_preview_id,
        make_guarded_patch_request,
        make_guarded_workspace_request,
        patch_apply_main,
        preview_guarded_patch_application,
        validate_guarded_patch_receipt,
        validate_guarded_patch_request,
    )

    def pass_gate_stack(gate_stack: dict[str, Any]) -> dict[str, Any]:
        passed = dict(gate_stack)
        gates = []
        for gate in gate_stack["gates"]:
            clean_gate = dict(gate)
            clean_gate["blockers"] = []
            clean_gate["warnings"] = []
            clean_gate["pass_status"] = "pass"
            clean_gate["recommended_next_action"] = "test-only approval for guarded workspace patching"
            gates.append(clean_gate)
        passed["gates"] = gates
        passed["pass_count"] = len(gates)
        passed["review_count"] = 0
        passed["block_count"] = 0
        passed["gate_stack_preview_id"] = make_execution_gate_stack_preview_id(
            passed["planning_chain_id"],
            passed["execution_package_id"],
            gates,
        )
        return passed

    def pass_approval(checklist: dict[str, Any], gate_stack: dict[str, Any]) -> dict[str, Any]:
        passed = dict(checklist)
        passed["gate_stack_preview_id"] = gate_stack["gate_stack_preview_id"]
        passed["approval_blockers"] = []
        passed["approval_warnings"] = []
        passed["approval_status"] = "pass"
        passed["recommended_next_action"] = "test-only explicit approval supplied"
        passed["approval_checklist_id"] = make_execution_approval_checklist_id(
            passed["planning_chain_id"],
            passed["execution_package_id"],
            passed["human_approval_package_id"],
            passed["gate_stack_preview_id"],
            passed["required_approvals"],
            passed["approval_blockers"],
            passed["approval_warnings"],
        )
        return passed

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("patch-apply" in help_out.getvalue(), "growth help must include patch-apply")

    preview_out = io.StringIO()
    with contextlib.redirect_stdout(preview_out):
        preview_rc = patch_apply_main(["--json"])
    _require(preview_rc == 0, "patch-apply --json preview must return 0")
    preview = json.loads(preview_out.getvalue())
    validate_guarded_patch_receipt(preview)
    _require(preview["status"] == "preview", "patch-apply default must preview only")
    _require(preview["safety_metadata"]["writes"] == [], "patch-apply preview must not write")

    denied_out = io.StringIO()
    denied_err = io.StringIO()
    with contextlib.redirect_stdout(denied_out), contextlib.redirect_stderr(denied_err):
        denied_rc = patch_apply_main(["--write", "--json"])
    _require(denied_rc != 0, "patch-apply --write without approval/workspace must fail closed")
    _require("approval" in denied_err.getvalue().lower(), "patch-apply denied write must explain approval requirement")
    _require(denied_out.getvalue() == "", "patch-apply denied write must not print receipt")

    chain = collect_growth_planning_chain_preview()
    patch_plan = chain["verified_patch_plan"]
    patch_diff = chain["verified_patch_diff"]
    gate_stack = pass_gate_stack(chain["execution_gate_stack_preview"])
    approval = pass_approval(collect_execution_approval_checklist(chain), gate_stack)
    evidence_contract = chain["execution_evidence_contract"]
    workspace_boundary = collect_workspace_creator_runtime_boundary(chain)
    workspace_runtime_plan = collect_workspace_creator_runtime_plan(chain)
    boundary = collect_patch_applier_boundary(
        patch_plan,
        patch_diff,
        gate_stack,
        approval,
        evidence_contract,
        workspace_boundary,
        workspace_runtime_plan,
        planning_chain_id=chain["planning_chain_id"],
    )

    repo_file = ROOT / patch_plan["target_files"][0]
    repo_before = repo_file.read_bytes() if repo_file.exists() else b""
    with tempfile.TemporaryDirectory() as temp_root:
        safe_plan = dict(workspace_runtime_plan)
        safe_plan["plan_status"] = "pass"
        safe_plan["recommended_next_action"] = "test-only approved temp workspace creation"
        workspace_request = make_guarded_workspace_request(
            safe_plan,
            approved=True,
            write=True,
            workspace_root=temp_root,
        )
        workspace_receipt = create_guarded_workspace(workspace_request, safe_plan)
        workspace_path = Path(workspace_receipt["workspace_path"])
        first_target = workspace_path / patch_plan["target_files"][0]
        first_target.parent.mkdir(parents=True, exist_ok=True)
        first_target.write_text("original workspace content\n", encoding="utf-8")

        request = make_guarded_patch_request(boundary, workspace_receipt, approved=True, write=True)
        validate_guarded_patch_request(request, boundary, workspace_receipt)
        receipt = apply_guarded_patch(
            request,
            boundary,
            patch_plan,
            patch_diff,
            workspace_receipt,
            workspace_receipt["workspace_manifest"],
            approval,
            gate_stack,
            evidence_contract,
        )
        validate_guarded_patch_receipt(receipt, request, boundary, patch_plan, patch_diff, workspace_receipt)
        _require(receipt["status"] == "applied", "guarded patch write must return applied receipt")
        _require(receipt["applied_operations"], "guarded patch write must record applied operations")
        _require(receipt["changed_files"], "guarded patch write must record changed files")
        _require(receipt["before_file_hashes"], "guarded patch write must record before hashes")
        _require(receipt["after_file_hashes"], "guarded patch write must record after hashes")
        _require(receipt["safety_metadata"]["dry_run"] is False, "guarded patch applied receipt must not be dry run")
        _require(receipt["safety_metadata"]["write_allowed"] is True, "guarded patch applied receipt must record write allowance")
        _require(receipt["safety_metadata"]["automation_allowed"] is False, "guarded patch must keep automation disabled")
        _require(receipt["safety_metadata"]["writes"] == receipt["changed_files"], "guarded patch writes must match changed files")
        _require((workspace_path / "guarded_patch_receipt.json").exists(), "guarded patch write must create workspace-local receipt")
        _require(b"Link guarded patch operation" in first_target.read_bytes(), "guarded patch must update workspace-local target")
        _require(repo_file.read_bytes() == repo_before if repo_file.exists() else repo_before == b"", "guarded patch must not modify repo target file")

        preview_request = make_guarded_patch_request(boundary, workspace_receipt, approved=False, write=False)
        preview_receipt = preview_guarded_patch_application(
            preview_request,
            boundary,
            patch_plan,
            patch_diff,
            workspace_receipt,
            workspace_receipt["workspace_manifest"],
            approval,
            gate_stack,
            evidence_contract,
        )
        validate_guarded_patch_receipt(preview_receipt, preview_request, boundary, patch_plan, patch_diff, workspace_receipt)
        _require(preview_receipt["status"] == "preview", "guarded patch preview helper must stay preview")
        _require(preview_receipt["applied_operations"] == [], "guarded patch preview must not apply operations")

        bad_boundary = dict(boundary)
        bad_boundary["allowed_target_files"] = [".agents/unsafe.json"]
        try:
            make_guarded_patch_request(bad_boundary, workspace_receipt, approved=True, write=True)
        except ValueError:
            pass
        else:
            raise AssertionError("guarded patch request must reject invalid boundary")

        bad_plan = dict(patch_plan)
        bad_operations = [dict(operation) for operation in patch_plan["patch_operations"]]
        bad_operations[0]["operation_type"] = "create_file"
        bad_plan["patch_operations"] = bad_operations
        bad_boundary = collect_patch_applier_boundary(
            bad_plan,
            patch_diff,
            gate_stack,
            approval,
            evidence_contract,
            workspace_boundary,
            workspace_runtime_plan,
            planning_chain_id=chain["planning_chain_id"],
        )
        before_failure = first_target.read_text(encoding="utf-8")
        bad_request = make_guarded_patch_request(bad_boundary, workspace_receipt, approved=True, write=True)
        try:
            apply_guarded_patch(
                bad_request,
                bad_boundary,
                bad_plan,
                patch_diff,
                workspace_receipt,
                workspace_receipt["workspace_manifest"],
                approval,
                gate_stack,
                evidence_contract,
            )
        except FileExistsError:
            pass
        else:
            raise AssertionError("guarded patch must fail closed on invalid create operation")
        _require(first_target.read_text(encoding="utf-8") == before_failure,
                 "guarded patch failure must restore workspace file content")

    _require(repo_file.read_bytes() == repo_before if repo_file.exists() else repo_before == b"", "guarded patch tests must leave repo file unchanged")
    print("guarded patch applier runtime component OK")


# ---------------------------------------------------------------------------
# 62c. Verification runner boundary helper
# ---------------------------------------------------------------------------

def check_verification_runner_boundary_helper() -> None:
    """verification runner boundary stays read-only before command execution exists."""
    from link_modes.growth.link_growth_console import (
        collect_execution_approval_checklist,
        collect_execution_review,
        collect_growth_planning_chain_preview,
        collect_patch_boundary_preview_from_chain,
        collect_verification_runner_boundary,
        collect_workspace_creator_runtime_plan,
        make_guarded_patch_request,
        make_guarded_workspace_request,
        parse_verification_runner_boundary_json,
        preview_guarded_patch_application,
        preview_guarded_workspace_creation,
        stable_verification_runner_boundary_json,
        validate_verification_runner_boundary,
    )

    chain = collect_growth_planning_chain_preview()
    patch_boundary = collect_patch_boundary_preview_from_chain(chain)
    workspace_plan = collect_workspace_creator_runtime_plan(chain)
    workspace_request = make_guarded_workspace_request(
        workspace_plan,
        approved=False,
        write=False,
        workspace_root="/tmp/link-verification-boundary-test",
    )
    workspace_receipt = preview_guarded_workspace_creation(workspace_request, workspace_plan)
    patch_request = make_guarded_patch_request(patch_boundary, workspace_receipt, approved=False, write=False)
    approval = collect_execution_approval_checklist(chain)
    execution_review = collect_execution_review(chain)
    patch_receipt = preview_guarded_patch_application(
        patch_request,
        patch_boundary,
        chain["verified_patch_plan"],
        chain["verified_patch_diff"],
        workspace_receipt,
        workspace_receipt["workspace_manifest"],
        approval,
        chain["execution_gate_stack_preview"],
        chain["execution_evidence_contract"],
    )
    boundary = collect_verification_runner_boundary(
        patch_receipt,
        patch_boundary,
        chain["execution_evidence_contract"],
        chain["execution_retry_policy"],
        chain["execution_gate_stack_preview"],
        approval,
        chain["execution_preflight_checklist"],
        execution_review,
        metadata={"suite": "growth"},
    )
    same = collect_verification_runner_boundary(
        patch_receipt,
        patch_boundary,
        chain["execution_evidence_contract"],
        chain["execution_retry_policy"],
        chain["execution_gate_stack_preview"],
        approval,
        chain["execution_preflight_checklist"],
        execution_review,
        metadata={"suite": "growth"},
    )
    _require(boundary["verification_runner_boundary_id"] == same["verification_runner_boundary_id"],
             "verification runner boundary id must be deterministic")
    decoded = parse_verification_runner_boundary_json(stable_verification_runner_boundary_json(boundary))
    _require(decoded == boundary, "verification runner boundary JSON must round trip")
    validate_verification_runner_boundary(
        boundary,
        patch_receipt,
        patch_boundary,
        chain["execution_evidence_contract"],
        chain["execution_retry_policy"],
        chain["execution_gate_stack_preview"],
        approval,
        chain["execution_preflight_checklist"],
        execution_review,
    )
    _require(boundary["planning_chain_id"] == chain["planning_chain_id"],
             "verification runner boundary must reference planning chain")
    _require(boundary["patch_applier_boundary_id"] == patch_boundary["patch_applier_boundary_id"],
             "verification runner boundary must reference patch boundary")
    _require(boundary["guarded_patch_receipt_id"] == patch_receipt["guarded_patch_receipt_id"],
             "verification runner boundary must reference patch receipt")
    _require(set(["compile", "tests", "healthcheck"]).issubset(boundary["required_verification_actions"]),
             "verification runner boundary must require compile/tests/healthcheck")
    _require(boundary["allowed_command_families"] == ["python3"],
             "verification runner boundary must allow only python3 command family initially")
    _require("git" in boundary["forbidden_command_families"],
             "verification runner boundary must forbid git command family")
    _require(boundary["max_command_count"] >= 3,
             "verification runner boundary command cap must cover required stages")
    _require(boundary["per_command_timeout_seconds"] <= boundary["max_runtime_seconds"],
             "verification runner boundary timeout must fit max runtime")
    _require(boundary["max_attempts"] == chain["execution_retry_policy"]["max_attempts"],
             "verification runner boundary must preserve retry policy max attempts")
    _require(boundary["required_command_evidence"] and boundary["required_exit_code_evidence"],
             "verification runner boundary must require command and exit code evidence")
    _require(boundary["required_stdout_log_evidence"] and boundary["required_stderr_log_evidence"],
             "verification runner boundary must require stdout/stderr evidence")
    _require(boundary["required_file_hash_evidence"] and boundary["required_diff_hash_evidence"],
             "verification runner boundary must require file hash and diff hash evidence")
    _require(boundary["required_journal_evidence"],
             "verification runner boundary must require journal evidence")
    _require(boundary["dry_run"] is True and boundary["write_allowed"] is False,
             "verification runner boundary must remain read-only")
    _require(boundary["automation_allowed"] is False and boundary["writes"] == [],
             "verification runner boundary must not allow automation or writes")

    bad_missing = dict(boundary)
    bad_missing.pop("verification_runner_boundary_id")
    try:
        validate_verification_runner_boundary(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject missing id")

    bad_family = dict(boundary)
    bad_family["allowed_command_families"] = ["git", "python3"]
    try:
        validate_verification_runner_boundary(bad_family)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject forbidden allowed command family")

    bad_forbidden = dict(boundary)
    bad_forbidden["forbidden_command_families"] = [item for item in bad_forbidden["forbidden_command_families"] if item != "git"]
    try:
        validate_verification_runner_boundary(bad_forbidden)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must require forbidden git command family")

    bad_pattern = dict(boundary)
    bad_pattern["allowed_command_patterns"] = ["git status"]
    try:
        validate_verification_runner_boundary(bad_pattern)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject non-python allowed command pattern")

    bad_timeout = dict(boundary)
    bad_timeout["per_command_timeout_seconds"] = bad_timeout["max_runtime_seconds"] + 1
    try:
        validate_verification_runner_boundary(bad_timeout)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject invalid timeout")

    bad_retry = dict(boundary)
    bad_retry["max_attempts"] = 0
    try:
        validate_verification_runner_boundary(bad_retry)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject invalid retry max")

    bad_rollback = dict(boundary)
    bad_rollback["rollback_triggers"] = [item for item in bad_rollback["rollback_triggers"] if not item.startswith("compile command")]
    try:
        validate_verification_runner_boundary(bad_rollback)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must require rollback triggers")

    bad_evidence = dict(boundary)
    bad_evidence["required_command_evidence"] = []
    try:
        validate_verification_runner_boundary(bad_evidence)
    except TypeError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject missing command evidence")

    bad_writes = dict(boundary)
    bad_writes["writes"] = ["tmp.txt"]
    try:
        validate_verification_runner_boundary(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("verification runner boundary must reject writes")

    print("verification runner boundary helper OK")


# ---------------------------------------------------------------------------
# 62d. Growth verification-boundary CLI preview
# ---------------------------------------------------------------------------

def check_growth_verification_boundary_cli() -> None:
    """verification-boundary exposes only the verification runner boundary."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        collect_growth_planning_chain_preview,
        collect_verification_boundary_preview_from_chain,
        parse_verification_runner_boundary_json,
        stable_verification_runner_boundary_json,
        validate_verification_runner_boundary,
        verification_boundary_main,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("verification-boundary" in help_out.getvalue(),
             "growth help must include verification-boundary")

    json_out = io.StringIO()
    with contextlib.redirect_stdout(json_out):
        json_rc = verification_boundary_main(["--json"])
    _require(json_rc == 0, "verification-boundary --json must return 0")
    parsed = parse_verification_runner_boundary_json(json_out.getvalue())
    validate_verification_runner_boundary(parsed)
    chain = collect_growth_planning_chain_preview()
    expected = collect_verification_boundary_preview_from_chain(chain)
    _require(parsed["verification_runner_boundary_id"] == expected["verification_runner_boundary_id"],
             "verification-boundary id must be deterministic")
    _require(parsed == parse_verification_runner_boundary_json(stable_verification_runner_boundary_json(parsed)),
             "verification-boundary JSON must round trip")
    _require(parsed["planning_chain_id"] == chain["planning_chain_id"],
             "verification-boundary must reference planning chain")
    _require(parsed["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "verification-boundary must reference execution package")
    _require(parsed["dry_run"] is True and parsed["write_allowed"] is False,
             "verification-boundary must remain read-only")
    _require(parsed["automation_allowed"] is False and parsed["writes"] == [],
             "verification-boundary must not allow automation or writes")
    for full_chain_key in (
        "capability_gap_preview",
        "upgrade_execution_plan",
        "verified_patch_plan",
        "verified_patch_diff",
        "execution_gate_stack_preview",
        "execution_approval_checklist",
        "execution_evidence_contract",
        "execution_retry_policy",
        "execution_review",
        "patch_applier_boundary",
        "guarded_patch_receipt",
        "planning_chain_review_bundle",
    ):
        _require(full_chain_key not in parsed,
                 "verification-boundary --json must output only boundary payload")

    routed_out = io.StringIO()
    with contextlib.redirect_stdout(routed_out):
        routed_rc = _cmd_growth(["verification-boundary", "--json"])
    routed = parse_verification_runner_boundary_json(routed_out.getvalue())
    _require(routed_rc == 0, "growth verification-boundary --json route must return 0")
    _require(routed["verification_runner_boundary_id"] == parsed["verification_runner_boundary_id"],
             "growth verification-boundary route must preserve deterministic boundary id")

    human_out = io.StringIO()
    with contextlib.redirect_stdout(human_out):
        human_rc = verification_boundary_main([])
    human = human_out.getvalue()
    _require(human_rc == 0, "verification-boundary human mode must return 0")
    for needle in (
        "Growth verification boundary",
        "verification_runner_boundary_id:",
        "planning_chain_id:",
        "execution_package_id:",
        "patch_applier_boundary_id:",
        "guarded_patch_receipt_id:",
        "workspace_id:",
        "required_verification_stage_count:",
        "allowed_command_family_count:",
        "forbidden_command_family_count:",
        "max_command_count:",
        "max_runtime_seconds:",
        "max_attempts:",
        "evidence_requirement_count:",
        "rollback_trigger_count:",
        "next_action:",
    ):
        _require(needle in human, f"verification-boundary human mode must include {needle}")
    _require(len(human.splitlines()) <= 16,
             "verification-boundary human mode must stay concise")

    write_out = io.StringIO()
    write_err = io.StringIO()
    with contextlib.redirect_stdout(write_out), contextlib.redirect_stderr(write_err):
        write_rc = verification_boundary_main(["--write"])
    _require(write_rc != 0, "verification-boundary --write must be rejected")
    _require("--write is not supported" in write_err.getvalue(),
             "verification-boundary --write must print clear error")
    _require(write_out.getvalue() == "",
             "verification-boundary --write must not print normal output")

    print("growth verification-boundary CLI OK")


# ---------------------------------------------------------------------------
# 62e. Guarded verification runner runtime component
# ---------------------------------------------------------------------------

def check_guarded_verification_runner_runtime_component() -> None:
    """guarded verification runs only allowlisted Python commands in temp workspaces."""
    from link_modes.growth.link_growth_console import (
        apply_guarded_patch,
        collect_execution_approval_checklist,
        collect_execution_review,
        collect_growth_planning_chain_preview,
        collect_patch_applier_boundary,
        collect_verification_runner_boundary,
        collect_workspace_creator_runtime_boundary,
        collect_workspace_creator_runtime_plan,
        create_guarded_workspace,
        make_execution_approval_checklist_id,
        make_execution_gate_stack_preview_id,
        make_guarded_patch_request,
        make_guarded_verification_request,
        make_guarded_workspace_request,
        run_guarded_verification,
        validate_guarded_verification_receipt,
        validate_guarded_verification_request,
    )

    def pass_gate_stack(gate_stack: dict[str, Any]) -> dict[str, Any]:
        passed = dict(gate_stack)
        gates = []
        for gate in gate_stack["gates"]:
            clean_gate = dict(gate)
            clean_gate["blockers"] = []
            clean_gate["warnings"] = []
            clean_gate["pass_status"] = "pass"
            clean_gate["recommended_next_action"] = "test-only approval for guarded verification"
            gates.append(clean_gate)
        passed["gates"] = gates
        passed["pass_count"] = len(gates)
        passed["review_count"] = 0
        passed["block_count"] = 0
        passed["gate_stack_preview_id"] = make_execution_gate_stack_preview_id(
            passed["planning_chain_id"],
            passed["execution_package_id"],
            gates,
        )
        return passed

    def pass_approval(checklist: dict[str, Any], gate_stack: dict[str, Any]) -> dict[str, Any]:
        passed = dict(checklist)
        passed["gate_stack_preview_id"] = gate_stack["gate_stack_preview_id"]
        passed["approval_blockers"] = []
        passed["approval_warnings"] = []
        passed["approval_status"] = "pass"
        passed["recommended_next_action"] = "test-only explicit approval supplied"
        passed["approval_checklist_id"] = make_execution_approval_checklist_id(
            passed["planning_chain_id"],
            passed["execution_package_id"],
            passed["human_approval_package_id"],
            passed["gate_stack_preview_id"],
            passed["required_approvals"],
            passed["approval_blockers"],
            passed["approval_warnings"],
        )
        return passed

    chain = collect_growth_planning_chain_preview()
    patch_plan = chain["verified_patch_plan"]
    patch_diff = chain["verified_patch_diff"]
    gate_stack = pass_gate_stack(chain["execution_gate_stack_preview"])
    approval = pass_approval(collect_execution_approval_checklist(chain), gate_stack)
    evidence_contract = chain["execution_evidence_contract"]
    retry_policy = chain["execution_retry_policy"]
    workspace_boundary = collect_workspace_creator_runtime_boundary(chain)
    workspace_runtime_plan = collect_workspace_creator_runtime_plan(chain)
    patch_boundary = collect_patch_applier_boundary(
        patch_plan,
        patch_diff,
        gate_stack,
        approval,
        evidence_contract,
        workspace_boundary,
        workspace_runtime_plan,
        planning_chain_id=chain["planning_chain_id"],
    )

    repo_file = ROOT / patch_plan["target_files"][0]
    repo_before = repo_file.read_bytes() if repo_file.exists() else b""
    with tempfile.TemporaryDirectory() as temp_root:
        safe_plan = dict(workspace_runtime_plan)
        safe_plan["plan_status"] = "pass"
        safe_plan["recommended_next_action"] = "test-only approved temp workspace creation"
        workspace_request = make_guarded_workspace_request(
            safe_plan,
            approved=True,
            write=True,
            workspace_root=temp_root,
        )
        workspace_receipt = create_guarded_workspace(workspace_request, safe_plan)
        workspace_path = Path(workspace_receipt["workspace_path"])
        first_target = workspace_path / patch_plan["target_files"][0]
        first_target.parent.mkdir(parents=True, exist_ok=True)
        first_target.write_text("original workspace content\n", encoding="utf-8")

        patch_request = make_guarded_patch_request(patch_boundary, workspace_receipt, approved=True, write=True)
        patch_receipt = apply_guarded_patch(
            patch_request,
            patch_boundary,
            patch_plan,
            patch_diff,
            workspace_receipt,
            workspace_receipt["workspace_manifest"],
            approval,
            gate_stack,
            evidence_contract,
        )
        execution_review = collect_execution_review(chain)
        verification_boundary = collect_verification_runner_boundary(
            patch_receipt,
            patch_boundary,
            evidence_contract,
            retry_policy,
            gate_stack,
            approval,
            chain["execution_preflight_checklist"],
            execution_review,
        )

        command = "python3 -c \"print('guarded verification ok')\""
        request = make_guarded_verification_request(
            verification_boundary,
            commands=[command],
            approved=True,
            write=True,
        )
        validate_guarded_verification_request(request, verification_boundary)
        receipt = run_guarded_verification(
            request,
            verification_boundary,
            patch_receipt,
            workspace_receipt["workspace_manifest"],
            workspace_receipt,
            evidence_contract,
            retry_policy,
        )
        validate_guarded_verification_receipt(
            receipt,
            request,
            verification_boundary,
            patch_receipt,
            workspace_receipt,
            evidence_contract,
            retry_policy,
        )
        _require(receipt["verification_result"] == "passed",
                 "allowlisted python verification command must pass")
        _require(receipt["exit_codes"] == [0], "verification receipt must capture exit code")
        _require(receipt["executed_commands"][0]["command"] == command,
                 "verification receipt must preserve executed command")
        _require(receipt["retry_count"] == 0, "successful verification must not retry")
        _require(receipt["rollback_triggered"] is False,
                 "successful verification must not trigger rollback")
        _require(receipt["safety_metadata"]["dry_run"] is False,
                 "verification write receipt must not be dry run")
        _require(receipt["safety_metadata"]["write_allowed"] is True,
                 "verification write receipt must record workspace-local write allowance")
        _require(receipt["safety_metadata"]["automation_allowed"] is False,
                 "guarded verification must keep automation disabled")
        _require("guarded_verification_receipt.json" in receipt["safety_metadata"]["writes"],
                 "verification receipt writes must include workspace-local receipt")
        stdout_path = workspace_path / receipt["stdout_refs"][0]
        stderr_path = workspace_path / receipt["stderr_refs"][0]
        evidence_path = workspace_path / receipt["evidence_refs"][0]
        _require(stdout_path.exists(), "verification must write workspace-local stdout log")
        _require(stderr_path.exists(), "verification must write workspace-local stderr log")
        _require(evidence_path.exists(), "verification must write workspace-local evidence")
        _require("guarded verification ok" in stdout_path.read_text(encoding="utf-8"),
                 "verification stdout log must capture command output")
        _require((workspace_path / "guarded_verification_receipt.json").exists(),
                 "verification must write workspace-local receipt")

        bad_no_write = make_guarded_verification_request(
            verification_boundary,
            commands=[command],
            approved=False,
            write=False,
        )
        try:
            run_guarded_verification(
                bad_no_write,
                verification_boundary,
                patch_receipt,
                workspace_receipt["workspace_manifest"],
                workspace_receipt,
                evidence_contract,
                retry_policy,
            )
        except PermissionError:
            pass
        else:
            raise AssertionError("guarded verification runtime must require --write")

        for forbidden in ("git status", "bash -lc echo no", "python3 -m pip install nope", "python3 -c \"import urllib.request\""):
            try:
                make_guarded_verification_request(
                    verification_boundary,
                    commands=[forbidden],
                    approved=True,
                    write=True,
                )
            except ValueError:
                pass
            else:
                raise AssertionError(f"guarded verification must reject forbidden command: {forbidden}")

        bad_request = dict(request)
        bad_request["workspace_path"] = str(ROOT)
        try:
            validate_guarded_verification_request(bad_request)
        except ValueError:
            pass
        else:
            raise AssertionError("guarded verification request must reject repo workspace path")

        bad_boundary = dict(verification_boundary)
        bad_boundary["verification_runner_boundary_id"] = "wrong-boundary"
        try:
            validate_guarded_verification_request(request, bad_boundary)
        except ValueError:
            pass
        else:
            raise AssertionError("guarded verification request must reject boundary mismatch")

        fail_command = "python3 -c \"raise SystemExit(2)\""
        fail_request = make_guarded_verification_request(
            verification_boundary,
            commands=[fail_command],
            approved=True,
            write=True,
        )
        fail_receipt = run_guarded_verification(
            fail_request,
            verification_boundary,
            patch_receipt,
            workspace_receipt["workspace_manifest"],
            workspace_receipt,
            evidence_contract,
            retry_policy,
        )
        validate_guarded_verification_receipt(
            fail_receipt,
            fail_request,
            verification_boundary,
            patch_receipt,
            workspace_receipt,
            evidence_contract,
            retry_policy,
        )
        _require(fail_receipt["verification_result"] == "failed",
                 "failing verification command must produce failed receipt")
        _require(fail_receipt["exit_codes"] == [2],
                 "failing verification receipt must capture nonzero exit code")
        _require(fail_receipt["rollback_triggered"] is True,
                 "failing verification must trigger rollback flag")

    _require(repo_file.read_bytes() == repo_before if repo_file.exists() else repo_before == b"",
             "guarded verification tests must leave repo file unchanged")
    print("guarded verification runner runtime component OK")


# ---------------------------------------------------------------------------
# 62. Guarded workspace cleanup / abandon lifecycle
# ---------------------------------------------------------------------------

def check_guarded_workspace_lifecycle_cleanup_abandon() -> None:
    """guarded workspace cleanup and abandon close temp workspaces safely."""
    from link import _cmd_growth
    from link_modes.growth.link_growth_console import (
        abandon_guarded_workspace,
        cleanup_guarded_workspace,
        collect_growth_planning_chain_preview,
        collect_workspace_abandon_plan,
        collect_workspace_abandon_receipt,
        collect_workspace_cleanup_plan,
        collect_workspace_cleanup_receipt,
        collect_workspace_creator_runtime_plan,
        create_guarded_workspace,
        make_guarded_workspace_request,
        parse_workspace_abandon_plan_json,
        parse_workspace_cleanup_plan_json,
        stable_workspace_abandon_plan_json,
        stable_workspace_cleanup_plan_json,
        validate_workspace_abandon_plan,
        validate_workspace_abandon_receipt,
        validate_workspace_cleanup_plan,
        validate_workspace_cleanup_receipt,
        workspace_abandon_main,
        workspace_cleanup_main,
    )

    help_out = io.StringIO()
    with contextlib.redirect_stdout(help_out):
        help_rc = _cmd_growth(["--help"])
    _require(help_rc == 0, "growth --help must return 0")
    _require("workspace-cleanup" in help_out.getvalue(), "growth help must include workspace-cleanup")
    _require("workspace-abandon" in help_out.getvalue(), "growth help must include workspace-abandon")

    cleanup_preview_out = io.StringIO()
    with contextlib.redirect_stdout(cleanup_preview_out):
        cleanup_preview_rc = workspace_cleanup_main(["--json"])
    _require(cleanup_preview_rc == 0, "workspace-cleanup --json preview must return 0")
    cleanup_preview = parse_workspace_cleanup_plan_json(cleanup_preview_out.getvalue())
    _require(cleanup_preview["cleanup_status"] == "preview", "workspace cleanup default must preview")

    abandon_preview_out = io.StringIO()
    with contextlib.redirect_stdout(abandon_preview_out):
        abandon_preview_rc = workspace_abandon_main(["--json"])
    _require(abandon_preview_rc == 0, "workspace-abandon --json preview must return 0")
    abandon_preview = parse_workspace_abandon_plan_json(abandon_preview_out.getvalue())
    _require(abandon_preview["abandonment_status"] == "blocked", "workspace abandon default must preview blockers")

    cleanup_denied = io.StringIO()
    cleanup_err = io.StringIO()
    with contextlib.redirect_stdout(cleanup_denied), contextlib.redirect_stderr(cleanup_err):
        cleanup_denied_rc = workspace_cleanup_main(["--write", "--json"])
    _require(cleanup_denied_rc != 0, "workspace-cleanup --write must require workspace args")
    _require("--workspace-path" in cleanup_err.getvalue(), "workspace-cleanup --write must explain required args")

    chain = collect_growth_planning_chain_preview()
    plan = collect_workspace_creator_runtime_plan(chain)
    safe_plan = dict(plan)
    safe_plan["plan_status"] = "pass"
    safe_plan["recommended_next_action"] = "test-only lifecycle temp workspace"

    with tempfile.TemporaryDirectory() as temp_root:
        request = make_guarded_workspace_request(safe_plan, approved=True, write=True, workspace_root=temp_root)
        creation = create_guarded_workspace(request, safe_plan)
        cleanup_plan = collect_workspace_cleanup_plan(creation, cleanup_reason="successful closure")
        same_cleanup = collect_workspace_cleanup_plan(creation, cleanup_reason="successful closure")
        _require(cleanup_plan["cleanup_plan_id"] == same_cleanup["cleanup_plan_id"],
                 "workspace cleanup plan id must be deterministic")
        _require(parse_workspace_cleanup_plan_json(stable_workspace_cleanup_plan_json(cleanup_plan)) == cleanup_plan,
                 "workspace cleanup plan JSON must round trip")
        validate_workspace_cleanup_plan(cleanup_plan, creation)
        preview_receipt = collect_workspace_cleanup_receipt(cleanup_plan, cleanup_result="preview")
        validate_workspace_cleanup_receipt(preview_receipt, cleanup_plan)
        workspace_path = Path(creation["workspace_path"])
        _require(workspace_path.exists(), "cleanup test workspace must exist before cleanup")
        cleanup_receipt = cleanup_guarded_workspace(cleanup_plan)
        validate_workspace_cleanup_receipt(cleanup_receipt, cleanup_plan)
        _require(cleanup_receipt["cleanup_result"] == "cleaned", "cleanup receipt must report cleaned")
        _require(not workspace_path.exists(), "cleanup must remove guarded temp workspace")
        _require(not (ROOT / ".link/worktrees" / safe_plan["workspace_name"]).exists(),
                 "cleanup test must not touch repo runtime workspace")

    with tempfile.TemporaryDirectory() as temp_root:
        request = make_guarded_workspace_request(safe_plan, approved=True, write=True, workspace_root=temp_root)
        creation = create_guarded_workspace(request, safe_plan)
        abandon_plan = collect_workspace_abandon_plan(
            creation,
            abandonment_reason="blocked execution",
            abandonment_category="blocked",
            blockers=["quality gate blocked"],
        )
        same_abandon = collect_workspace_abandon_plan(
            creation,
            abandonment_reason="blocked execution",
            abandonment_category="blocked",
            blockers=["quality gate blocked"],
        )
        _require(abandon_plan["abandon_plan_id"] == same_abandon["abandon_plan_id"],
                 "workspace abandon plan id must be deterministic")
        _require(parse_workspace_abandon_plan_json(stable_workspace_abandon_plan_json(abandon_plan)) == abandon_plan,
                 "workspace abandon plan JSON must round trip")
        validate_workspace_abandon_plan(abandon_plan, creation)
        preview_abandon_receipt = collect_workspace_abandon_receipt(abandon_plan, abandonment_result="preview")
        validate_workspace_abandon_receipt(preview_abandon_receipt, abandon_plan)
        abandon_receipt = abandon_guarded_workspace(abandon_plan)
        validate_workspace_abandon_receipt(abandon_receipt, abandon_plan)
        abandon_path = Path(creation["workspace_path"]) / "workspace_abandon_receipt.json"
        _require(abandon_path.exists(), "abandon must write receipt inside guarded temp workspace")
        _require(json.loads(abandon_path.read_text(encoding="utf-8")) == abandon_receipt,
                 "abandon receipt file must match returned receipt")
        _require(Path(creation["workspace_path"]).exists(), "abandon must leave workspace for review")
        cleanup_guarded_workspace(collect_workspace_cleanup_plan(creation, cleanup_reason="abandon test cleanup"))

    bad_plan = dict(cleanup_preview)
    bad_plan["workspace_path"] = str(ROOT)
    try:
        validate_workspace_cleanup_plan(bad_plan)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace cleanup plan must reject mutated deterministic id")

    with tempfile.TemporaryDirectory() as temp_root:
        bad_path = Path(temp_root) / "not-a-guarded-workspace"
        bad_path.mkdir()
        bad_out = io.StringIO()
        bad_err = io.StringIO()
        with contextlib.redirect_stdout(bad_out), contextlib.redirect_stderr(bad_err):
            bad_rc = workspace_cleanup_main([
                "--write", "--json",
                "--workspace-path", str(bad_path),
                "--workspace-id", "missing-workspace",
            ])
        _require(bad_rc != 0, "workspace-cleanup must reject invalid workspace")
        _require("manifest" in bad_err.getvalue().lower(), "invalid workspace error must mention manifest")
        _require(bad_path.exists(), "invalid workspace rejection must not remove directory")

    print("guarded workspace cleanup/abandon lifecycle OK")


# ---------------------------------------------------------------------------
# 62. Growth planning-chain review bundle helper
# ---------------------------------------------------------------------------

def check_planning_chain_review_bundle_helper() -> None:
    """planning-chain review bundle summarizes the full chain without writes."""
    from link_modes.growth.link_growth_console import (
        collect_growth_planning_chain_preview,
        collect_planning_chain_review_bundle,
        parse_planning_chain_review_bundle_json,
        stable_planning_chain_review_bundle_json,
        validate_planning_chain_review_bundle,
    )

    chain = collect_growth_planning_chain_preview()
    bundle = collect_planning_chain_review_bundle(chain)
    same = collect_planning_chain_review_bundle(chain)
    _require(bundle["review_bundle_id"] == same["review_bundle_id"],
             "planning-chain review bundle id must be deterministic")
    encoded = stable_planning_chain_review_bundle_json(bundle)
    _require(encoded == stable_planning_chain_review_bundle_json(bundle),
             "planning-chain review bundle JSON must be stable")
    decoded = parse_planning_chain_review_bundle_json(encoded)
    _require(decoded == bundle, "planning-chain review bundle JSON must round trip")
    validate_planning_chain_review_bundle(bundle, chain)

    action = chain["top_recommended_next_action"]
    patch_plan = chain["verified_patch_plan"]
    quality_gate = chain["patch_behavior_quality_gate"]
    execution = chain["autonomous_execution_package"]
    _require(bundle["planning_chain_id"] == chain["planning_chain_id"],
             "review bundle must preserve planning_chain_id")
    _require(bundle["top_upgrade_id"] == action["upgrade_id"],
             "review bundle must preserve top upgrade id")
    _require(bundle["top_upgrade_title"] == action["title"],
             "review bundle must preserve top upgrade title")
    _require(bundle["branch_plan_id"] == action["branch_plan_id"],
             "review bundle must preserve branch plan id")
    _require(bundle["work_package_id"] == action["package_id"],
             "review bundle must preserve work package id")
    _require(bundle["verification_plan_id"] == action["verification_plan_id"],
             "review bundle must preserve verification plan id")
    _require(bundle["verified_patch_plan_id"] == action["verified_patch_plan_id"],
             "review bundle must preserve verified patch plan id")
    _require(bundle["verified_patch_diff_id"] == action["verified_patch_diff_id"],
             "review bundle must preserve verified patch diff id")
    _require(bundle["autonomous_execution_package_id"] == action["execution_package_id"],
             "review bundle must preserve autonomous execution package id")
    _require(bundle["execution_stage_count"] == execution["stage_count"],
             "review bundle must preserve execution stage count")
    _require(bundle["required_evidence"] == sorted(patch_plan["required_evidence"]),
             "review bundle must summarize required evidence")
    _require(bundle["missing_evidence"] == sorted(patch_plan["missing_evidence"]),
             "review bundle must summarize missing evidence")
    _require(bundle["patch_behavior_quality_gate"]["quality_gate_id"] == quality_gate["quality_gate_id"],
             "review bundle must summarize quality gate id")
    _require(bundle["patch_behavior_quality_gate"]["pass_status"] == quality_gate["pass_status"],
             "review bundle must summarize quality gate status")
    _require(bundle["top_risks"], "review bundle must include a risk summary")
    _require(bundle["recommended_next_action"] == action["summary"],
             "review bundle must preserve recommended next action")
    _require(bundle["dry_run"] is True and bundle["write_allowed"] is False,
             "review bundle must remain read-only")
    _require(bundle["automation_allowed"] is False and bundle["writes"] == [],
             "review bundle must not allow automation or writes")

    bad_missing = dict(bundle)
    bad_missing.pop("review_bundle_id")
    try:
        validate_planning_chain_review_bundle(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("review bundle must reject missing review_bundle_id")

    bad_writes = dict(bundle)
    bad_writes["writes"] = [".agents/runtime.json"]
    try:
        validate_planning_chain_review_bundle(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("review bundle must reject writes")

    bad_chain_ref = dict(bundle)
    bad_chain_ref["planning_chain_id"] = "growth-planning-chain-other"
    try:
        validate_planning_chain_review_bundle(bad_chain_ref, chain)
    except ValueError:
        pass
    else:
        raise AssertionError("review bundle must reject planning-chain id mismatch")


    print("planning-chain review bundle helper OK")


# ---------------------------------------------------------------------------
# 63. Execution readiness helper stack
# ---------------------------------------------------------------------------

def check_execution_readiness_stack_helper() -> None:
    """execution-readiness helpers stay read-only and preserve ID flow."""
    from link_modes.growth.link_growth_console import (
        collect_execution_event_timeline,
        collect_execution_readiness_bundle,
        collect_execution_retry_policy,
        collect_execution_workspace_plan,
        collect_growth_planning_chain_preview,
        collect_human_approval_package,
        collect_witness_manifest_plan,
        parse_execution_event_timeline_json,
        parse_execution_readiness_bundle_json,
        parse_execution_retry_policy_json,
        parse_execution_workspace_plan_json,
        parse_human_approval_package_json,
        parse_witness_manifest_plan_json,
        stable_execution_event_timeline_json,
        stable_execution_readiness_bundle_json,
        stable_execution_retry_policy_json,
        stable_execution_workspace_plan_json,
        stable_human_approval_package_json,
        stable_witness_manifest_plan_json,
        validate_execution_event_timeline,
        validate_execution_readiness_bundle,
        validate_execution_retry_policy,
        validate_execution_workspace_plan,
        validate_human_approval_package,
        validate_witness_manifest_plan,
    )

    chain = collect_growth_planning_chain_preview()
    review = chain["planning_chain_review_bundle"]
    execution = chain["autonomous_execution_package"]

    workspace = collect_execution_workspace_plan(chain)
    same_workspace = collect_execution_workspace_plan(chain)
    _require(workspace["workspace_id"] == same_workspace["workspace_id"],
             "workspace plan id must be deterministic")
    _require(parse_execution_workspace_plan_json(stable_execution_workspace_plan_json(workspace)) == workspace,
             "workspace plan JSON must round trip")
    validate_execution_workspace_plan(workspace, chain)
    _require(workspace["planning_chain_id"] == chain["planning_chain_id"],
             "workspace plan must reference planning chain")
    _require(workspace["review_bundle_id"] == review["review_bundle_id"],
             "workspace plan must reference review bundle")
    _require(workspace["execution_package_id"] == execution["execution_package_id"],
             "workspace plan must reference execution package")
    _require(workspace["cleanup_policy"] == "keep_on_unknown_or_failed_verification",
             "workspace cleanup policy must fail closed")
    _require(workspace["dry_run"] is True and workspace["write_allowed"] is False,
             "workspace plan must be read-only")
    _require(workspace["automation_allowed"] is False and workspace["writes"] == [],
             "workspace plan must not allow automation or writes")

    timeline = collect_execution_event_timeline(workspace, chain=chain)
    _require(parse_execution_event_timeline_json(stable_execution_event_timeline_json(timeline)) == timeline,
             "execution event timeline JSON must round trip")
    validate_execution_event_timeline(timeline, workspace)
    _require(timeline["workspace_id"] == workspace["workspace_id"],
             "timeline must reference workspace")
    _require([event["event_type"] for event in timeline["events"]] == [
        "workspace_planned",
        "branch_planned",
        "patch_application_planned",
        "compile_planned",
        "tests_planned",
        "healthcheck_planned",
        "quality_gate_planned",
        "review_bundle_planned",
        "cleanup_planned",
    ], "timeline must preserve canonical execution lifecycle")

    retry = collect_execution_retry_policy(timeline, workspace_plan=workspace)
    _require(parse_execution_retry_policy_json(stable_execution_retry_policy_json(retry)) == retry,
             "execution retry policy JSON must round trip")
    validate_execution_retry_policy(retry, timeline)
    _require(retry["execution_event_timeline_id"] == timeline["execution_event_timeline_id"],
             "retry policy must reference timeline")
    _require("any non-retryable failure occurs" in retry["stop_conditions"],
             "retry policy must include stop conditions")
    _require("compile failure after patch application" in retry["non_retryable_failures"],
             "retry policy must not retry deterministic compile failures")

    witness = collect_witness_manifest_plan(chain)
    _require(parse_witness_manifest_plan_json(stable_witness_manifest_plan_json(witness)) == witness,
             "witness manifest plan JSON must round trip")
    validate_witness_manifest_plan(witness, chain)
    _require(witness["expected_patch_diff_id"] == review["verified_patch_diff_id"],
             "witness plan must reference patch diff")
    _require(witness["expected_execution_package_id"] == execution["execution_package_id"],
             "witness plan must reference execution package")
    _require(witness["expected_review_bundle_id"] == review["review_bundle_id"],
             "witness plan must reference review bundle")
    _require(witness["missing_evidence"] == witness["required_evidence"],
             "default witness plan must surface missing evidence")

    approval = collect_human_approval_package(chain, workspace_plan=workspace, witness_manifest_plan=witness)
    _require(parse_human_approval_package_json(stable_human_approval_package_json(approval)) == approval,
             "human approval package JSON must round trip")
    validate_human_approval_package(approval, chain, workspace, witness)
    _require(approval["planning_chain_id"] == chain["planning_chain_id"],
             "approval package must reference planning chain")
    _require(approval["workspace_id"] == workspace["workspace_id"],
             "approval package must reference workspace")
    _require(approval["evidence_summary"]["missing_count"] == len(witness["missing_evidence"]),
             "approval package must summarize evidence")
    _require(approval["recommended_human_decision"] in {"approve", "revise", "reject"},
             "approval package must produce a bounded decision")

    readiness = collect_execution_readiness_bundle(
        chain,
        workspace_plan=workspace,
        event_timeline=timeline,
        retry_policy=retry,
        witness_manifest_plan=witness,
        human_approval_package=approval,
    )
    _require(parse_execution_readiness_bundle_json(stable_execution_readiness_bundle_json(readiness)) == readiness,
             "execution readiness bundle JSON must round trip")
    validate_execution_readiness_bundle(readiness)
    _require(readiness["execution_workspace_plan"]["workspace_id"] == workspace["workspace_id"],
             "readiness bundle must include workspace plan")
    _require(readiness["execution_event_timeline"]["execution_event_timeline_id"] == timeline["execution_event_timeline_id"],
             "readiness bundle must include timeline")
    _require(readiness["retry_policy"]["retry_policy_id"] == retry["retry_policy_id"],
             "readiness bundle must include retry policy")
    _require(readiness["witness_manifest_plan"]["witness_manifest_id"] == witness["witness_manifest_id"],
             "readiness bundle must include witness manifest plan")
    _require(readiness["human_approval_package"]["approval_package_id"] == approval["approval_package_id"],
             "readiness bundle must include human approval package")
    _require(readiness["readiness_status"] in {"blocked", "needs_evidence"},
             "default readiness should not claim ready while evidence is missing")
    _require(readiness["blocking_reasons"], "blocked readiness must include reasons")
    _require(readiness["dry_run"] is True and readiness["write_allowed"] is False,
             "readiness bundle must remain read-only")
    _require(readiness["automation_allowed"] is False and readiness["writes"] == [],
             "readiness bundle must not allow automation or writes")

    import copy as _copy

    reviewed_chain = _copy.deepcopy(chain)
    reviewed_chain["patch_behavior_quality_gate"]["pass_status"] = "pass"
    reviewed_chain["patch_behavior_quality_gate"]["findings"] = []
    reviewed_chain["patch_behavior_quality_gate"]["required_clarifications"] = []
    reviewed_chain["planning_chain_review_bundle"]["patch_behavior_quality_gate"]["pass_status"] = "pass"
    reviewed_chain["planning_chain_review_bundle"]["required_clarifications"] = []
    reviewed_chain["stage_summary"]["quality_gate_status"] = "pass"
    complete_witness = collect_witness_manifest_plan(
        reviewed_chain,
        provided_evidence=witness["required_evidence"],
    )
    ready_workspace = collect_execution_workspace_plan(reviewed_chain)
    ready_workspace = dict(ready_workspace)
    ready_workspace["blocked"] = False
    ready_approval = collect_human_approval_package(
        reviewed_chain,
        workspace_plan=ready_workspace,
        witness_manifest_plan=complete_witness,
    )
    _require(ready_approval["recommended_human_decision"] == "approve",
             "approval package should recommend approve when unblocked")
    ready_timeline = collect_execution_event_timeline(ready_workspace, chain=reviewed_chain)
    ready_retry = collect_execution_retry_policy(ready_timeline, workspace_plan=ready_workspace)
    ready_bundle = collect_execution_readiness_bundle(
        reviewed_chain,
        workspace_plan=ready_workspace,
        event_timeline=ready_timeline,
        retry_policy=ready_retry,
        witness_manifest_plan=complete_witness,
        human_approval_package=ready_approval,
    )
    _require(ready_bundle["readiness_status"] == "ready_for_review",
             "readiness bundle should become ready_for_review when unblocked")
    _require(ready_bundle["blocking_reasons"] == [],
             "ready_for_review bundle must not include blocking reasons")

    bad_workspace = dict(workspace)
    bad_workspace["writes"] = [".link/runtime.json"]
    try:
        validate_execution_workspace_plan(bad_workspace)
    except ValueError:
        pass
    else:
        raise AssertionError("workspace plan must reject writes")

    bad_event = dict(timeline)
    bad_event["events"] = [dict(event) for event in timeline["events"]]
    bad_event["events"][0]["event_type"] = "branch_planned"
    try:
        validate_execution_event_timeline(bad_event)
    except ValueError:
        pass
    else:
        raise AssertionError("timeline must reject malformed event order")

    bad_retry = dict(retry)
    bad_retry["max_attempts"] = 0
    try:
        validate_execution_retry_policy(bad_retry)
    except ValueError:
        pass
    else:
        raise AssertionError("retry policy must reject invalid max_attempts")

    bad_witness = dict(witness)
    bad_witness["missing_evidence"] = []
    try:
        validate_witness_manifest_plan(bad_witness)
    except ValueError:
        pass
    else:
        raise AssertionError("witness manifest must reject inconsistent evidence accounting")

    bad_approval = dict(approval)
    bad_approval["recommended_human_decision"] = "ship"
    try:
        validate_human_approval_package(bad_approval)
    except ValueError:
        pass
    else:
        raise AssertionError("approval package must reject invalid decision")

    bad_readiness = dict(readiness)
    bad_readiness["readiness_status"] = "ready_for_review"
    try:
        validate_execution_readiness_bundle(bad_readiness)
    except ValueError:
        pass
    else:
        raise AssertionError("readiness bundle must reject ready status with blockers")

    print("execution readiness stack helper OK")


# ---------------------------------------------------------------------------
# 64. Execution journal schema helper
# ---------------------------------------------------------------------------

def check_execution_journal_schema_helper() -> None:
    """execution journal plan models append-only future execution events."""
    from link_modes.growth.link_growth_console import (
        collect_execution_journal_plan,
        collect_execution_readiness_bundle,
        parse_execution_journal_plan_json,
        stable_execution_journal_plan_json,
        validate_execution_journal_plan,
    )

    readiness = collect_execution_readiness_bundle()
    execution = readiness["planning_chain"]["autonomous_execution_package"]
    journal = collect_execution_journal_plan(
        readiness,
        evidence_refs_by_stage={
            "run_tests": ["evidence:test-log", "evidence:test-log", "evidence:coverage-summary"],
            "produce_review_bundle": ["evidence:review-bundle"],
        },
        metadata={"suite": "growth"},
    )
    same = collect_execution_journal_plan(
        readiness,
        evidence_refs_by_stage={
            "run_tests": ["evidence:test-log", "evidence:test-log", "evidence:coverage-summary"],
            "produce_review_bundle": ["evidence:review-bundle"],
        },
        metadata={"suite": "growth"},
    )
    _require(journal["execution_journal_id"] == same["execution_journal_id"],
             "execution journal id must be deterministic")
    decoded = parse_execution_journal_plan_json(stable_execution_journal_plan_json(journal))
    _require(decoded == journal, "execution journal JSON must round trip")
    validate_execution_journal_plan(journal, readiness)
    _require(journal["execution_package_id"] == execution["execution_package_id"],
             "journal must reference autonomous execution package")
    _require(journal["planning_chain_id"] == readiness["planning_chain"]["planning_chain_id"],
             "journal must reference planning chain")
    _require(journal["upgrade_id"] == execution["upgrade_id"],
             "journal must preserve upgrade id")
    _require(journal["branch_plan_id"] == execution["branch_plan_id"],
             "journal must preserve branch plan id")
    _require(journal["work_package_id"] == execution["work_package_id"],
             "journal must preserve work package id")
    _require(journal["verification_plan_id"] == execution["verification_plan_id"],
             "journal must preserve verification plan id")
    _require(journal["dry_run"] is True and journal["write_allowed"] is False,
             "journal plan must remain read-only")
    _require(journal["automation_allowed"] is False and journal["writes"] == [],
             "journal plan must not allow automation or writes")

    expected_stages = [
        "create_workspace",
        "create_branch",
        "apply_patch_operations",
        "run_compile",
        "run_tests",
        "run_healthcheck",
        "evaluate_quality_gate",
        "produce_review_bundle",
    ]
    entries = journal["journal_entries"]
    _require([entry["sequence"] for entry in entries] == list(range(1, len(expected_stages) + 1)),
             "journal entries must be ordered by sequence")
    _require([entry["stage"] for entry in entries] == expected_stages,
             "journal entries must use supported stage order")
    _require(all(entry["status"] == "planned" for entry in entries),
             "journal entries must default to planned status")
    _require(entries[4]["evidence_refs"] == ["evidence:coverage-summary", "evidence:test-log"],
             "journal evidence refs must be preserved and normalized")
    _require(entries[2]["rollback_required"] is True,
             "patch application journal entry must require rollback on failure")
    _require(entries[-1]["rollback_required"] is False,
             "review bundle production should not itself require rollback")
    _require(entries[3]["retryable"] is True and entries[4]["retryable"] is True,
             "compile and test journal entries should be retryable by policy")
    _require(entries[0]["retryable"] is False,
             "workspace creation journal entry should not be marked retryable")

    bad_duplicate = dict(journal)
    bad_duplicate["journal_entries"] = [dict(entry) for entry in entries]
    bad_duplicate["journal_entries"][1]["sequence"] = 1
    try:
        validate_execution_journal_plan(bad_duplicate)
    except ValueError:
        pass
    else:
        raise AssertionError("journal plan must reject duplicate sequence")

    bad_stage = dict(journal)
    bad_stage["journal_entries"] = [dict(entry) for entry in entries]
    bad_stage["journal_entries"][0]["stage"] = "run_everything"
    try:
        validate_execution_journal_plan(bad_stage)
    except ValueError:
        pass
    else:
        raise AssertionError("journal plan must reject invalid stage")

    bad_status = dict(journal)
    bad_status["journal_entries"] = [dict(entry) for entry in entries]
    bad_status["journal_entries"][0]["status"] = "maybe"
    try:
        validate_execution_journal_plan(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("journal plan must reject invalid status")

    bad_writes = dict(journal)
    bad_writes["writes"] = [".link/execution-journal.json"]
    try:
        validate_execution_journal_plan(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("journal plan must reject writes")

    print("execution journal schema helper OK")


# ---------------------------------------------------------------------------
# 65. Execution evidence contract helper
# ---------------------------------------------------------------------------

def check_execution_evidence_contract_helper() -> None:
    """execution evidence contract defines future evidence without collecting it."""
    from link_modes.growth.link_growth_console import (
        collect_execution_evidence_contract,
        collect_execution_journal_plan,
        collect_execution_readiness_bundle,
        parse_execution_evidence_contract_json,
        stable_execution_evidence_contract_json,
        validate_execution_evidence_contract,
    )

    readiness = collect_execution_readiness_bundle()
    journal = collect_execution_journal_plan(readiness)
    contract = collect_execution_evidence_contract(journal, metadata={"suite": "growth"})
    same = collect_execution_evidence_contract(journal, metadata={"suite": "growth"})
    _require(contract["execution_evidence_contract_id"] == same["execution_evidence_contract_id"],
             "execution evidence contract id must be deterministic")
    decoded = parse_execution_evidence_contract_json(stable_execution_evidence_contract_json(contract))
    _require(decoded == contract, "execution evidence contract JSON must round trip")
    validate_execution_evidence_contract(contract, journal)
    _require(contract["execution_journal_id"] == journal["execution_journal_id"],
             "evidence contract must reference execution journal")
    _require(contract["execution_package_id"] == journal["execution_package_id"],
             "evidence contract must reference execution package")
    _require(contract["dry_run"] is True and contract["write_allowed"] is False,
             "evidence contract must remain read-only")
    _require(contract["automation_allowed"] is False and contract["writes"] == [],
             "evidence contract must not allow automation or writes")

    items = {item["evidence_type"]: item for item in contract["evidence_items"]}
    for evidence_type in ("compile", "tests", "healthcheck", "patch_application", "quality_gate"):
        _require(evidence_type in items, f"{evidence_type} evidence must be required")
    _require("rollback" in items, "rollback evidence must be required when rollback applies")

    command_fields = {
        "attempt_id",
        "command",
        "combined_log_ref",
        "completed_at_policy",
        "exit_code",
        "journal_entry_id",
        "log_hash",
        "reviewer_visible_summary",
        "started_at_policy",
        "stderr_log_ref",
        "stdout_log_ref",
    }
    for evidence_type in ("compile", "tests", "healthcheck"):
        required = set(items[evidence_type]["required_fields"])
        _require(command_fields.issubset(required),
                 f"{evidence_type} evidence must require command, exit, log, journal, and attempt fields")
        _require(items[evidence_type]["reviewer_summary_required"] is True,
                 f"{evidence_type} evidence must require reviewer summary")
        _require(items[evidence_type]["blocks_completion_if_missing"] is True,
                 f"{evidence_type} evidence must block completion if missing")

    patch_required = set(items["patch_application"]["required_fields"])
    _require({"changed_file_refs", "changed_file_hashes", "diff_hash"}.issubset(patch_required),
             "patch evidence must require diff and changed-file hashes")
    rollback_required = set(items["rollback"]["required_fields"])
    _require("rollback_ref" in rollback_required,
             "rollback evidence must require rollback_ref")
    _require(items["rollback"]["blocks_completion_if_missing"] is True,
             "rollback evidence must block completion when rollback applies")
    _require(items["compile"]["journal_entry_id"] == journal["journal_entries"][3]["entry_id"],
             "compile evidence must reference compile journal entry")
    _require(items["tests"]["journal_entry_id"] == journal["journal_entries"][4]["entry_id"],
             "test evidence must reference test journal entry")
    _require(items["healthcheck"]["journal_entry_id"] == journal["journal_entries"][5]["entry_id"],
             "healthcheck evidence must reference healthcheck journal entry")

    bad_missing = dict(contract)
    bad_missing["evidence_items"] = [dict(item) for item in contract["evidence_items"]]
    bad_missing["evidence_items"][0]["required_fields"] = [
        field for field in bad_missing["evidence_items"][0]["required_fields"]
        if field != "journal_entry_id"
    ]
    try:
        validate_execution_evidence_contract(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("evidence contract must reject missing common required fields")

    bad_type = dict(contract)
    bad_type["evidence_items"] = [dict(item) for item in contract["evidence_items"]]
    bad_type["evidence_items"][0]["evidence_type"] = "screenshots"
    try:
        validate_execution_evidence_contract(bad_type)
    except ValueError:
        pass
    else:
        raise AssertionError("evidence contract must reject invalid evidence_type")

    bad_writes = dict(contract)
    bad_writes["writes"] = [".link/execution-evidence.json"]
    try:
        validate_execution_evidence_contract(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("evidence contract must reject writes")

    no_rollback_journal = dict(journal)
    no_rollback_journal["journal_entries"] = [dict(entry) for entry in journal["journal_entries"]]
    for entry in no_rollback_journal["journal_entries"]:
        entry["rollback_required"] = False
    no_rollback_contract = collect_execution_evidence_contract(no_rollback_journal)
    no_rollback_types = {item["evidence_type"] for item in no_rollback_contract["evidence_items"]}
    _require("rollback" not in no_rollback_types,
             "rollback evidence must not be required when rollback does not apply")
    validate_execution_evidence_contract(no_rollback_contract, no_rollback_journal)

    print("execution evidence contract helper OK")


# ---------------------------------------------------------------------------
# 66. Execution preflight checklist helper
# ---------------------------------------------------------------------------

def check_execution_preflight_checklist_helper() -> None:
    """execution preflight checklist summarizes future execution prerequisites."""
    from link_modes.growth.link_growth_console import (
        collect_execution_preflight_checklist,
        collect_growth_planning_chain_preview,
        parse_execution_preflight_checklist_json,
        stable_execution_preflight_checklist_json,
        validate_execution_preflight_checklist,
    )

    chain = collect_growth_planning_chain_preview()
    checklist = collect_execution_preflight_checklist(chain, metadata={"suite": "growth"})
    same = collect_execution_preflight_checklist(chain, metadata={"suite": "growth"})
    _require(checklist["preflight_checklist_id"] == same["preflight_checklist_id"],
             "execution preflight checklist id must be deterministic")
    decoded = parse_execution_preflight_checklist_json(stable_execution_preflight_checklist_json(checklist))
    _require(decoded == checklist, "execution preflight checklist JSON must round trip")
    validate_execution_preflight_checklist(checklist, chain)

    readiness = chain["execution_readiness_bundle"]
    evidence_contract = chain["execution_evidence_contract"]
    approval = chain["human_approval_package"]
    workspace = chain["execution_workspace_plan"]
    _require(checklist["planning_chain_id"] == chain["planning_chain_id"],
             "preflight checklist must reference planning chain")
    _require(checklist["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "preflight checklist must reference execution package")
    _require(checklist["execution_readiness_bundle_id"] == readiness["execution_readiness_bundle_id"],
             "preflight checklist must reference readiness bundle")
    _require(checklist["execution_evidence_contract_id"] == evidence_contract["execution_evidence_contract_id"],
             "preflight checklist must reference evidence contract")
    _require(checklist["human_approval_package_id"] == approval["approval_package_id"],
             "preflight checklist must reference human approval package")
    _require(checklist["workspace_id"] == workspace["workspace_id"],
             "preflight checklist must reference workspace plan")

    _require(checklist["required_human_approvals"],
             "preflight checklist must include required human approvals")
    _require(checklist["clean_tree_checks"],
             "preflight checklist must include clean-tree checks")
    _require(checklist["path_safety_checks"],
             "preflight checklist must include path safety checks")
    _require(checklist["command_allowlist_checks"],
             "preflight checklist must include command allowlist checks")
    _require(checklist["branch_worktree_isolation_checks"],
             "preflight checklist must include branch/worktree isolation checks")
    _require(checklist["evidence_contract_checks"],
             "preflight checklist must include evidence contract checks")
    _require({check["name"] for check in checklist["required_human_approvals"]} == set(approval["required_approvals"]),
             "preflight checklist must preserve human approvals")
    _require({check["name"] for check in checklist["command_allowlist_checks"]} == set(workspace["verification_requirements"]),
             "preflight checklist must preserve command allowlist checks")
    evidence_types = {item["evidence_type"] for item in evidence_contract["evidence_items"]}
    _require(evidence_types.issubset({check["name"] for check in checklist["evidence_contract_checks"]}),
             "preflight checklist must cover evidence contract requirements")

    all_checks = []
    for group in (
        "required_human_approvals",
        "clean_tree_checks",
        "path_safety_checks",
        "command_allowlist_checks",
        "branch_worktree_isolation_checks",
        "evidence_contract_checks",
    ):
        all_checks.extend(checklist[group])
    _require(checklist["blocker_count"] == sum(1 for check in all_checks if check["status"] == "block"),
             "preflight checklist blocker_count must match checks")
    _require(checklist["warning_count"] == sum(1 for check in all_checks if check["status"] == "warning"),
             "preflight checklist warning_count must match checks")
    _require(checklist["pass_status"] in {"pass", "review", "block"},
             "preflight checklist pass_status must be bounded")
    _require(checklist["blocker_count"] > 0 and checklist["pass_status"] == "block",
             "default preflight checklist should block while readiness evidence is missing")
    _require(checklist["dry_run"] is True and checklist["write_allowed"] is False,
             "preflight checklist must remain read-only")
    _require(checklist["automation_allowed"] is False and checklist["writes"] == [],
             "preflight checklist must not allow automation or writes")

    bad_missing = dict(checklist)
    del bad_missing["execution_readiness_bundle_id"]
    try:
        validate_execution_preflight_checklist(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("preflight checklist must reject missing readiness reference")

    bad_evidence = dict(checklist)
    bad_evidence["execution_evidence_contract_id"] = "wrong-contract"
    try:
        validate_execution_preflight_checklist(bad_evidence, chain)
    except ValueError:
        pass
    else:
        raise AssertionError("preflight checklist must reject mismatched evidence reference")

    bad_writes = dict(checklist)
    bad_writes["writes"] = [".link/preflight.json"]
    try:
        validate_execution_preflight_checklist(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("preflight checklist must reject writes")

    bad_status = dict(checklist)
    bad_status["required_human_approvals"] = [dict(check) for check in checklist["required_human_approvals"]]
    bad_status["required_human_approvals"][0]["status"] = "maybe"
    try:
        validate_execution_preflight_checklist(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("preflight checklist must reject malformed check status")

    print("execution preflight checklist helper OK")


# ---------------------------------------------------------------------------
# 67. Execution attempt history helper
# ---------------------------------------------------------------------------

def check_execution_attempt_history_helper() -> None:
    """execution attempt history models future attempts without running them."""
    from link_modes.growth.link_growth_console import (
        collect_execution_attempt_history,
        collect_growth_planning_chain_preview,
        parse_execution_attempt_history_json,
        stable_execution_attempt_history_json,
        validate_execution_attempt_history,
    )

    chain = collect_growth_planning_chain_preview()
    journal = chain["execution_journal_plan"]
    retry = chain["execution_retry_policy"]
    execution = chain["autonomous_execution_package"]
    history = collect_execution_attempt_history(journal, retry_policy=retry, execution_package=execution, metadata={"suite": "growth"})
    same = collect_execution_attempt_history(journal, retry_policy=retry, execution_package=execution, metadata={"suite": "growth"})
    _require(history["attempt_history_id"] == same["attempt_history_id"],
             "execution attempt history id must be deterministic")
    decoded = parse_execution_attempt_history_json(stable_execution_attempt_history_json(history))
    _require(decoded == history, "execution attempt history JSON must round trip")
    validate_execution_attempt_history(history, journal, retry, execution)

    _require(history["execution_package_id"] == execution["execution_package_id"],
             "attempt history must reference execution package")
    _require(history["execution_journal_plan_id"] == journal["execution_journal_id"],
             "attempt history must reference execution journal")
    _require(history["retry_policy_id"] == retry["retry_policy_id"],
             "attempt history must reference retry policy")
    _require(history["attempt_count"] == retry["max_attempts"],
             "attempt history should plan attempts from retry policy")
    _require([attempt["sequence"] for attempt in history["attempts"]] == list(range(1, retry["max_attempts"] + 1)),
             "attempt history must preserve ordered attempt sequences")
    _require(all(attempt["status"] == "planned" for attempt in history["attempts"]),
             "default attempts must be planned only")
    _require(history["retry_allowed_count"] == retry["max_attempts"] - 1,
             "retry accounting must follow retry policy")
    _require(history["attempts"][-1]["retry_allowed"] is False,
             "last attempt must not allow another retry")
    _require(history["rollback_required_count"] == history["attempt_count"],
             "rollback accounting must follow journal rollback policy")
    expected_evidence = {"compile", "healthcheck", "patch_application", "quality_gate", "rollback", "tests"}
    _require(set(history["attempts"][0]["expected_evidence"]) == expected_evidence,
             "attempts must preserve expected evidence labels")
    _require(history["dry_run"] is True and history["write_allowed"] is False,
             "attempt history must remain read-only")
    _require(history["automation_allowed"] is False and history["writes"] == [],
             "attempt history must not allow automation or writes")

    bad_status = dict(history)
    bad_status["attempts"] = [dict(attempt) for attempt in history["attempts"]]
    bad_status["attempts"][0]["status"] = "maybe"
    try:
        validate_execution_attempt_history(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("attempt history must reject invalid statuses")

    bad_retry = dict(history)
    bad_retry["attempts"] = [dict(attempt) for attempt in history["attempts"]]
    bad_retry["attempts"][0]["retry_allowed"] = False
    bad_retry["retry_allowed_count"] = sum(1 for attempt in bad_retry["attempts"] if attempt["retry_allowed"])
    try:
        validate_execution_attempt_history(bad_retry, journal, retry, execution)
    except ValueError:
        pass
    else:
        raise AssertionError("attempt history must reject retry accounting mismatches")

    bad_rollback = dict(history)
    bad_rollback["attempts"] = [dict(attempt) for attempt in history["attempts"]]
    bad_rollback["attempts"][0]["rollback_required"] = False
    bad_rollback["rollback_required_count"] = sum(1 for attempt in bad_rollback["attempts"] if attempt["rollback_required"])
    try:
        validate_execution_attempt_history(bad_rollback, journal, retry, execution)
    except ValueError:
        pass
    else:
        raise AssertionError("attempt history must reject rollback accounting mismatches")

    bad_link = dict(history)
    bad_link["execution_journal_plan_id"] = "wrong-journal"
    try:
        validate_execution_attempt_history(bad_link, journal, retry, execution)
    except ValueError:
        pass
    else:
        raise AssertionError("attempt history must reject journal linkage mismatch")

    bad_writes = dict(history)
    bad_writes["writes"] = [".link/execution-attempt-history.json"]
    try:
        validate_execution_attempt_history(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("attempt history must reject writes")

    print("execution attempt history helper OK")


# ---------------------------------------------------------------------------
# 68. Execution readiness dashboard summary helper
# ---------------------------------------------------------------------------

def check_execution_readiness_dashboard_summary_helper() -> None:
    """execution readiness dashboard summary distills planning-chain state."""
    from link_modes.growth.link_growth_console import (
        collect_execution_readiness_dashboard_summary,
        collect_growth_planning_chain_preview,
        parse_execution_readiness_dashboard_summary_json,
        stable_execution_readiness_dashboard_summary_json,
        validate_execution_readiness_dashboard_summary,
    )

    chain = collect_growth_planning_chain_preview()
    summary = collect_execution_readiness_dashboard_summary(chain, metadata={"suite": "growth"})
    same = collect_execution_readiness_dashboard_summary(chain, metadata={"suite": "growth"})
    _require(summary["dashboard_summary_id"] == same["dashboard_summary_id"],
             "execution readiness dashboard summary id must be deterministic")
    decoded = parse_execution_readiness_dashboard_summary_json(stable_execution_readiness_dashboard_summary_json(summary))
    _require(decoded == summary, "execution readiness dashboard summary JSON must round trip")
    validate_execution_readiness_dashboard_summary(summary, chain)

    quality_gate = chain["patch_behavior_quality_gate"]
    evidence_contract = chain["execution_evidence_contract"]
    preflight = chain["execution_preflight_checklist"]
    attempts = chain["execution_attempt_history"]
    readiness = chain["execution_readiness_bundle"]
    execution = chain["autonomous_execution_package"]
    approval = chain["human_approval_package"]
    review_bundle = chain["planning_chain_review_bundle"]

    _require(summary["planning_chain_id"] == chain["planning_chain_id"],
             "dashboard summary must reference planning chain")
    _require(summary["top_upgrade_id"] == chain["top_recommended_next_action"]["upgrade_id"],
             "dashboard summary must preserve top upgrade id")
    _require(summary["top_upgrade_title"] == chain["top_recommended_next_action"]["title"],
             "dashboard summary must preserve top upgrade title")
    _require(summary["quality_gate"]["quality_gate_id"] == quality_gate["quality_gate_id"],
             "dashboard summary must preserve quality gate id")
    _require(summary["quality_gate"]["pass_status"] == quality_gate["pass_status"],
             "dashboard summary must preserve quality gate status")
    _require(summary["quality_gate"]["quality_score"] == quality_gate["quality_score"],
             "dashboard summary must preserve quality gate score")
    _require(summary["quality_gate"]["risk_score"] == quality_gate["risk_score"],
             "dashboard summary must preserve quality gate risk")
    _require(summary["execution_evidence_contract_id"] == evidence_contract["execution_evidence_contract_id"],
             "dashboard summary must reference evidence contract")
    _require(summary["required_evidence_count"] == evidence_contract["evidence_item_count"],
             "dashboard summary must summarize evidence count")
    _require(summary["preflight_checklist_id"] == preflight["preflight_checklist_id"],
             "dashboard summary must reference preflight checklist")
    _require(summary["preflight_status"] == preflight["pass_status"],
             "dashboard summary must preserve preflight status")
    _require(summary["preflight_blocker_count"] == preflight["blocker_count"],
             "dashboard summary must preserve preflight blocker count")
    _require(summary["preflight_warning_count"] == preflight["warning_count"],
             "dashboard summary must preserve preflight warning count")
    _require(summary["attempt_history_id"] == attempts["attempt_history_id"],
             "dashboard summary must reference attempt history")
    _require(summary["planned_attempt_count"] == attempts["attempt_count"],
             "dashboard summary must summarize planned attempts")
    _require(summary["execution_readiness_bundle_id"] == readiness["execution_readiness_bundle_id"],
             "dashboard summary must reference readiness bundle")
    _require(summary["readiness_status"] == readiness["readiness_status"],
             "dashboard summary must preserve readiness status")
    _require(summary["execution_package_id"] == execution["execution_package_id"],
             "dashboard summary must reference execution package")
    _require(summary["execution_stage_count"] == execution["stage_count"],
             "dashboard summary must summarize execution stages")
    _require(summary["required_approvals_count"] == len(approval["required_approvals"]),
             "dashboard summary must summarize required approvals")
    _require(summary["missing_evidence_count"] == len(review_bundle["missing_evidence"]),
             "dashboard summary must summarize missing evidence")
    _require(summary["required_clarifications_count"] == len(review_bundle["required_clarifications"]),
             "dashboard summary must summarize required clarifications")
    gate_stack = chain["execution_gate_stack_preview"]
    _require(summary["gate_stack_preview_id"] == gate_stack["gate_stack_preview_id"],
             "dashboard summary must reference gate stack")
    _require(summary["gate_count"] == gate_stack["gate_count"],
             "dashboard summary must summarize gate count")
    _require(summary["pass_count"] == gate_stack["pass_count"],
             "dashboard summary must summarize gate pass count")
    _require(summary["review_count"] == gate_stack["review_count"],
             "dashboard summary must summarize gate review count")
    _require(summary["block_count"] == gate_stack["block_count"],
             "dashboard summary must summarize gate block count")
    _require(isinstance(summary["gate_stack_top_blockers"], list),
             "dashboard summary must include gate stack top blockers")
    _require(isinstance(summary["gate_stack_top_warnings"], list),
             "dashboard summary must include gate stack top warnings")
    _require(isinstance(summary["top_blockers"], list) and summary["top_blockers"],
             "dashboard summary must include top blockers for default blocked state")
    _require(isinstance(summary["top_warnings"], list),
             "dashboard summary must include top warnings list")
    _require(summary["recommended_next_action"] == gate_stack["recommended_next_action"],
             "dashboard summary must preserve gate stack recommended next action when present")
    _require(summary["dry_run"] is True and summary["write_allowed"] is False,
             "dashboard summary must remain read-only")
    _require(summary["automation_allowed"] is False and summary["writes"] == [],
             "dashboard summary must not allow automation or writes")

    bad_missing = dict(summary)
    del bad_missing["dashboard_summary_id"]
    try:
        validate_execution_readiness_dashboard_summary(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("dashboard summary must reject missing dashboard_summary_id")

    bad_quality = dict(summary)
    bad_quality["quality_gate"] = dict(summary["quality_gate"])
    bad_quality["quality_gate"]["risk_score"] = 2
    try:
        validate_execution_readiness_dashboard_summary(bad_quality)
    except ValueError:
        pass
    else:
        raise AssertionError("dashboard summary must reject invalid quality gate risk")

    bad_link = dict(summary)
    bad_link["attempt_history_id"] = "wrong-attempt-history"
    try:
        validate_execution_readiness_dashboard_summary(bad_link, chain)
    except ValueError:
        pass
    else:
        raise AssertionError("dashboard summary must reject planning-chain ID mismatch")

    bad_writes = dict(summary)
    bad_writes["writes"] = [".link/execution-dashboard-summary.json"]
    try:
        validate_execution_readiness_dashboard_summary(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("dashboard summary must reject writes")

    print("execution readiness dashboard summary helper OK")


# ---------------------------------------------------------------------------
# 69. Execution gate stack preview helper
# ---------------------------------------------------------------------------

def check_execution_gate_stack_preview_helper() -> None:
    """execution gate stack aggregates future execution gates without writes."""
    from link_modes.growth.link_growth_console import (
        EXECUTION_GATE_TYPES,
        collect_execution_gate_stack_preview,
        collect_growth_planning_chain_preview,
        parse_execution_gate_stack_preview_json,
        stable_execution_gate_stack_preview_json,
        validate_execution_gate_stack_preview,
    )

    chain = collect_growth_planning_chain_preview()
    preview = collect_execution_gate_stack_preview(chain, metadata={"suite": "growth"})
    same = collect_execution_gate_stack_preview(chain, metadata={"suite": "growth"})
    _require(preview["gate_stack_preview_id"] == same["gate_stack_preview_id"],
             "execution gate stack preview id must be deterministic")
    decoded = parse_execution_gate_stack_preview_json(stable_execution_gate_stack_preview_json(preview))
    _require(decoded == preview, "execution gate stack preview JSON must round trip")
    validate_execution_gate_stack_preview(preview, chain)

    _require(preview["planning_chain_id"] == chain["planning_chain_id"],
             "gate stack must reference planning chain")
    _require(preview["execution_package_id"] == chain["autonomous_execution_package"]["execution_package_id"],
             "gate stack must reference execution package")
    _require(preview["dashboard_summary_id"] == chain["execution_readiness_dashboard_summary"]["dashboard_summary_id"],
             "gate stack must reference dashboard summary")
    _require(preview["preflight_checklist_id"] == chain["execution_preflight_checklist"]["preflight_checklist_id"],
             "gate stack must reference preflight checklist")
    _require(preview["execution_evidence_contract_id"] == chain["execution_evidence_contract"]["execution_evidence_contract_id"],
             "gate stack must reference evidence contract")
    _require(preview["quality_gate_id"] == chain["patch_behavior_quality_gate"]["quality_gate_id"],
             "gate stack must reference quality gate")
    _require(preview["human_approval_package_id"] == chain["human_approval_package"]["approval_package_id"],
             "gate stack must reference human approval package")
    _require(preview["attempt_history_id"] == chain["execution_attempt_history"]["attempt_history_id"],
             "gate stack must reference attempt history")

    gates = preview["gates"]
    _require(preview["gate_count"] == len(gates),
             "gate stack gate_count must match gates")
    _require({gate["gate_type"] for gate in gates} == set(EXECUTION_GATE_TYPES),
             "gate stack must include all required gate types")
    _require(preview["pass_count"] == sum(1 for gate in gates if gate["pass_status"] == "pass"),
             "gate stack pass_count must match gates")
    _require(preview["review_count"] == sum(1 for gate in gates if gate["pass_status"] == "review"),
             "gate stack review_count must match gates")
    _require(preview["block_count"] == sum(1 for gate in gates if gate["pass_status"] == "block"),
             "gate stack block_count must match gates")
    _require(preview["block_count"] > 0,
             "default gate stack should block while execution readiness is blocked")

    by_type = {gate["gate_type"]: gate for gate in gates}
    _require(by_type["human_approval"]["blockers"],
             "human approval gate must surface approval blockers")
    _require(by_type["command_allowlist"]["warnings"],
             "command allowlist gate must surface command warnings")
    _require(by_type["quality_gate"]["required_evidence"],
             "quality gate must preserve missing evidence requirements")
    evidence_types = {item["evidence_type"] for item in chain["execution_evidence_contract"]["evidence_items"]}
    _require(evidence_types.issubset(set(by_type["evidence_contract"]["required_evidence"])),
             "evidence contract gate must aggregate required evidence")
    _require(by_type["workspace_isolation"]["required_human_action"],
             "workspace isolation gate must include required human action")

    _require(preview["dry_run"] is True and preview["write_allowed"] is False,
             "gate stack must remain read-only")
    _require(preview["automation_allowed"] is False and preview["writes"] == [],
             "gate stack must not allow automation or writes")

    bad_status = dict(preview)
    bad_status["gates"] = [dict(gate) for gate in gates]
    bad_status["gates"][0]["pass_status"] = "maybe"
    try:
        validate_execution_gate_stack_preview(bad_status)
    except ValueError:
        pass
    else:
        raise AssertionError("gate stack must reject invalid gate status")

    bad_missing = dict(preview)
    del bad_missing["planning_chain_id"]
    try:
        validate_execution_gate_stack_preview(bad_missing)
    except ValueError:
        pass
    else:
        raise AssertionError("gate stack must reject missing planning_chain_id")

    bad_link = dict(preview)
    bad_link["execution_package_id"] = "wrong-package"
    try:
        validate_execution_gate_stack_preview(bad_link, chain)
    except ValueError:
        pass
    else:
        raise AssertionError("gate stack must reject planning-chain id flow mismatch")

    bad_writes = dict(preview)
    bad_writes["writes"] = [".link/execution-gates.json"]
    try:
        validate_execution_gate_stack_preview(bad_writes)
    except ValueError:
        pass
    else:
        raise AssertionError("gate stack must reject writes")

    print("execution gate stack preview helper OK")


# ---------------------------------------------------------------------------
# 58. Growth archive-code-brief -- dry-run
# ---------------------------------------------------------------------------

def check_growth_archive_code_brief_dry_run() -> None:
    """archive-code-brief dry-run reads sources, produces preview, writes nothing."""
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_code_brief

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_dir = root / "extracted/commands/agent"
        src_dir.mkdir(parents=True)
        (src_dir / "index.ts").write_text(
            "// Agent command dispatcher\n"
            "import { registerTool } from '../tool-registry';\n"
            "export function agentOrchestrator() { return 'agent'; }\n"
            "// Permission check before agent delegation\n",
            encoding="utf-8",
        )
        (src_dir / "context.ts").write_text(
            "// Session context for agent pipeline\n"
            "export class AgentContext { storage: Map<string, any>; }\n",
            encoding="utf-8",
        )

        data = collect_code_brief(str(src_dir), write=False, root=str(root))
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("dry_run") is True, "dry-run must set dry_run=True")
        _require(data.get("brief_path") == "", "dry-run must have empty brief_path")
        _require(data.get("files_read_count", 0) == 2,
                 f"2 files should be read, got {data.get('files_read_count')}")
        _require(data.get("source_type") == "directory",
                 "source_type must be 'directory'")

        preview = data.get("brief_preview", [])
        _require(len(preview) >= 1, "dry-run must populate brief_preview")

        # Verify Growth Upgrade Candidates section is present
        preview_text = "\n".join(preview)
        _require("## Growth Upgrade Candidates" in preview_text,
                 "dry-run brief must include Growth Upgrade Candidates section")
        _require("### UPGRADE CANDIDATE:" in preview_text,
                 "dry-run brief must include at least one UPGRADE CANDIDATE block")

        # Verify no files written
        briefs_dir = root / "research/_catalog/code_briefs"
        _require(not briefs_dir.exists(),
                 f"dry-run must not create briefs dir: {briefs_dir}")

    print("growth archive-code-brief dry-run OK")


# ---------------------------------------------------------------------------
# 48. Growth archive-code-brief -- --write
# ---------------------------------------------------------------------------

def check_growth_archive_code_brief_write() -> None:
    """archive-code-brief --write persists a markdown brief to disk."""
    import json as _json
    from pathlib import Path
    from link_modes.growth.link_growth_console import collect_code_brief

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        src_file = root / "extracted/src/main.ts"
        src_file.parent.mkdir(parents=True)
        src_file.write_text(
            "// Main CLI entry\n"
            "import { CommandRouter } from './router';\n"
            "import { ToolRegistry } from './tools';\n"
            "import { AgentOrchestrator } from './agent';\n"
            "import { MemoryStore } from './memory';\n"
            "const router = new CommandRouter();\n"
            "const tools = new ToolRegistry();\n"
            "const agent = new AgentOrchestrator(tools, new MemoryStore());\n"
            "export { router, tools, agent };\n",
            encoding="utf-8",
        )

        data = collect_code_brief(str(src_file), write=True, root=str(root))
        _require(data.get("ok") is True, "write must set ok=True")
        _require(data.get("dry_run") is False, "write must set dry_run=False")
        _require(bool(data.get("brief_path")), "brief_path must be non-empty")
        _require(data.get("files_read_count", 0) >= 1,
                 "must have read at least 1 file")

        brief_file = Path(data.get("brief_path", ""))
        _require(brief_file.exists(), f"brief file must exist: {brief_file}")
        content = brief_file.read_text(encoding="utf-8")
        _require("Code Research Brief" in content,
                 "brief must contain title")
        _require("python3 link.py growth code-brief-propose" in content,
                 "brief must suggest code-brief-propose command")
        _require("python3 link.py growth archive-mine" not in content,
                 "brief must not suggest archive-mine command")
        _require("archive-code-brief" in content,
                 "brief must mention archive-code-brief")
        next_cmds = data.get("next_commands", [])
        _require(next_cmds and "code-brief-propose --source" in next_cmds[0],
                 "archive-code-brief next command must route to code-brief-propose")

        # Architecture signals should be detected
        _require("agent" in content.lower() or "Agent" in content,
                 "brief should detect agent patterns")
        _require("Tool" in content or "tool" in content.lower(),
                 "brief should detect tool patterns")

        # Verify Growth Upgrade Candidates section with structured blocks
        _require("## Growth Upgrade Candidates" in content,
                 "brief must include Growth Upgrade Candidates section")
        _require("### UPGRADE CANDIDATE:" in content,
                 "brief must include at least one UPGRADE CANDIDATE block")
        _require("**Problem:**" in content,
                 "candidate block must include Problem field")
        _require("**Evidence from source:**" in content,
                 "candidate block must include Evidence from source field")
        _require("**Pattern observed:**" in content,
                 "candidate block must include Pattern observed field")
        _require("**Proposed Link upgrade:**" in content,
                 "candidate block must include Proposed Link upgrade field")
        _require("**Risk level:**" in content,
                 "candidate block must include Risk level field")
        _require("**Acceptance test idea:**" in content,
                 "candidate block must include Acceptance test idea field")

        # Verify no proposals were written
        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0, "archive-code-brief must not write proposal files")

    print("growth archive-code-brief write OK")


# ---------------------------------------------------------------------------
# 49. Growth code-brief-propose -- parses brief blocks into proposals
# ---------------------------------------------------------------------------

def check_growth_code_brief_propose() -> None:
    """code-brief-propose parses candidate blocks, dry-runs, writes, and JSON-renders."""
    import contextlib
    import io
    from link_core.control_plane import validate_proposal
    from link_modes.growth.link_growth_console import (
        code_brief_propose_main,
        collect_code_brief_propose,
    )

    brief_text = """# Code Research Brief: sample

## Growth Upgrade Candidates

### UPGRADE CANDIDATE: Add branch traceability receipts

**Problem:**
Link lacks source-grounded branch lineage receipts.

**Evidence from source:**
- `branch.ts`
Transcript copy logic records branch metadata.

**Pattern observed:**
Session branching with transcript preservation.

**Proposed Link upgrade:**
Add a branch lineage receipt that records parent session and fork point.

**Likely Link files or subsystem:**
link_core/context/

**Risk level:**
low

**Acceptance test idea:**
Create a fork and verify the receipt records parent session metadata.

### UPGRADE CANDIDATE: Add profile-gated tool routing

**Problem:**
Workers can see tool metadata but routing lacks a mandatory pre-dispatch profile gate.

**Evidence from source:**
- `router.ts`
Command routing maps names to handlers.

**Pattern observed:**
Command router with lazy handler loading.

**Proposed Link upgrade:**
Check the profile tool gate before dispatching registered tools.

**Likely Link files or subsystem:**
link_tool_registry.py
link_profile_gate.py

**Risk level:**
medium

**Acceptance test idea:**
Attempt a restricted tool call and verify the gate returns deny before execution.

---

## Possible Link Upgrade Ideas

- This trailing section must not leak into candidate fields.
"""

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        brief = root / "research/_catalog/code_briefs/sample.md"
        brief.parent.mkdir(parents=True)
        brief.write_text(brief_text, encoding="utf-8")

        data = collect_code_brief_propose(str(brief), write=False, root=td)
        _require(data.get("ok") is True, "dry-run must set ok=True")
        _require(data.get("source_exists") is True, "source must exist")
        _require(data.get("candidate_count") == 2,
                 f"must parse 2 candidates, got {data.get('candidate_count')}")
        _require(data.get("proposal_count") == 2,
                 f"must create 2 proposals, got {data.get('proposal_count')}")
        _require(data.get("dry_run") is True, "default must be dry_run=True")
        _require(data.get("written_paths") == [], "dry-run must not write paths")
        _require(data.get("quality_warnings") == [],
                 "valid candidates must not emit quality warnings")
        _require(data.get("weak_candidate_count") == 0,
                 "valid candidates must have weak_candidate_count=0")
        _require(data.get("duplicate_count") == 0,
                 "valid candidates must have duplicate_count=0")

        prop_dir = root / ".agents/control_plane/proposals"
        p_files = list(prop_dir.glob("*.json")) if prop_dir.exists() else []
        _require(len(p_files) == 0, "dry-run must not write proposal files")

        proposals = data.get("proposals", [])
        _require(proposals[0]["title"] == "Add branch traceability receipts",
                 "first proposal title must come from heading")
        _require(proposals[0]["risk_level"] == "low",
                 "first proposal risk must be low")
        _require(proposals[0]["recommendation"] == "accept",
                 "low risk proposal must recommend accept")
        _require(proposals[1]["risk_level"] == "medium",
                 "second proposal risk must be medium")
        _require(proposals[1]["recommendation"] == "review",
                 "medium risk proposal must recommend review")
        second_acceptance = proposals[1]["verification_commands"][0]
        _require("Possible Link Upgrade Ideas" not in second_acceptance,
                 "trailing markdown section must not leak into acceptance test")
        _require("trailing section" not in second_acceptance,
                 "trailing markdown body must not leak into acceptance test")

        for proposal in proposals:
            validate_proposal(proposal)
            _require(proposal["status"] == "pending", "status must be pending")
            _require(str(brief) in proposal["source_path"],
                     "source_path must include the brief path")
            _require(str(brief) in proposal.get("source_reference", ""),
                     "source_reference must include the brief path")
            _require(bool(proposal["source_summary"]),
                     "proposal must include source_summary")
            _require(bool(proposal["verification_commands"]),
                     "proposal must include acceptance test as verification command")

        json_out = io.StringIO()
        with contextlib.redirect_stdout(json_out):
            rc = code_brief_propose_main([
                "--source", str(brief), "--json", "--root", td,
            ])
        _require(rc == 0, f"--json command must return 0, got {rc}")
        rendered = json.loads(json_out.getvalue())
        _require(rendered.get("proposal_count") == 2,
                 "--json output must contain 2 proposals")
        _require(isinstance(rendered.get("quality_warnings"), list),
                 "--json output must include quality_warnings list")
        _require(rendered.get("weak_candidate_count") == 0,
                 "--json output must include weak_candidate_count")
        _require(rendered.get("duplicate_count") == 0,
                 "--json output must include duplicate_count")
        for proposal in rendered.get("proposals", []):
            _require(proposal.get("duplicate_existing") is False,
                     "--json proposals must include duplicate_existing=False")

        weak = root / "research/_catalog/code_briefs/weak.md"
        weak.write_text(
            "# Code Research Brief: weak\n\n"
            "### UPGRADE CANDIDATE: Weak acceptance\n\n"
            "**Problem:**\nNeeds a better proposal gate.\n\n"
            "**Evidence from source:**\n- `gate.md` mentions weak candidates.\n\n"
            "**Pattern observed:**\nQuality checks before writes.\n\n"
            "**Proposed Link upgrade:**\nWarn before writing weak proposals.\n\n"
            "**Likely Link files or subsystem:**\nlink_modes/growth/link_growth_console.py\n\n"
            "**Risk level:**\nlow\n\n"
            "**Acceptance test idea:**\n\n"
            "### UPGRADE CANDIDATE: Vague likely files\n\n"
            "**Problem:**\nWeak proposals lack file targeting.\n\n"
            "**Evidence from source:**\n- `files.md` records vague targeting.\n\n"
            "**Pattern observed:**\nFile targeting previews.\n\n"
            "**Proposed Link upgrade:**\nWarn about vague file targeting.\n\n"
            "**Likely Link files or subsystem:**\nruntime\n\n"
            "**Risk level:**\nlow\n\n"
            "**Acceptance test idea:**\nVerify vague file targets emit a warning.\n",
            encoding="utf-8",
        )
        weak_data = collect_code_brief_propose(str(weak), root=td)
        weak_codes = {w.get("code") for w in weak_data.get("quality_warnings", [])}
        _require("weak_acceptance_test" in weak_codes,
                 "missing acceptance test must emit weak_acceptance_test warning")
        _require("weak_likely_files" in weak_codes,
                 "vague likely files must emit weak_likely_files warning")
        _require(weak_data.get("weak_candidate_count") == 2,
                 "two weak candidates must be counted")

        duplicate = root / "research/_catalog/code_briefs/duplicate.md"
        duplicate.write_text(brief_text.replace(
            "### UPGRADE CANDIDATE: Add profile-gated tool routing",
            "### UPGRADE CANDIDATE: Add branch traceability receipts",
        ), encoding="utf-8")
        duplicate_data = collect_code_brief_propose(str(duplicate), root=td)
        duplicate_codes = {w.get("code") for w in duplicate_data.get("quality_warnings", [])}
        _require("duplicate_candidate_title" in duplicate_codes,
                 "duplicate candidate titles must emit warning")
        _require(duplicate_data.get("duplicate_count", 0) >= 2,
                 "duplicate candidate titles must increase duplicate_count")

        existing_preview = collect_code_brief_propose(str(brief), root=td)
        existing_id = existing_preview["proposals"][0]["proposal_id"]
        prop_dir.mkdir(parents=True, exist_ok=True)
        (prop_dir / f"{existing_id}.json").write_text("{}", encoding="utf-8")
        existing_data = collect_code_brief_propose(str(brief), root=td)
        existing_codes = {w.get("code") for w in existing_data.get("quality_warnings", [])}
        _require("existing_proposal_id" in existing_codes,
                 "existing proposal_id must emit duplicate_existing warning")
        _require(existing_data["proposals"][0].get("duplicate_existing") is True,
                 "existing proposal must set duplicate_existing=True")
        _require(existing_data["candidates"][0].get("duplicate_existing") is True,
                 "existing candidate must set duplicate_existing=True")


        data_w = collect_code_brief_propose(str(brief), write=True, root=td)
        _require(data_w.get("dry_run") is False, "write=True must set dry_run=False")
        _require(len(data_w.get("written_paths", [])) == 2,
                 "--write must write 2 proposal files")
        for wp in data_w.get("written_paths", []):
            path = Path(wp)
            _require(path.exists(), f"written proposal must exist: {path}")
            _require(str(prop_dir) in str(path),
                     "written proposal must be under .agents/control_plane/proposals")

        missing = collect_code_brief_propose(str(root / "missing.md"), root=td)
        _require(missing.get("ok") is False, "missing source must set ok=False")
        _require(missing.get("source_exists") is False,
                 "missing source must set source_exists=False")
        _require(isinstance(missing.get("error"), str),
                 "missing source must include error string")

        empty = root / "research/_catalog/code_briefs/empty.md"
        empty.write_text("# Empty brief\nNo candidate blocks here.\n", encoding="utf-8")
        empty_data = collect_code_brief_propose(str(empty), root=td)
        _require(empty_data.get("ok") is True, "no-block source must be ok")
        _require(empty_data.get("candidate_count") == 0,
                 "no-block source must have 0 candidates")
        _require(empty_data.get("proposal_count") == 0,
                 "no-block source must have 0 proposals")
        _require("no upgrade candidate" in empty_data.get("error", "").lower(),
                 "no-block source must include clear error note")

    print("growth code-brief-propose OK")


# ---------------------------------------------------------------------------
# 56. Receipts make_unique_title helper
# ---------------------------------------------------------------------------

def check_make_unique_title() -> None:
    """make_unique_title produces deterministic unique titles."""
    from link_core.receipts import make_unique_title

    # Unique title is unchanged
    t1 = make_unique_title("add branch traceability", existing_titles=set())
    _require(t1 == "add branch traceability",
             f"unique title must be unchanged, got {t1!r}")

    # Duplicate title gets numeric suffix
    seen = {"add branch traceability"}
    t2 = make_unique_title("add branch traceability", existing_titles=seen)
    _require(t2 == "add branch traceability 2",
             f"duplicate title must get ' 2' suffix, got {t2!r}")

    # Second duplicate gets " 3"
    seen.add(" ".join(t2.split()).lower())
    t3 = make_unique_title("add branch traceability", existing_titles=seen)
    _require(t3 == "add branch traceability 3",
             f"second duplicate must get ' 3' suffix, got {t3!r}")

    # None title gets a timestamp-based fallback
    t_none = make_unique_title(None)
    _require(t_none.startswith("untitled-upgrade-"),
             f"None title must start with 'untitled-upgrade-', got {t_none!r}")

    # Empty title gets a timestamp-based fallback
    t_empty = make_unique_title("")
    _require(t_empty.startswith("untitled-upgrade-"),
             f"empty title must start with 'untitled-upgrade-', got {t_empty!r}")

    # Whitespace-only title gets a fallback
    t_ws = make_unique_title("   ")
    _require(t_ws.startswith("untitled-upgrade-"),
             f"whitespace-only title must get fallback, got {t_ws!r}")

    # Different casing is treated as collision
    seen2 = {"Add Branch Traceability"}
    t_case = make_unique_title("add branch traceability", existing_titles=seen2)
    _require(t_case == "add branch traceability 2",
             f"case-insensitive collision must get suffix, got {t_case!r}")

    # Title is returned unchanged when no set given
    t_no_set = make_unique_title("some brand new title")
    _require(t_no_set == "some brand new title",
             f"no set implies unique, got {t_no_set!r}")

    # High count of duplicates still works (tests hash fallback)
    full = set()
    for i in range(1, 101):
        full.add(f"overwhelmed {i}")
    t_many = make_unique_title("overwhelmed 5", existing_titles=full)
    _require(t_many.startswith("overwhelmed 5 "),
             f"hash fallback must keep original prefix, got {t_many!r}")

    print("make_unique_title OK")


# ---------------------------------------------------------------------------
# 57. Content replacement entry helper
# ---------------------------------------------------------------------------

def check_content_replacement_entry_helper() -> None:
    """Build, validate, and round-trip content replacement entries."""
    from link_core.receipts import (
        CONTENT_REPLACEMENT_VERSION,
        build_content_replacement_entry,
        content_replacement_entry_from_json,
        content_replacement_entry_to_json,
        validate_content_replacement_entry,
    )

    prev_hash = "a" * 64
    new_hash = "b" * 64

    # Full entry with all optional fields
    entry = build_content_replacement_entry(
        session_id="session-cr-001",
        previous_content_hash=prev_hash,
        replacement_content_hash=new_hash,
        created_at="2026-05-31T00:00:00Z",
        message_index=7,
        fork_point={"message_index": 7, "run_step": "planner"},
        reason="User edited content inline",
        source="content-regeneration",
        metadata={"tool": "unknown"},
    )

    _require(entry["session_id"] == "session-cr-001",
             "session_id must be preserved")
    _require(entry["previous_content_hash"] == prev_hash,
             "previous_content_hash must be preserved")
    _require(entry["replacement_content_hash"] == new_hash,
             "replacement_content_hash must be preserved")
    _require(entry["message_index"] == 7,
             "message_index must be preserved")
    _require(entry["reason"] == "User edited content inline",
             "reason must be preserved")
    _require(entry["source"] == "content-regeneration",
             "source must be preserved")
    _require(isinstance(entry["replacement_id"], str) and entry["replacement_id"].startswith("content-replacement-"),
             "replacement_id must have content-replacement prefix")
    _require(entry["fork_point"]["message_index"] == 7,
             "fork_point message_index must be preserved")

    # Stable JSON serialization
    encoded = content_replacement_entry_to_json(entry)
    _require(encoded == content_replacement_entry_to_json(entry),
             "content replacement JSON serialization must be stable")
    decoded = content_replacement_entry_from_json(encoded)
    _require(decoded == entry,
             "content replacement JSON round-trip must preserve data")

    # Minimal entry (only required fields)
    minimal = build_content_replacement_entry(
        session_id="session-cr-002",
        previous_content_hash=prev_hash,
        replacement_content_hash=new_hash,
        created_at="2026-05-31T00:00:01Z",
    )
    validate_content_replacement_entry(minimal)
    _require("message_index" not in minimal,
             "missing optional message_index should be absent")
    _require("reason" not in minimal,
             "missing optional reason should be absent")
    _require("source" not in minimal,
             "missing optional source should be absent")

    # Same hash must be rejected (no-op replacement)
    try:
        build_content_replacement_entry(
            session_id="session-cr-003",
            previous_content_hash=prev_hash,
            replacement_content_hash=prev_hash,
        )
    except ValueError as exc:
        _require("must differ" in str(exc).lower(),
                 "same hashes must be rejected with 'must differ'")
    else:
        raise AssertionError("identical hashes must be rejected")

    # Missing required field must be rejected
    try:
        validate_content_replacement_entry(
            {"replacement_id": "bad", "session_id": "s", "created_at": "t"}
        )
    except ValueError:
        pass
    else:
        raise AssertionError("missing required fields must be rejected")

    # Non-hex hash must be rejected
    try:
        build_content_replacement_entry(
            session_id="session-cr-004",
            previous_content_hash="not-a-hex-hash",
            replacement_content_hash=new_hash,
        )
    except ValueError as exc:
        _require("hex" in str(exc).lower(),
                 "non-hex hash must be rejected with 'hex' mention")
    else:
        raise AssertionError("non-hex hash must be rejected")

    print("content replacement entry helper OK")


# ---------------------------------------------------------------------------
# 58. Fork lineage with content replacements
# ---------------------------------------------------------------------------

def check_fork_lineage_with_content_replacements() -> None:
    """Fork lineage receipts accept optional content replacement entries."""
    from link_core.receipts import (
        build_content_replacement_entry,
        build_fork_lineage_receipt,
        fork_lineage_receipt_from_json,
        fork_lineage_receipt_to_json,
        validate_fork_lineage_receipt,
    )

    prev_hash = "a" * 64
    new_hash = "b" * 64
    prev_hash_2 = "c" * 64
    new_hash_2 = "d" * 64

    cr1 = build_content_replacement_entry(
        session_id="fork-cr-001",
        previous_content_hash=prev_hash,
        replacement_content_hash=new_hash,
        message_index=3,
        reason="edited by user",
        created_at="2026-05-31T00:00:00Z",
    )
    cr2 = build_content_replacement_entry(
        session_id="fork-cr-001",
        previous_content_hash=prev_hash_2,
        replacement_content_hash=new_hash_2,
        message_index=7,
        reason="content regeneration",
        created_at="2026-05-31T00:00:01Z",
    )

    receipt = build_fork_lineage_receipt(
        parent_session_id="parent-cr-001",
        child_session_id="child-cr-001",
        fork_point={"message_index": 10, "run_step": "planner"},
        fork_depth=2,
        diverged=True,
        content_replacements=[cr1, cr2],
        created_at="2026-05-31T00:00:02Z",
    )

    _require("content_replacements" in receipt,
             "receipt must have content_replacements field")
    crs = receipt["content_replacements"]
    _require(isinstance(crs, list) and len(crs) == 2,
             f"content_replacements must be list of 2, got {len(crs) if isinstance(crs, list) else type(crs)}")
    _require(crs[0]["replacement_id"] == cr1["replacement_id"],
             "first replacement_id must match input")
    _require(crs[0]["session_id"] == "fork-cr-001",
             "first session_id must match input")
    _require(crs[0]["message_index"] == 3,
             "first message_index must be preserved")
    _require(crs[1]["replacement_id"] == cr2["replacement_id"],
             "second replacement_id must match input")
    _require(crs[1]["reason"] == "content regeneration",
             "second reason must be preserved")

    # JSON round-trip for the combined receipt
    encoded = fork_lineage_receipt_to_json(receipt)
    _require(encoded == fork_lineage_receipt_to_json(receipt),
             "combined receipt JSON serialization must be stable")
    decoded = fork_lineage_receipt_from_json(encoded)
    _require(decoded == receipt,
             "combined receipt JSON round-trip must preserve data")
    _require(decoded["content_replacements"] == receipt["content_replacements"],
             "content_replacements must survive JSON round-trip")

    # Backward-compatible: no content_replacements
    no_cr = build_fork_lineage_receipt(
        parent_session_id="parent-cr-002",
        child_session_id="child-cr-002",
        created_at="2026-05-31T00:00:03Z",
    )
    _require("content_replacements" not in no_cr,
             "receipt without content_replacements must not have the field")
    validate_fork_lineage_receipt(no_cr)

    # content_replacements must be a list
    try:
        build_fork_lineage_receipt(
            parent_session_id="parent-cr-003",
            child_session_id="child-cr-003",
            content_replacements={"not": "a list"},  # type: ignore[arg-type]
        )
    except (TypeError, ValueError):
        pass
    else:
        raise AssertionError("non-list content_replacements must be rejected")

    print("fork lineage with content replacements OK")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main() -> None:
    check_fork_lineage_receipt_helper()
    check_transcript_snapshot_receipt_helper()
    check_growth_facade()
    check_upgrade_miner_candidates()
    check_research_archive_miner()
    check_approved_research_handoff_executor()
    check_self_learning_dashboard()
    check_control_plane_accepts_valid_proposal()
    check_bridge_produces_valid_proposal()
    check_bridge_rejects_bad_input()
    check_growth_propose_function()
    check_growth_console_data()
    check_growth_proposals_data()
    check_growth_propose_command()
    check_growth_approve_command()
    check_growth_reject_command()
    check_growth_approve_reject_missing_id()
    check_growth_handoff_dry_run()
    check_growth_handoff_write()
    check_growth_handoff_errors()
    check_growth_run_guide()
    check_growth_run_with_source()
    check_growth_run_smart_router()
    check_growth_handoffs_empty()
    check_growth_handoffs_populated()
    check_growth_execute_dry_run()
    check_growth_execute_write()
    check_growth_execute_errors()
    check_growth_receipts_empty()
    check_growth_receipts_populated()
    check_growth_finalize_command()
    check_growth_archive_inventory_empty()
    check_growth_archive_inventory_populated()
    check_growth_archive_extract_dry_run()
    check_growth_archive_extract_write()
    check_growth_archive_extract_blocked()
    check_growth_archive_catalog_dry_run()
    check_growth_archive_catalog_write()
    check_growth_archive_catalog_refuses_existing()
    check_growth_archive_queue_empty()
    check_growth_archive_queue_populated()
    check_growth_archive_queue_invalid_catalog()
    check_growth_archive_mine_dry_run_rank()
    check_growth_archive_mine_dry_run_source()
    check_growth_archive_mine_errors()
    check_growth_archive_batch_mine_dry_run()
    check_growth_archive_batch_mine_top_clamp()
    check_growth_archive_batch_mine_partial_failure()
    check_growth_archive_code_queue_empty()
    check_growth_archive_code_queue_populated()
    check_growth_archive_code_queue_top_clamp()
    check_growth_code_brief_propose_batch()
    check_ruflo_upgrade_intake_helper()
    check_ruflo_upgrade_plan_helper()
    check_self_learning_feedback_receipt_helper()
    check_self_learning_next_step_recommendations_helper()
    check_repo_value_scan_helper()
    check_link_capability_inventory_helper()
    check_capability_gap_preview_helper()
    check_growth_planning_preview_helper()
    check_capability_graph_helper()
    check_capability_evidence_graph_helper()
    check_capability_discovery_helper()
    check_capability_intelligence_payload_helper()
    check_upgrade_execution_plan_helper()
    check_implementation_branch_plan_helper()
    check_implementation_work_packages_helper()
    check_verification_plan_helper()
    check_verified_patch_plan_helper()
    check_verified_patch_diff_helper()
    check_patch_applier_boundary_helper()
    check_patch_behavior_quality_gate_helper()
    check_autonomous_execution_package_helper()
    check_growth_planning_chain_cli()
    check_growth_execution_readiness_cli()
    check_growth_execution_gates_cli()
    check_growth_execution_approval_checklist_cli()
    check_growth_execution_review_cli()
    check_workspace_creator_runtime_boundary_helper()
    check_growth_workspace_boundary_cli()
    check_growth_patch_boundary_cli()
    check_workspace_creator_runtime_plan_helper()
    check_guarded_workspace_creator_runtime_component()
    check_guarded_patch_applier_runtime_component()
    check_verification_runner_boundary_helper()
    check_growth_verification_boundary_cli()
    check_guarded_verification_runner_runtime_component()
    check_guarded_workspace_lifecycle_cleanup_abandon()
    check_planning_chain_review_bundle_helper()
    check_execution_readiness_stack_helper()
    check_execution_journal_schema_helper()
    check_execution_evidence_contract_helper()
    check_execution_preflight_checklist_helper()
    check_execution_attempt_history_helper()
    check_execution_readiness_dashboard_summary_helper()
    check_execution_gate_stack_preview_helper()
    check_growth_archive_code_brief_dry_run()
    check_growth_archive_code_brief_write()
    check_growth_code_brief_propose()
    check_make_unique_title()
    check_content_replacement_entry_helper()
    check_fork_lineage_with_content_replacements()
    print("Growth pipeline smoke tests passed")


if __name__ == "__main__":
    main()
