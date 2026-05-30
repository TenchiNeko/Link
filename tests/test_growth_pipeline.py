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
# 20. Growth handoffs -- empty state
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
    check_growth_handoffs_empty()
    check_growth_handoffs_populated()
    print("Growth pipeline smoke tests passed")


if __name__ == "__main__":
    main()
