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
                "accepted_proposal_ids", "next_action", "commands",
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

    with tempfile.TemporaryDirectory() as td:
        write_proposal(_sample_control_plane_proposal("router-accepted-001", "accepted"), root=td)
        data = collect_run_data(root=td)
        commands = "\n".join(data.get("commands", []))
        _require(data.get("pipeline_stage") == "PatchWorker",
                 "accepted proposal must route to PatchWorker")
        _require("growth handoff router-accepted-001 --write" in commands,
                 "accepted proposal must recommend handoff for the accepted id")

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
            "export { runFooCommand } from './run';\n"
            "export { fooSchema } from './schema';\n",
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

        # Verify skipped contains node_modules
        skipped = data.get("skipped_entries", [])
        node_skipped = [s for s in skipped if "node_modules" in s.get("path", "")]
        _require(len(node_skipped) >= 1, "node_modules file must be skipped")

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
# 47. Growth archive-code-brief -- dry-run
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
# main
# ---------------------------------------------------------------------------

def main() -> None:
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
    check_growth_archive_code_brief_dry_run()
    check_growth_archive_code_brief_write()
    check_growth_code_brief_propose()
    print("Growth pipeline smoke tests passed")


if __name__ == "__main__":
    main()
