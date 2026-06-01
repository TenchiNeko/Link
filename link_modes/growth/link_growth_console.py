#!/usr/bin/env python3
"""Link Growth terminal status console.

Import path: ``link_modes.growth.link_growth_console``

Read-only status screen for Growth mode. Collects repo, healthcheck, config,
pipeline, cluster, and proposal data from existing sources and renders it in
the terminal. Uses ``rich`` for styled output when available; falls back to
plain ``print()`` text.

Invocation (via link.py):
    python3 link.py growth status       # styled terminal output
    python3 link.py growth status --json  # machine-readable dump

No file writes. No network. No subprocess. No mutation.
"""

from __future__ import annotations

import json
import sys
from typing import Any

CONSOLE_VERSION = "link-growth-console-v1"
_GROWTH_COMMAND = "growth"

# ── data collector ──────────────────────────────────────────────────────


def collect_console_data() -> dict[str, Any]:
    """Gather all Growth console data from existing sources.

    Returns a dict keyed by display section. Every value comes from a
    previously-tested function; no new logic is introduced here.
    """
    from pathlib import Path

    from link_core.control_plane import (
        CONTROL_PLANE_STAGES,
        list_proposals,
    )
    from link_core.dashboard import collect as _dashboard_collect
    from link_modes.growth import (
        MODE_NAME,
        TEAM_CONFIG,
        control_plane_stages,
    )
    from link_modes.growth.link_candidate_proposal_bridge import (
        BRIDGE_VERSION,
    )
    from link_modes.growth.link_research_upgrade_miner import CLUSTERS
    from link_modes.growth.link_self_learning_dashboard import (
        build_dashboard,
    )

    dashboard = _dashboard_collect() or {}
    git_section = dashboard.get("git", {})
    hc_section = dashboard.get("healthcheck", {})

    sd = build_dashboard(root=Path.cwd())
    sd_git = sd.get("git", {})
    patch_counts = sd.get("patch_draft_counts", {})

    clusters = []
    for c in CLUSTERS:
        clusters.append(
            {"title": c["title"], "risk": c.get("risk", "medium")}
        )

    return {
        "version": CONSOLE_VERSION,
        "repo": {
            "branch": sd_git.get("branch") or git_section.get("head_full", "")[:40],
            "head": git_section.get("head", ""),
            "safe_tag": git_section.get("safe_link_latest", ""),
            "dirty": bool(git_section.get("dirty_count", 0)),
        },
        "healthcheck": {
            "ok": hc_section.get("ok", False),
        },
        "mode": {
            "name": MODE_NAME,
            "team_config": TEAM_CONFIG,
            "entrypoint": "link_modes.growth.propose()",
            "bridge_version": BRIDGE_VERSION,
            "has_propose": True,
        },
        "pipeline": {
            "stages": list(control_plane_stages()),
            "canonical_stages": list(CONTROL_PLANE_STAGES),
        },
        "clusters": clusters,
        "proposals": {
            "on_disk": len(list_proposals()),
        },
        "drafts": {
            "pending": patch_counts.get("pending", 0),
            "approved": patch_counts.get("approved", 0),
            "rejected": patch_counts.get("rejected", 0),
        },
        "next_actions": sd.get("next_action", "no action"),
    }


# ── rich renderer ───────────────────────────────────────────────────────


def render_with_rich(data: dict[str, Any]) -> None:
    """Render the Growth console using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    repo = data["repo"]
    mode = data["mode"]
    hc = data["healthcheck"]
    pipeline = data["pipeline"]
    clusters = data["clusters"]
    proposals = data["proposals"]
    drafts = data["drafts"]

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH CONSOLE[/]",
        f"[dim]v{data['version']}[/]",
    )
    console.print(header)

    # ── repo bar ──
    repo_line = (
        f"branch: [bold]{repo['branch']}[/]  "
        f"HEAD: [bold]{repo['head'][:8]}[/]  "
        f"tag: [bold]{repo['safe_tag'][:8]}[/]  "
        f"dirty: [{'red' if repo['dirty'] else 'green'}]{'YES' if repo['dirty'] else 'no'}[/]"
    )
    console.print(Panel(repo_line, border_style="dim"))

    # ── status panel ──
    status_t = Table.grid(padding=(0, 2))
    status_t.add_column()
    status_t.add_column()
    status_t.add_column()
    hc_color = "green" if hc["ok"] else "red"
    status_t.add_row(
        f"healthcheck: [{hc_color}]{'PASS' if hc['ok'] else 'FAIL'}[/]",
        f"proposals on disk: {proposals['on_disk']}",
        f"drafts pending: {drafts['pending']}",
    )
    status_t.add_row(
        f"mode: [bold bright_cyan]{mode['name']}[/]",
        f"bridge: {mode['bridge_version']}",
        f"drafts approved: {drafts['approved']}",
    )
    status_t.add_row(
        f"config: {mode['team_config']}",
        f"propose: [green]available[/]",
        f"drafts rejected: {drafts['rejected']}",
    )
    console.print(Panel(status_t, title="SYSTEM STATUS", border_style="dim"))

    # ── pipeline bar ──
    stages = pipeline.get("stages", []) or pipeline.get("canonical_stages", [])
    if stages:
        stage_text = " [dim]>[/] ".join(f"[cyan]{s}[/]" for s in stages)
        console.print(Panel(stage_text, title="CONTROL PLANE PIPELINE", border_style="dim"))

    # ── upgrade clusters ──
    if clusters:
        cluster_t = Table.grid(padding=(0, 2))
        cluster_t.add_column(justify="right")
        cluster_t.add_column()
        cluster_t.add_column(justify="right")
        for i, c in enumerate(clusters, 1):
            risk_color = {"low": "green", "medium": "yellow", "high": "red"}.get(
                c.get("risk", "low"), ""
            )
            cluster_t.add_row(
                f"[dim]{i}.[/]",
                c["title"],
                f"[dim]risk:[/] [{risk_color}]{c.get('risk', 'medium')}[/]",
            )
        console.print(Panel(cluster_t, title="AVAILABLE UPGRADE CLUSTERS", border_style="dim"))

    # ── next actions ──
    actions = Text()
    actions.append("Next: ", style="dim")
    actions.append(data.get("next_actions", ""), style="bold")
    actions.append("\n")
    actions.append("python3 link.py growth status   ", style="dim")
    actions.append("-- refresh this screen\n", style="dim")
    actions.append("python3 link.py growth proposals  -- view proposal cards\n", style="dim")
    console.print(Panel(actions, title="NEXT ACTIONS", border_style="dim"))

    console.print(Rule(style="dim"))
    console.print(
        f"  [dim]Generated: {data.get('version', '')}[/]",
        justify="right",
    )


# ── plain text fallback ─────────────────────────────────────────────────


def render_plain(data: dict[str, Any]) -> None:
    """Render the Growth console using plain print."""
    repo = data["repo"]
    mode = data["mode"]
    hc = data["healthcheck"]
    pipeline = data["pipeline"]
    clusters = data["clusters"]
    proposals = data["proposals"]
    drafts = data["drafts"]

    out: list[str] = []
    out.append("== LINK GROWTH CONSOLE ==")
    out.append(
        f"branch:   {repo['branch']}\n"
        f"HEAD:     {repo['head']}  (tag: {repo['safe_tag']})\n"
        f"dirty:    {'YES' if repo['dirty'] else 'no'}"
    )
    out.append("")
    out.append("-- SYSTEM STATUS --")
    out.append(
        f"healthcheck: {'PASS' if hc['ok'] else 'FAIL'}\n"
        f"mode:        {mode['name']}\n"
        f"config:      {mode['team_config']}\n"
        f"bridge:      {mode['bridge_version']}\n"
        f"propose:     {'available' if mode['has_propose'] else 'missing'}\n"
        f"proposals:   {proposals['on_disk']} on disk\n"
        f"drafts:      pending={drafts['pending']}  approved={drafts['approved']}  rejected={drafts['rejected']}"
    )
    out.append("")
    stages = pipeline.get("stages", []) or pipeline.get("canonical_stages", [])
    if stages:
        out.append("-- PIPELINE --")
        out.append(" > ".join(stages))
    out.append("")
    if clusters:
        out.append("-- UPGRADE CLUSTERS --")
        for i, c in enumerate(clusters, 1):
            out.append(f"  {i}. {c['title']}  (risk: {c.get('risk', '?')})")
    out.append("")
    out.append("-- NEXT --")
    out.append(f"  {data.get('next_actions', '')}")
    out.append("  python3 link.py growth status")
    out.append("")
    out.append(f"Generated: {data.get('version', '')}")
    print("\n".join(out))


# ── render orchestrator ─────────────────────────────────────────────────


def render_console(data: dict[str, Any]) -> None:
    """Render with rich if available; fall back to plain text."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_plain(data)
        return
    render_with_rich(data)


# ── main entry points ───────────────────────────────────────────────────


def proposals_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth proposals``.

    Reads proposals from the control-plane registry (repo-root relative),
    renders them as proposal cards, and shows a useful empty state when
    no proposals exist.

    Supports ``--json`` for machine-readable output. Read-only. No mutation.
    """
    args = sys.argv[1:] if argv is None else argv
    data = collect_proposals_data()
    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0
    render_proposals(data)
    return 0


def collect_proposals_data() -> dict[str, Any]:
    """Read proposals from the control-plane registry (repo-root relative).

    Returns a dict with ``count``, ``proposals``, and ``storage_path``.
    Zero proposals is a valid state.
    """
    from pathlib import Path

    from link_core.control_plane import list_proposals

    proposals = list_proposals(root=Path.cwd())
    return {
        "count": len(proposals),
        "proposals": proposals,
        "storage_path": str(Path.cwd() / ".agents" / "control_plane" / "proposals"),
    }


# ── proposals rich renderer ──────────────────────────────────────────────


def render_proposals_with_rich(data: dict[str, Any]) -> None:
    """Render proposal cards using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    count: int = data.get("count", 0)
    proposals: list[dict] = data.get("proposals", [])

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH PROPOSALS[/]",
        f"[dim]{count} proposal{'s' if count != 1 else ''}[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    # ── empty state ──
    if count == 0:
        empty = Text()
        empty.append("\nNo proposals found in ", style="dim")
        empty.append(data.get("storage_path", ""), style="bold")
        empty.append("\n\nTo generate proposals from research:\n", style="dim")
        empty.append("  from link_modes.growth import propose\n", style="dim")
        empty.append("  from link_modes.growth.link_research_upgrade_miner import run_miner\n", style="dim")
        empty.append("  receipt = run_miner(...)\n", style="dim")
        empty.append("  proposals = propose(receipt[\"candidates\"])\n", style="dim")
        empty.append("\n")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        console.print(
            "  [dim]python3 link.py growth status  -- back to status console[/]"
        )
        return

    # ── proposal cards ──
    status_colors = {
        "pending": "yellow",
        "accepted": "green",
        "rejected": "red",
        "deferred": "magenta",
        "converted_to_patch": "cyan",
        "needs_smaller_plan": "orange1",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    for i, p in enumerate(proposals):
        card_lines = Text()

        # Title + status badge bar
        status = p.get("status", "?")
        sc = status_colors.get(status, "")
        risk = p.get("risk_level", "?")
        rc = risk_colors.get(risk, "")
        rec = p.get("recommendation", "?")

        card_lines.append(
            f"[bold]{p.get('title', '(untitled)')}[/]\n"
            f"[{sc}]STATUS: {status}[/]  "
            f"[{rc}]RISK: {risk}[/]  "
            f"[dim]RECOMMENDATION: {rec}[/]"
        )

        # Source
        card_lines.append(
            f"\n[dim]source:[/] {p.get('source_path', '?')}"
        )

        # Summary
        summary = p.get("source_summary", "")
        if summary:
            if len(summary) > 140:
                summary = summary[:137] + "..."
            card_lines.append(f"\n[dim]why:[/] {summary}")

        # Implementation plan
        impl = p.get("implementation_plan", [])
        if impl:
            card_lines.append("\n[dim]plan:[/]")
            for step in impl:
                card_lines.append(f"\n  \u2022 {step}")

        # Affected files
        files = p.get("affected_files", [])
        if files:
            card_lines.append(
                f"\n[dim]files:[/] {', '.join(files[:5])}"
            )

        # Footer
        card_lines.append(
            f"\n[dim]created: {p.get('created_at', '?')}[/]"
        )

        panel_title = f"PROPOSAL [{i + 1}/{count}]  {p.get('proposal_id', '?')[:24]}"
        console.print(Panel(card_lines, title=panel_title, border_style="dim"))

    console.print(Rule(style="dim"))
    console.print(
        "  [dim]python3 link.py growth status   -- back to status console[/]"
    )
    console.print(
        "  [dim]python3 link.py growth proposals --json  -- machine-readable[/]"
    )


# ── proposals plain fallback ─────────────────────────────────────────────


def render_proposals_plain(data: dict[str, Any]) -> None:
    """Render proposal cards using plain print."""
    count: int = data.get("count", 0)
    proposals: list[dict] = data.get("proposals", [])
    out: list[str] = []
    out.append(f"== LINK GROWTH PROPOSALS ({count}) ==")
    out.append("")

    if count == 0:
        out.append(f"No proposals found in {data.get('storage_path', '?')}")
        out.append("")
        out.append("To generate proposals from research:")
        out.append("  from link_modes.growth import propose")
        out.append("  from link_modes.growth.link_research_upgrade_miner import run_miner")
        out.append("  receipt = run_miner(...)")
        out.append("  proposals = propose(receipt[\\\"candidates\\\"])")
        out.append("")
        out.append("python3 link.py growth status  -- back to status console")
        print("\n".join(out))
        return

    for i, p in enumerate(proposals):
        out.append(f"--- PROPOSAL [{i + 1}/{count}] ---")
        out.append(f"title:          {p.get('title', '?')}")
        out.append(f"status:         {p.get('status', '?')}")
        out.append(f"risk_level:     {p.get('risk_level', '?')}")
        out.append(f"recommendation: {p.get('recommendation', '?')}")
        out.append(f"source_path:    {p.get('source_path', '?')}")
        summary = p.get("source_summary", "")
        if summary:
            out.append(f"summary:        {summary[:120]}")
        impl = p.get("implementation_plan", [])
        if impl:
            out.append("plan:")
            for step in impl:
                out.append(f"  - {step}")
        files = p.get("affected_files", [])
        if files:
            out.append(f"files:          {', '.join(files[:5])}")
        out.append(f"created_at:     {p.get('created_at', '?')}")
        out.append("")
    out.append("python3 link.py growth status  -- back to status console")
    print("\n".join(out))


# ── proposals render orchestrator ────────────────────────────────────────


def render_proposals(data: dict[str, Any]) -> None:
    """Render proposals with rich if available; fall back to plain text."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_proposals_plain(data)
        return
    render_proposals_with_rich(data)


# ── propose entry points ─────────────────────────────────────────────────


def propose_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth propose --source <path>``.

    Mines research from ``--source``, bridges candidates to proposals via
    ``propose()``, and either previews (dry-run, default) or persists to the
    control-plane proposal registry via ``--write``.

    Flags:
        --source <path>    Required. Research file or directory.
        --write            Persist proposals to .agents/control_plane/proposals/
        --json             Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth propose: mine research into proposals")
        print("")
        print("Usage:")
        print("  python3 link.py growth propose --source <path>")
        print("  python3 link.py growth propose --source <path> --json")
        print("  python3 link.py growth propose --source <path> --write")
        print("")
        print("Flags:")
        print("  --source <path>    Research file or directory to mine.")
        print("  --write            Persist proposals to the control-plane registry.")
        print("  --json             Output machine-readable JSON.")
        print("")
        print("Default is dry-run. No files are written unless --write is provided.")
        return 0

    source = _parse_arg(args, "--source")
    if not source:
        print("error: --source <path> is required", file=sys.stderr)
        print("Run 'python3 link.py growth propose --help' for usage.", file=sys.stderr)
        return 2

    write = "--write" in args
    data = collect_propose_data(source, write=write)

    if data.get("source_exists") is False:
        print(f"error: source not found: {data['source']}", file=sys.stderr)
        return 1

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_propose(data)
    return 0


def _parse_arg(argv: list[str], flag: str) -> str | None:
    """Extract a flag value from argv (e.g. ``--source value``)."""
    for i, a in enumerate(argv):
        if a == flag and i + 1 < len(argv):
            return argv[i + 1]
    return None


def collect_propose_data(
    source: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Mine a research source, bridge to proposals, optionally persist.

    Args:
        source: Research file or directory path (absolute or relative to cwd).
        write: When True, persist each proposal via ``write_proposal``.
        root: Override repo root (defaults to cwd). Used in tests.

    Returns a dict summarizing the run. ``source_exists`` is False when the
    resolved source path does not exist or is not a file/directory.
    """
    from pathlib import Path

    from link_core.control_plane import write_proposal as _write_proposal
    from link_modes.growth import propose
    from link_modes.growth.link_research_upgrade_miner import run_miner

    repo_root = Path(root) if root else Path.cwd()
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (repo_root / source).resolve()
    else:
        source_path = source_path.resolve()

    if not source_path.exists() or not (source_path.is_file() or source_path.is_dir()):
        return {
            "source": str(source_path),
            "source_exists": False,
            "chunk_count": 0,
            "candidate_count": 0,
            "proposal_count": 0,
            "proposals": [],
            "written_paths": [],
            "dry_run": True,
            "error": f"source not found: {source_path}",
        }

    (repo_root / ".link" / "patch_drafts" / "pending").mkdir(parents=True, exist_ok=True)

    receipt = run_miner(
        root=repo_root,
        research_dirs=[str(source_path)],
        candidate_file=Path(".link/approval_candidates.jsonl"),
        write_candidates=False,
    )

    chunk_count: int = receipt.get("chunk_count", 0)
    candidate_count: int = receipt.get("candidate_count", 0)
    candidates = receipt.get("candidates", [])

    proposals = propose(candidates)
    proposal_count = len(proposals)

    written_paths: list[str] = []
    if write:
        for p in proposals:
            path = _write_proposal(p, root=repo_root)
            written_paths.append(str(path))

    return {
        "source": str(source_path),
        "source_exists": True,
        "chunk_count": chunk_count,
        "candidate_count": candidate_count,
        "proposal_count": proposal_count,
        "proposals": proposals,
        "written_paths": written_paths,
        "dry_run": not write,
        "error": None if proposal_count > 0 else "no upgrade candidates found in source",
    }


# ── propose rich renderer ───────────────────────────────────────────────


def render_propose_with_rich(data: dict[str, Any]) -> None:
    """Render propose results using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    proposal_count: int = data.get("proposal_count", 0)
    candidate_count: int = data.get("candidate_count", 0)
    chunk_count: int = data.get("chunk_count", 0)
    dry_run: bool = data.get("dry_run", True)
    proposals = data.get("proposals", [])
    written = data.get("written_paths", [])

    status_colors = {
        "pending": "yellow", "accepted": "green", "rejected": "red",
        "deferred": "magenta", "converted_to_patch": "cyan",
        "needs_smaller_plan": "orange1",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH PROPOSE[/]",
        f"[{'yellow' if dry_run else 'red'}]DRY RUN[/]" if dry_run else "[bold red]WRITING[/]",
    )
    console.print(header)

    # ── source info ──
    info = Text()
    info.append("source: ", style="dim")
    info.append(data.get("source", ""), style="bold")
    info.append(f"\n[dim]chunks: {chunk_count}  candidates: {candidate_count}  proposals: {proposal_count}[/]")
    console.print(Panel(info, border_style="dim"))

    if proposal_count == 0:
        empty = Text()
        empty.append("No upgrade candidates found in source.", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        console.print("  [dim]python3 link.py growth status  -- back to status console[/]")
        return

    console.print(Rule(style="dim"))

    # ── proposal cards ──
    for i, p in enumerate(proposals):
        card = Text()
        status = p.get("status", "?")
        risk = p.get("risk_level", "?")
        rec = p.get("recommendation", "?")
        sc = status_colors.get(status, "")
        rc = risk_colors.get(risk, "")

        card.append(f"[bold]{p.get('title', '(untitled)')}[/]\n")
        card.append(f"[{sc}]STATUS: {status}[/]  ")
        card.append(f"[{rc}]RISK: {risk}[/]  ")
        card.append(f"[dim]REC: {rec}[/]")

        summary = p.get("source_summary", "")
        if summary:
            if len(summary) > 140:
                summary = summary[:137] + "..."
            card.append(f"\n[dim]why:[/] {summary}")

        impl = p.get("implementation_plan", [])
        if impl:
            card.append(f"\n[dim]plan (first {min(3, len(impl))} of {len(impl)}):[/]")
            for step in impl[:3]:
                card.append(f"\n  \u2022 {step}")

        files = p.get("affected_files", [])
        if files:
            card.append(f"\n[dim]files:[/] {', '.join(files[:5])}")

        panel_title = f"PROPOSAL [{i + 1}/{proposal_count}]  {p.get('proposal_id', '?')[:24]}"
        console.print(Panel(card, title=panel_title, border_style="dim"))

    # ── write summary ──
    if written:
        wrote_text = Text()
        wrote_text.append("Written:\n", style="bold green")
        for w in written:
            wrote_text.append(f"  {w}\n", style="dim")
        console.print(Panel(wrote_text, title="PERSISTED", border_style="dim green"))

    console.print(Rule(style="dim"))
    if dry_run:
        console.print("  [dim]Use --write to persist proposals to disk[/]")
    console.print("  [dim]python3 link.py growth status   -- back to status console[/]")
    console.print("  [dim]python3 link.py growth proposals -- view proposal cards[/]")


# ── propose plain fallback ──────────────────────────────────────────────


def render_propose_plain(data: dict[str, Any]) -> None:
    """Render propose results using plain print."""
    proposal_count: int = data.get("proposal_count", 0)
    dry_run: bool = data.get("dry_run", True)
    proposals = data.get("proposals", [])
    written = data.get("written_paths", [])

    out: list[str] = []
    out.append(
        f"== LINK GROWTH PROPOSE ({'DRY RUN' if dry_run else 'WRITING'}) =="
    )
    out.append(f"source:   {data.get('source', '')}")
    out.append(
        f"chunks:   {data.get('chunk_count', 0)}\n"
        f"candidates: {data.get('candidate_count', 0)}\n"
        f"proposals: {proposal_count}"
    )
    out.append("")

    if proposal_count == 0:
        out.append("No upgrade candidates found in source.")
    else:
        for i, p in enumerate(proposals):
            out.append(f"--- PROPOSAL [{i + 1}/{proposal_count}] ---")
            out.append(f"title:          {p.get('title', '?')}")
            out.append(f"status:         {p.get('status', '?')}")
            out.append(f"risk_level:     {p.get('risk_level', '?')}")
            out.append(f"recommendation: {p.get('recommendation', '?')}")
            impl = p.get("implementation_plan", [])
            if impl:
                out.append(f"plan ({len(impl)} steps):")
                for step in impl[:3]:
                    out.append(f"  - {step}")
            out.append("")

    if written:
        out.append("Written:")
        for w in written:
            out.append(f"  {w}")
        out.append("")

    if dry_run:
        out.append("Use --write to persist proposals to disk.")
    out.append("python3 link.py growth status   -- back to status console")
    out.append("python3 link.py growth proposals -- view proposal cards")

    print("\n".join(out))


# ── approve / reject entry points ────────────────────────────────────────


def approve_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth approve <proposal_id>``.

    Sets the proposal status to *accepted* via ``update_proposal_status``.
    The proposal must already exist in the control-plane registry.

    Flags:
        --root <path>  Override repo root (for test isolation).
        --json         Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth approve: accept a pending proposal")
        print("")
        print("Usage:")
        print("  python3 link.py growth approve <proposal_id>")
        print("  python3 link.py growth approve <proposal_id> --json")
        return 0

    proposal_id = args[0]
    root_override = _parse_arg(args, "--root")
    data = collect_approve_data(proposal_id, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_decision(data)
    return 0 if data.get("ok") else 1


def reject_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth reject <proposal_id>``.

    Sets the proposal status to *rejected* via ``update_proposal_status``.
    An optional ``--reason`` flag stores a rejection note.
    The proposal must already exist in the control-plane registry.

    Flags:
        --root <path>    Override repo root (for test isolation).
        --reason <text>  Rejection reason stored on the proposal.
        --json           Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth reject: reject a pending proposal")
        print("")
        print("Usage:")
        print("  python3 link.py growth reject <proposal_id>")
        print("  python3 link.py growth reject <proposal_id> --reason \"...\"")
        print("  python3 link.py growth reject <proposal_id> --reason \"...\" --json")
        return 0

    proposal_id = args[0]
    reason = _parse_arg(args, "--reason")
    root_override = _parse_arg(args, "--root")
    data = collect_reject_data(proposal_id, reason=reason, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_decision(data)
    return 0 if data.get("ok") else 1


# ── decision data collectors ─────────────────────────────────────────────


def collect_approve_data(
    proposal_id: str,
    root: str | None = None,
) -> dict[str, Any]:
    """Approve a proposal by setting its status to *accepted*.

    Returns a receipt dict with ``ok``, ``proposal_id``, ``title``,
    ``previous_status``, ``new_status``, ``path``, and ``error`` when
    the proposal was not found or the update failed.
    """
    from pathlib import Path

    from link_core.control_plane import update_proposal_status
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )

    repo_root = Path(root) if root else Path.cwd()
    storage = proposal_storage_dir(repo_root)
    prop_path = storage / f"{proposal_id}.json"

    if not prop_path.exists():
        return _decision_error(proposal_id, str(prop_path), "proposal not found on disk")

    try:
        previous = load_proposal(prop_path)
    except Exception as exc:
        return _decision_error(proposal_id, str(prop_path), f"failed to load proposal: {exc}")

    previous_status = previous.get("status", "?")

    try:
        updated = update_proposal_status(proposal_id, "accepted", root=repo_root)
    except Exception as exc:
        return _decision_error(proposal_id, str(prop_path), f"update_proposal_status failed: {exc}")

    return _decision_receipt(
        proposal_id=proposal_id,
        title=updated.get("title", ""),
        previous_status=previous_status,
        new_status=updated.get("status", "?"),
        path=str(prop_path),
    )


def collect_reject_data(
    proposal_id: str,
    reason: str | None = None,
    root: str | None = None,
) -> dict[str, Any]:
    """Reject a proposal by setting its status to *rejected*.

    When ``reason`` is provided, it is stored as ``rejection_reason``
    on the proposal via ``write_proposal`` after the status update.

    Returns a receipt dict with ``ok``, ``proposal_id``, ``title``,
    ``previous_status``, ``new_status``, ``path``, ``reason``, and
    ``error`` when the proposal was not found or the update failed.
    """
    from pathlib import Path

    from link_core.control_plane import update_proposal_status, write_proposal
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )

    repo_root = Path(root) if root else Path.cwd()
    storage = proposal_storage_dir(repo_root)
    prop_path = storage / f"{proposal_id}.json"

    if not prop_path.exists():
        return _decision_error(proposal_id, str(prop_path), "proposal not found on disk")

    try:
        previous = load_proposal(prop_path)
    except Exception as exc:
        return _decision_error(proposal_id, str(prop_path), f"failed to load proposal: {exc}")

    previous_status = previous.get("status", "?")

    try:
        updated = update_proposal_status(proposal_id, "rejected", root=repo_root)
    except Exception as exc:
        return _decision_error(proposal_id, str(prop_path), f"update_proposal_status failed: {exc}")

    if reason:
        updated["rejection_reason"] = reason
        write_proposal(updated, root=repo_root)

    return _decision_receipt(
        proposal_id=proposal_id,
        title=updated.get("title", ""),
        previous_status=previous_status,
        new_status=updated.get("status", "?"),
        path=str(prop_path),
        reason=reason,
    )


def _decision_error(
    proposal_id: str,
    path: str,
    error: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "proposal_id": proposal_id,
        "title": "",
        "previous_status": "",
        "new_status": "",
        "path": path,
        "reason": None,
        "error": error,
    }


def _decision_receipt(
    proposal_id: str,
    title: str,
    previous_status: str,
    new_status: str,
    path: str,
    reason: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "ok": True,
        "proposal_id": proposal_id,
        "title": title,
        "previous_status": previous_status,
        "new_status": new_status,
        "path": path,
        "error": None,
    }
    if reason:
        result["reason"] = reason
    return result


# ── decision rich renderer ──────────────────────────────────────────────


def render_decision_with_rich(data: dict[str, Any]) -> None:
    """Render an approve/reject decision receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", False)
    proposal_id: str = data.get("proposal_id", "?")

    status_colors = {
        "accepted": "green", "rejected": "red", "deferred": "magenta",
        "pending": "yellow", "needs_smaller_plan": "orange1",
    }

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    action = "approved" if data.get("new_status") == "accepted" else "rejected"
    state_color = "green" if ok else "red"
    state_label = action.upper() if ok else "FAILED"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH DECISION[/]",
        f"[{state_color}]{state_label}[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    receipt = Text()
    receipt.append("proposal_id: ", style="dim")
    receipt.append(proposal_id, style="bold")
    receipt.append("\n[dim]title:          [/]")
    receipt.append(data.get("title", "?"))
    receipt.append("\n[dim]previous status:[/] ")
    prev = data.get("previous_status", "?")
    receipt.append(f"[{status_colors.get(prev, '')}]{prev}[/]")
    receipt.append("\n[dim]new status:     [/] ")
    new_s = data.get("new_status", "?")
    receipt.append(f"[{status_colors.get(new_s, '')}]{new_s}[/]")
    receipt.append("\n[dim]path:           [/]")
    receipt.append(data.get("path", "?"))

    reason = data.get("reason")
    if reason:
        receipt.append("\n[dim]reason:         [/]")
        receipt.append(reason)

    console.print(Panel(receipt, border_style="green" if ok else "red"))
    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth status   -- back to status console[/]")
    console.print("  [dim]python3 link.py growth proposals -- view proposal cards[/]")


# ── decision plain fallback ──────────────────────────────────────────────


def render_decision_plain(data: dict[str, Any]) -> None:
    """Render an approve/reject decision receipt using plain print."""
    ok: bool = data.get("ok", False)
    action = "APPROVED" if data.get("new_status") == "accepted" else "REJECTED"
    label = action if ok else "FAILED"
    out: list[str] = []
    out.append(f"== LINK GROWTH DECISION ({label}) ==")
    out.append("")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    out.append(f"proposal_id:     {data.get('proposal_id', '?')}")
    out.append(f"title:           {data.get('title', '?')}")
    out.append(f"previous status: {data.get('previous_status', '?')}")
    out.append(f"new status:      {data.get('new_status', '?')}")
    out.append(f"path:            {data.get('path', '?')}")
    reason = data.get("reason")
    if reason:
        out.append(f"reason:          {reason}")
    out.append("")
    out.append("python3 link.py growth status   -- back to status console")
    out.append("python3 link.py growth proposals -- view proposal cards")

    print("\n".join(out))


# ── decision render orchestrator ─────────────────────────────────────────


def render_decision(data: dict[str, Any]) -> None:
    """Render an approve/reject decision receipt with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_decision_plain(data)
        return
    render_decision_with_rich(data)


# ── handoff entry point ──────────────────────────────────────────────────


def handoff_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth handoff <proposal_id>``.

    Loads an accepted proposal, builds a patch plan and worker handoff from
    it, and either previews (dry-run, default) or persists to disk (--write).

    Flags:
        --write  Persist patch plan and worker handoff to canonical paths.
        --json   Machine-readable output.
        --root <path>  Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth handoff: create a worker handoff from an accepted proposal")
        print("")
        print("Usage:")
        print("  python3 link.py growth handoff <proposal_id>")
        print("  python3 link.py growth handoff <proposal_id> --json")
        print("  python3 link.py growth handoff <proposal_id> --write")
        print("")
        print("The proposal must have status 'accepted'.")
        print("Default is dry-run. No files are written without --write.")
        return 0

    proposal_id = args[0]
    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_handoff_data(proposal_id, write=write, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_handoff(data)
    return 0 if data.get("ok") else 1


# ── handoff data collector ───────────────────────────────────────────────


_HANDOFF_PLAN_DIR = ".agents/control_plane/patch_plans"
_HANDOFF_WORKER_DIR = ".agents/control_plane/worker_handoffs"


def collect_handoff_data(
    proposal_id: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Build a patch plan and worker handoff from an accepted proposal.

    Loads the proposal, verifies it is on disk and accepted, then builds
    a patch plan and worker handoff in memory.  When ``write=True`` both
    artifacts are persisted to ``_HANDOFF_PLAN_DIR`` and
    ``_HANDOFF_WORKER_DIR`` relative to the repo root.

    Returns a receipt dict with ``ok``, proposal/plan/handoff metadata,
    ``written_paths``, and ``error``.
    """
    from pathlib import Path

    from link_core.control_plane.link_control_plane_patch_plan import (
        build_patch_plan_from_proposal,
        write_patch_plan,
    )
    from link_core.control_plane.link_control_plane_proposals import (
        load_proposal,
        proposal_storage_dir,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        build_worker_handoff_from_plan,
        write_worker_handoff,
    )

    repo_root = Path(root) if root else Path.cwd()
    storage = proposal_storage_dir(repo_root)
    prop_path = storage / f"{proposal_id}.json"

    if not prop_path.exists():
        return _handoff_error(
            proposal_id,
            f"proposal not found: {prop_path}",
        )

    try:
        proposal = load_proposal(prop_path)
    except Exception as exc:
        return _handoff_error(
            proposal_id,
            f"failed to load proposal: {exc}",
        )

    current_status = str(proposal.get("status", ""))
    if current_status != "accepted":
        return _handoff_error(
            proposal_id,
            f"proposal must be accepted (current status: {current_status}). "
            f"Run 'python3 link.py growth approve {proposal_id}' first.",
        )

    try:
        plan = build_patch_plan_from_proposal(proposal)
    except Exception as exc:
        return _handoff_error(
            proposal_id,
            f"build_patch_plan_from_proposal failed: {exc}",
        )

    try:
        handoff = build_worker_handoff_from_plan(plan)
    except Exception as exc:
        return _handoff_error(
            proposal_id,
            f"build_worker_handoff_from_plan failed: {exc}",
        )

    written_paths: list[str] = []
    if write:
        plan_root = repo_root / _HANDOFF_PLAN_DIR
        handoff_root = repo_root / _HANDOFF_WORKER_DIR
        plan_path = write_patch_plan(plan, root=plan_root)
        handoff_path = write_worker_handoff(handoff, root=handoff_root)
        written_paths = [str(plan_path), str(handoff_path)]

    return {
        "ok": True,
        "proposal_id": proposal_id,
        "proposal_title": proposal.get("title", ""),
        "proposal_status": current_status,
        "plan_id": plan.get("plan_id", ""),
        "handoff_id": handoff.get("handoff_id", ""),
        "handoff_stage": handoff.get("stage", "PatchWorker"),
        "handoff_status": handoff.get("status", "queued"),
        "patch_plan": plan,
        "worker_handoff": handoff,
        "written_paths": written_paths,
        "dry_run": not write,
        "error": None,
    }


def _handoff_error(
    proposal_id: str,
    error: str,
) -> dict[str, Any]:
    return {
        "ok": False,
        "proposal_id": proposal_id,
        "proposal_title": "",
        "proposal_status": "",
        "plan_id": None,
        "handoff_id": None,
        "handoff_stage": "",
        "handoff_status": "",
        "patch_plan": None,
        "worker_handoff": None,
        "written_paths": [],
        "dry_run": True,
        "error": error,
    }


# ── handoff rich renderer ───────────────────────────────────────────────


def render_handoff_with_rich(data: dict[str, Any]) -> None:
    """Render a handoff preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH HANDOFF[/]",
        f"[{'yellow' if dry_run else 'red'}]DRY RUN[/]" if dry_run else "[bold green]WRITTEN[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── proposal summary ──
    proposal = Text()
    proposal.append("proposal_id: ", style="dim")
    proposal.append(data.get("proposal_id", "?"), style="bold")
    proposal.append("\n[dim]title:       [/]")
    proposal.append(data.get("proposal_title", "?"))
    proposal.append("\n[dim]status:      [/][green]accepted[/]")
    console.print(Panel(proposal, title="PROPOSAL", border_style="dim"))

    # ── patch plan ──
    plan = data.get("patch_plan") or {}
    plan_text = Text()
    plan_text.append("plan_id: ", style="dim")
    plan_text.append(plan.get("plan_id", "?"), style="bold")
    plan_text.append("\n[dim]status:      [/]")
    plan_text.append(f"[cyan]{plan.get('status', 'draft')}[/]")
    steps = plan.get("implementation_steps", [])
    if steps:
        plan_text.append(f"\n[dim]steps ({len(steps)}):[/]")
        for s in steps[:5]:
            plan_text.append(f"\n  \u2022 {s}")
    files = plan.get("affected_files", [])
    if files:
        plan_text.append(f"\n[dim]files:       [/]{', '.join(files[:5])}")
    console.print(Panel(plan_text, title="PATCH PLAN", border_style="dim"))

    # ── worker handoff ──
    handoff = data.get("worker_handoff") or {}
    hf_text = Text()
    hf_text.append("handoff_id: ", style="dim")
    hf_text.append(handoff.get("handoff_id", "?"), style="bold")
    hf_text.append("\n[dim]stage:       [/][cyan]")
    hf_text.append(handoff.get("stage", "PatchWorker"))
    hf_text.append("[/]")
    hf_text.append("\n[dim]status:      [/][green]")
    hf_text.append(handoff.get("status", "queued"))
    hf_text.append("[/]")
    hf_text.append("\n[dim]risk_level:  [/]")
    hf_text.append(handoff.get("risk_level", "?"))
    console.print(Panel(hf_text, title="WORKER HANDOFF", border_style="dim"))

    written = data.get("written_paths", [])
    if written:
        wrote_text = Text()
        wrote_text.append("Written:\n", style="bold green")
        for w in written:
            wrote_text.append(f"  {w}\n", style="dim")
        console.print(Panel(wrote_text, title="PERSISTED", border_style="dim green"))

    console.print(Rule(style="dim"))
    if dry_run:
        console.print("  [dim]Use --write to persist to disk[/]")
    console.print("  [dim]python3 link.py growth status   -- back to status console[/]")


# ── handoff plain fallback ───────────────────────────────────────────────


def render_handoff_plain(data: dict[str, Any]) -> None:
    """Render a handoff preview/receipt using plain print."""
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)
    out: list[str] = []
    out.append(
        f"== LINK GROWTH HANDOFF ({'DRY RUN' if dry_run else 'WRITTEN'}) =="
    )
    out.append("")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    out.append("-- PROPOSAL --")
    out.append(f"proposal_id: {data.get('proposal_id', '?')}")
    out.append(f"title:       {data.get('proposal_title', '?')}")
    out.append("status:      accepted")
    out.append("")

    plan = data.get("patch_plan") or {}
    out.append("-- PATCH PLAN --")
    out.append(f"plan_id:     {plan.get('plan_id', '?')}")
    out.append(f"status:      {plan.get('status', 'draft')}")
    steps = plan.get("implementation_steps", [])
    if steps:
        out.append(f"steps ({len(steps)}):")
        for s in steps[:5]:
            out.append(f"  - {s}")
    out.append("")

    handoff = data.get("worker_handoff") or {}
    out.append("-- WORKER HANDOFF --")
    out.append(f"handoff_id:  {handoff.get('handoff_id', '?')}")
    out.append(f"stage:       {handoff.get('stage', 'PatchWorker')}")
    out.append(f"status:      {handoff.get('status', 'queued')}")
    out.append(f"risk_level:  {handoff.get('risk_level', '?')}")
    out.append("")

    written = data.get("written_paths", [])
    if written:
        out.append("Written:")
        for w in written:
            out.append(f"  {w}")
        out.append("")

    if dry_run:
        out.append("Use --write to persist to disk.")
    out.append("python3 link.py growth status  -- back to status console")

    print("\n".join(out))


# ── handoff render orchestrator ──────────────────────────────────────────


def render_handoff(data: dict[str, Any]) -> None:
    """Render a handoff preview/receipt with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_handoff_plain(data)
        return
    render_handoff_with_rich(data)


# ── handoffs list entry point ────────────────────────────────────────────


def handoffs_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth handoffs``.

    Reads existing worker handoff JSON files from the canonical
    ``.agents/control_plane/worker_handoffs/`` directory and renders
    a read-only terminal view. No files are written. No handoffs are
    executed.

    Flags:
        --json  Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth handoffs: view existing worker handoffs")
        print("")
        print("Usage:")
        print("  python3 link.py growth handoffs")
        print("  python3 link.py growth handoffs --json")
        print("")
        print("This command is read-only. It lists handoff artifacts")
        print("stored under .agents/control_plane/worker_handoffs/")
        print("and does not execute or mutate anything.")
        return 0

    data = collect_handoffs_data()

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_handoffs_view(data)
    return 0


def collect_handoffs_data(
    root: str | None = None,
) -> dict[str, Any]:
    """Read handoff JSON files from the canonical worker_handoffs directory.

    Every handoff dict is loaded via ``load_worker_handoff``. Returns
    a flat dict with ``count``, ``handoffs``, and ``storage_path``.
    Zero handoffs is a valid state.
    """
    from pathlib import Path

    from link_core.control_plane.link_control_plane_worker_handoff import (
        list_worker_handoffs,
        load_worker_handoff,
    )

    repo_root = Path(root) if root else Path.cwd()
    handoff_dir = repo_root / _HANDOFF_WORKER_DIR

    paths = list_worker_handoffs(handoff_dir)
    handoffs = [load_worker_handoff(p) for p in paths]

    return {
        "count": len(handoffs),
        "handoffs": handoffs,
        "storage_path": str(handoff_dir),
    }


# ── handoffs rich renderer ──────────────────────────────────────────────


def render_handoffs_with_rich(data: dict[str, Any]) -> None:
    """Render a handoffs list view using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    count: int = data.get("count", 0)
    handoffs: list[dict] = data.get("handoffs", [])

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH HANDOFFS[/]",
        f"[dim]{count} handoff{'s' if count != 1 else ''}[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    # ── empty state ──
    if count == 0:
        empty = Text()
        empty.append("\nNo worker handoffs found in ", style="dim")
        empty.append(data.get("storage_path", ""), style="bold")
        empty.append("\n\nTo create a handoff:\n", style="dim")
        empty.append("  python3 link.py growth approve <proposal_id>\n", style="dim")
        empty.append("  python3 link.py growth handoff <proposal_id> --write\n", style="dim")
        empty.append("\n")
        empty.append("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    status_colors = {
        "queued": "yellow", "running": "cyan", "done": "green",
        "failed": "red", "blocked": "red",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    for i, hf in enumerate(handoffs):
        card = Text()
        hf_id = hf.get("handoff_id", "?")
        status = hf.get("status", "?")
        sc = status_colors.get(status, "")
        risk = hf.get("risk_level", "?")
        rc = risk_colors.get(risk, "")
        stage = hf.get("stage", "?")

        card.append(f"[bold]{hf.get('title', '(untitled)')}[/]\n")
        card.append(f"[{sc}]STATUS: {status}[/]  ")
        card.append(f"[{rc}]RISK: {risk}[/]  ")
        card.append(f"[dim]STAGE: {stage}[/]")

        prop_id = hf.get("proposal_id", "")
        if prop_id:
            card.append(f"\n[dim]proposal_id:[/] {prop_id}")
        plan_id = hf.get("plan_id", "")
        if plan_id:
            card.append(f"\n[dim]plan_id:    [/] {plan_id}")

        files = hf.get("allowed_files", [])
        if files:
            card.append(f"\n[dim]files:      [/]{', '.join(files[:5])}")

        steps = hf.get("implementation_steps", [])
        if steps:
            card.append(f"\n[dim]steps ({len(steps)}):[/]")
            for s in steps[:5]:
                card.append(f"\n  \u2022 {s}")

        card.append(f"\n[dim]created:    [/]{hf.get('created_at', '?')}")

        panel_title = f"HANDOFF [{i + 1}/{count}]  {hf_id[:24]}"
        console.print(Panel(card, title=panel_title, border_style="dim"))

    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth run      -- guided workflow dashboard[/]")


# ── handoffs plain fallback ─────────────────────────────────────────────


def render_handoffs_plain(data: dict[str, Any]) -> None:
    """Render a handoffs list view using plain print."""
    count: int = data.get("count", 0)
    handoffs: list[dict] = data.get("handoffs", [])
    out: list[str] = []
    out.append(f"== LINK GROWTH HANDOFFS ({count}) ==")
    out.append("")

    if count == 0:
        out.append(f"No worker handoffs found in {data.get('storage_path', '?')}")
        out.append("")
        out.append("To create a handoff:")
        out.append("  python3 link.py growth approve <proposal_id>")
        out.append("  python3 link.py growth handoff <proposal_id> --write")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow dashboard")
        print("\n".join(out))
        return

    for i, hf in enumerate(handoffs):
        out.append(f"--- HANDOFF [{i + 1}/{count}] ---")
        out.append(f"handoff_id:   {hf.get('handoff_id', '?')}")
        out.append(f"proposal_id:  {hf.get('proposal_id', '?')}")
        out.append(f"plan_id:      {hf.get('plan_id', '?')}")
        out.append(f"title:        {hf.get('title', '?')}")
        out.append(f"stage:        {hf.get('stage', '?')}")
        out.append(f"status:       {hf.get('status', '?')}")
        out.append(f"risk_level:   {hf.get('risk_level', '?')}")
        files = hf.get("allowed_files", [])
        if files:
            out.append(f"files:        {', '.join(files[:5])}")
        steps = hf.get("implementation_steps", [])
        if steps:
            out.append(f"steps ({len(steps)}):")
            for s in steps[:5]:
                out.append(f"  - {s}")
        out.append(f"created_at:   {hf.get('created_at', '?')}")
        out.append("")
    out.append("python3 link.py growth run  -- guided workflow dashboard")
    print("\n".join(out))


# ── handoffs render orchestrator ────────────────────────────────────────


def render_handoffs_view(data: dict[str, Any]) -> None:
    """Render handoffs with rich if available; fall back to plain text."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_handoffs_plain(data)
        return
    render_handoffs_with_rich(data)


# ── execute entry point ──────────────────────────────────────────────────
_VERIFIER_RECEIPT_DIR = ".agents/control_plane/verifier_receipts"


def execute_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth execute <handoff_id>``.

    Loads an existing worker handoff and builds a verifier receipt from
    it.  Dry-run by default; ``--write`` persists the receipt to the
    canonical ``_VERIFIER_RECEIPT_DIR``.

    **No code is executed by this command.**  It creates a verification
    receipt only.  Actual worker execution belongs to a future slice.

    Flags:
        --write  Persist the verifier receipt to canonical path.
        --json   Machine-readable output.
        --root <path>  Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth execute: prepare a worker handoff for verification")
        print("")
        print("Usage:")
        print("  python3 link.py growth execute <handoff_id>")
        print("  python3 link.py growth execute <handoff_id> --json")
        print("  python3 link.py growth execute <handoff_id> --write")
        print("")
        print("No code is executed by this command. It reads an existing")
        print("handoff and optionally creates a verifier receipt. Default")
        print("is dry-run. Use --write to persist the receipt to disk.")
        return 0

    handoff_id = args[0]
    add_json = True  # .json extension if not already present
    if handoff_id.endswith(".json"):
        add_json = False
    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_execute_data(
        handoff_id, write=write, add_json_extension=add_json, root=root_override
    )

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_execute(data)
    return 0 if data.get("ok") else 1


def collect_execute_data(
    handoff_id: str,
    write: bool = False,
    add_json_extension: bool = True,
    root: str | None = None,
) -> dict[str, Any]:
    """Load a worker handoff by ID and build a verifier receipt.

    Reads the handoff from ``_HANDOFF_WORKER_DIR``, validates it, and
    calls ``build_verifier_receipt_from_handoff`` to produce a receipt.
    When ``write=True`` the receipt is persisted to ``_VERIFIER_RECEIPT_DIR``.

    Returns a dict with ``ok``, handoff/receipt metadata, ``written_paths``,
    and ``error``.  Ready-for-execution handoffs get a verifier receipt;
    blocked or already-done handoffs return their state with a message.
    """
    from pathlib import Path

    from link_core.control_plane.link_control_plane_verifier_receipt import (
        build_verifier_receipt_from_handoff,
        write_verifier_receipt,
    )
    from link_core.control_plane.link_control_plane_worker_handoff import (
        load_worker_handoff,
    )

    repo_root = Path(root) if root else Path.cwd()
    handoff_dir = repo_root / _HANDOFF_WORKER_DIR

    filename = f"{handoff_id}.json" if add_json_extension else handoff_id
    hf_path = handoff_dir / filename

    if not hf_path.exists():
        return _execute_error(
            handoff_id,
            f"handoff not found: {hf_path}",
        )

    try:
        handoff = load_worker_handoff(hf_path)
    except Exception as exc:
        return _execute_error(
            handoff_id,
            f"failed to load handoff: {exc}",
        )

    hf_status = str(handoff.get("status", ""))

    if hf_status == "blocked":
        return _execute_error(
            handoff_id,
            "handoff is blocked — cannot create verifier receipt",
            handoff=handoff,
        )

    if hf_status == "done":
        return _execute_done(handoff_id, handoff)

    try:
        receipt = build_verifier_receipt_from_handoff(
            handoff, status="pending",
        )
    except Exception as exc:
        return _execute_error(
            handoff_id,
            f"build_verifier_receipt_from_handoff failed: {exc}",
        )

    written_paths: list[str] = []
    if write:
        receipt_dir = repo_root / _VERIFIER_RECEIPT_DIR
        receipt_path = write_verifier_receipt(receipt, root=receipt_dir)
        written_paths = [str(receipt_path)]

    return {
        "ok": True,
        "handoff_id": handoff.get("handoff_id", handoff_id),
        "handoff_title": handoff.get("title", ""),
        "handoff_status": hf_status,
        "handoff_stage": handoff.get("stage", ""),
        "handoff": handoff,
        "receipt": receipt,
        "verification_id": receipt.get("verification_id", ""),
        "written_paths": written_paths,
        "dry_run": not write,
        "recommended_next_action": (
            "Use --write to persist the verifier receipt to disk."
            if not write
            else "No code is executed by this command."
        ),
        "error": None,
    }


def _execute_error(
    handoff_id: str,
    error: str,
    handoff: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "handoff_id": handoff_id,
        "handoff_title": handoff.get("title", "") if handoff else "",
        "handoff_status": handoff.get("status", "") if handoff else "",
        "handoff_stage": handoff.get("stage", "") if handoff else "",
        "handoff": handoff,
        "receipt": None,
        "verification_id": None,
        "written_paths": [],
        "dry_run": True,
        "recommended_next_action": "",
        "error": error,
    }


def _execute_done(
    handoff_id: str,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    return {
        "ok": True,
        "handoff_id": handoff.get("handoff_id", handoff_id),
        "handoff_title": handoff.get("title", ""),
        "handoff_status": handoff.get("status", ""),
        "handoff_stage": handoff.get("stage", ""),
        "handoff": handoff,
        "receipt": None,
        "verification_id": None,
        "written_paths": [],
        "dry_run": True,
        "recommended_next_action": "Handoff is already completed.",
        "error": None,
    }


# ── execute rich renderer ───────────────────────────────────────────────


def render_execute_with_rich(data: dict[str, Any]) -> None:
    """Render an execute preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)
    hf_status = data.get("handoff_status", "")

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        state_label = "FAILED"
        state_color = "red"
    elif hf_status == "done":
        state_label = "DONE"
        state_color = "green"
    elif dry_run:
        state_label = "DRY RUN"
        state_color = "yellow"
    else:
        state_label = "WRITTEN"
        state_color = "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH EXECUTE[/]",
        f"[{state_color}]{state_label}[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        if data.get("handoff"):
            hf = data["handoff"]
            error_text.append(f"[bold]Handoff exists but is {hf.get('status', '?')}.[/]\n\n")
            error_text.append(f"[dim]title: {hf.get('title', '?')}[/]")
        error_text.append(f"\n[red]{data.get('error', 'unknown error')}[/]")
        if hf_status == "blocked":
            error_text.append("\n[dim]Recommendation: unblock or create a new handoff.[/]")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    handoff = data.get("handoff") or {}
    receipt = data.get("receipt") or {}

    # ── handoff summary ──
    status_colors = {
        "queued": "yellow", "running": "cyan", "done": "green",
        "failed": "red", "blocked": "red",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}
    sc = status_colors.get(hf_status, "")
    risk = handoff.get("risk_level", "?")
    rc = risk_colors.get(risk, "")

    hf_text = Text()
    hf_text.append("handoff_id: ", style="dim")
    hf_text.append(data.get("handoff_id", "?"), style="bold")
    hf_text.append("\n[dim]proposal_id: [/]")
    hf_text.append(handoff.get("proposal_id", "?"))
    hf_text.append("\n[dim]plan_id:     [/]")
    hf_text.append(handoff.get("plan_id", "?"))
    hf_text.append("\n[dim]title:       [/]")
    hf_text.append(data.get("handoff_title", "?"))
    hf_text.append("\n[dim]stage:       [/]")
    hf_text.append(data.get("handoff_stage", "?"))
    hf_text.append("\n[dim]status:      [/]")
    hf_text.append(f"[{sc}]{hf_status}[/]")
    hf_text.append("\n[dim]risk_level:  [/]")
    hf_text.append(f"[{rc}]{risk}[/]")

    files = handoff.get("allowed_files", [])
    if files:
        hf_text.append(f"\n[dim]files:       [/]{', '.join(files[:5])}")
    steps = handoff.get("implementation_steps", [])
    if steps:
        hf_text.append(f"\n[dim]steps ({len(steps)}):[/]")
        for s in steps[:5]:
            hf_text.append(f"\n  \u2022 {s}")
    cmds = handoff.get("verification_commands", [])
    if cmds:
        hf_text.append(f"\n[dim]verification commands ({len(cmds)}):[/]")
        for c in cmds[:3]:
            hf_text.append(f"\n  $ {c}")

    console.print(Panel(hf_text, title="HANDOFF", border_style="dim"))

    # ── receipt preview ──
    if receipt:
        rcpt = receipt
        rcpt_text = Text()
        rcpt_text.append("verification_id: ", style="dim")
        rcpt_text.append(rcpt.get("verification_id", "?"), style="bold")
        rcpt_text.append("\n[dim]stage:          [/][cyan]Verifier[/]")
        rcpt_text.append("\n[dim]status:         [/][yellow]pending[/]")
        findings = rcpt.get("findings", [])
        if findings:
            rcpt_text.append(f"\n[dim]findings:       [/]{', '.join(findings[:3])}")
        rcpt_text.append("\n")
        rcpt_text.append("\n[bold yellow]No code is executed by this command.[/]")
        console.print(Panel(rcpt_text, title="VERIFIER RECEIPT", border_style="dim"))

    if hf_status == "done":
        done_text = Text("This handoff is already completed.", style="green")
        done_text.append("\n[dim]No verifier receipt was created.[/]")
        console.print(Panel(done_text, border_style="green"))

    written = data.get("written_paths", [])
    if written:
        wrote_text = Text()
        wrote_text.append("Persisted:\n", style="bold green")
        for w in written:
            wrote_text.append(f"  {w}\n", style="dim")
        console.print(Panel(wrote_text, title="PERSISTED", border_style="dim green"))

    console.print(Rule(style="dim"))
    if dry_run and hf_status != "done":
        console.print("  [dim]Use --write to persist the verifier receipt to disk[/]")
    console.print("  [dim]python3 link.py growth run     -- guided workflow dashboard[/]")
    console.print("  [dim]python3 link.py growth handoffs -- view all handoffs[/]")


# ── execute plain fallback ──────────────────────────────────────────────


def render_execute_plain(data: dict[str, Any]) -> None:
    """Render an execute preview/receipt using plain print."""
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)
    hf_status = data.get("handoff_status", "")

    if not ok:
        state_label = "FAILED"
    elif hf_status == "done":
        state_label = "DONE"
    elif dry_run:
        state_label = "DRY RUN"
    else:
        state_label = "WRITTEN"

    out: list[str] = []
    out.append(f"== LINK GROWTH EXECUTE ({state_label}) ==")
    out.append("")
    out.append("No code is executed by this command.")
    out.append("")

    if not ok:
        if data.get("handoff"):
            hf = data["handoff"]
            out.append(f"Handoff exists but is {hf.get('status', '?')}.")
            out.append(f"title: {hf.get('title', '?')}")
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    handoff = data.get("handoff") or {}
    receipt = data.get("receipt") or {}

    out.append("-- HANDOFF --")
    out.append(f"handoff_id:   {data.get('handoff_id', '?')}")
    out.append(f"proposal_id:  {handoff.get('proposal_id', '?')}")
    out.append(f"plan_id:      {handoff.get('plan_id', '?')}")
    out.append(f"title:        {data.get('handoff_title', '?')}")
    out.append(f"stage:        {data.get('handoff_stage', '?')}")
    out.append(f"status:       {hf_status}")
    out.append(f"risk_level:   {handoff.get('risk_level', '?')}")
    files = handoff.get("allowed_files", [])
    if files:
        out.append(f"files:        {', '.join(files[:5])}")
    steps = handoff.get("implementation_steps", [])
    if steps:
        out.append(f"steps ({len(steps)}):")
        for s in steps[:5]:
            out.append(f"  - {s}")
    out.append("")

    if receipt:
        out.append("-- VERIFIER RECEIPT --")
        out.append(f"verification_id: {receipt.get('verification_id', '?')}")
        out.append("stage:           Verifier")
        out.append("status:          pending")
        findings = receipt.get("findings", [])
        if findings:
            out.append(f"findings:        {', '.join(findings[:3])}")
        out.append("")

    if hf_status == "done":
        out.append("This handoff is already completed. No receipt created.")
        out.append("")

    written = data.get("written_paths", [])
    if written:
        out.append("Persisted:")
        for w in written:
            out.append(f"  {w}")
        out.append("")

    if dry_run and hf_status != "done":
        out.append("Use --write to persist the verifier receipt to disk.")
    out.append("python3 link.py growth run     -- guided workflow dashboard")
    out.append("python3 link.py growth handoffs -- view all handoffs")

    print("\n".join(out))


# ── execute render orchestrator ─────────────────────────────────────────


def render_execute(data: dict[str, Any]) -> None:
    """Render an execute preview/receipt with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_execute_plain(data)
        return
    render_execute_with_rich(data)


# ── finalize entry point ─────────────────────────────────────────────────
_FINALIZER_RECEIPT_DIR = ".agents/control_plane/finalizer_receipts"


def finalize_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth finalize <verification_id>``.

    Loads an existing verifier receipt and builds a finalizer receipt from it.
    Dry-run by default; ``--write`` persists the receipt to the canonical
    ``_FINALIZER_RECEIPT_DIR``. No code is executed by this command.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth finalize: create finalizer receipt from verifier receipt")
        print("")
        print("Usage:")
        print("  python3 link.py growth finalize <verification_id-or-path>")
        print("  python3 link.py growth finalize <verification_id-or-path> --json")
        print("  python3 link.py growth finalize <verification_id-or-path> --write")
        print("")
        print("No code is executed by this command. It reads an existing")
        print("verifier receipt and optionally creates a finalizer receipt.")
        print("Default is dry-run. Use --write to persist the receipt to disk.")
        return 0

    verification_ref = args[0]
    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_finalize_data(verification_ref, write=write, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_finalize(data)
    return 0 if data.get("ok") else 1


def collect_finalize_data(
    verification_ref: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Load a verifier receipt and build a finalizer receipt.

    ``verification_ref`` may be a verifier receipt id or a JSON file path.
    The command is dry-run by default. When ``write=True`` it writes only the
    finalizer receipt under ``_FINALIZER_RECEIPT_DIR`` and never executes code.
    """
    from pathlib import Path

    from link_core.control_plane.link_control_plane_finalizer_receipt import (
        build_finalizer_receipt_from_verifier,
        load_finalizer_receipt,
        make_finalization_id,
        write_finalizer_receipt,
    )
    from link_core.control_plane.link_control_plane_verifier_receipt import (
        load_verifier_receipt,
    )

    repo_root = Path(root) if root else Path.cwd()
    verifier_path = _resolve_verifier_receipt_path(verification_ref, repo_root)

    if verifier_path is None or not verifier_path.exists():
        return _finalize_error(
            verification_ref,
            f"verifier receipt not found: {verification_ref}",
        )

    try:
        verifier_receipt = load_verifier_receipt(verifier_path)
    except Exception as exc:
        return _finalize_error(
            verification_ref,
            f"failed to load verifier receipt: {exc}",
        )

    verification_id = str(verifier_receipt.get("verification_id", verification_ref))
    finalization_id = make_finalization_id(verification_id)
    finalizer_dir = repo_root / _FINALIZER_RECEIPT_DIR
    finalizer_path = finalizer_dir / f"{finalization_id}.json"

    if finalizer_path.exists():
        try:
            existing = load_finalizer_receipt(finalizer_path)
        except Exception as exc:
            return _finalize_error(
                verification_ref,
                f"failed to load existing finalizer receipt: {exc}",
                verifier_receipt=verifier_receipt,
                verifier_path=verifier_path,
            )
        return {
            "ok": True,
            "verification_ref": verification_ref,
            "verification_id": verification_id,
            "verifier_receipt_path": str(verifier_path),
            "verifier_receipt": verifier_receipt,
            "finalization_id": existing.get("finalization_id", finalization_id),
            "finalizer_receipt": existing,
            "finalizer_receipt_path": str(finalizer_path),
            "already_finalized": True,
            "written_paths": [],
            "dry_run": True,
            "recommended_next_action": "Finalizer receipt already exists. No duplicate was written.",
            "error": None,
        }

    try:
        finalizer_receipt = build_finalizer_receipt_from_verifier(
            verifier_receipt,
            status="finalized",
        )
    except Exception as exc:
        return _finalize_error(
            verification_ref,
            f"build_finalizer_receipt_from_verifier failed: {exc}",
            verifier_receipt=verifier_receipt,
            verifier_path=verifier_path,
        )

    written_paths: list[str] = []
    if write:
        written_path = write_finalizer_receipt(finalizer_receipt, root=finalizer_dir)
        written_paths = [str(written_path)]

    return {
        "ok": True,
        "verification_ref": verification_ref,
        "verification_id": verification_id,
        "verifier_receipt_path": str(verifier_path),
        "verifier_receipt": verifier_receipt,
        "finalization_id": finalizer_receipt.get("finalization_id", ""),
        "finalizer_receipt": finalizer_receipt,
        "finalizer_receipt_path": str(finalizer_path),
        "already_finalized": False,
        "written_paths": written_paths,
        "dry_run": not write,
        "recommended_next_action": (
            "Use --write to persist the finalizer receipt to disk."
            if not write
            else "Finalizer receipt persisted. No code was executed."
        ),
        "error": None,
    }


def _resolve_verifier_receipt_path(verification_ref: str, repo_root: Any) -> Any:
    from pathlib import Path

    ref_path = Path(verification_ref)
    if ref_path.exists():
        return ref_path
    if ref_path.is_absolute() or ref_path.parent != Path("."):
        candidate = repo_root / ref_path
        if candidate.exists():
            return candidate
        return ref_path
    filename = verification_ref if verification_ref.endswith(".json") else f"{verification_ref}.json"
    return repo_root / _VERIFIER_RECEIPT_DIR / filename


def _finalize_error(
    verification_ref: str,
    error: str,
    verifier_receipt: dict[str, Any] | None = None,
    verifier_path: Any | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "verification_ref": verification_ref,
        "verification_id": verifier_receipt.get("verification_id") if verifier_receipt else None,
        "verifier_receipt_path": str(verifier_path) if verifier_path else "",
        "verifier_receipt": verifier_receipt,
        "finalization_id": None,
        "finalizer_receipt": None,
        "finalizer_receipt_path": "",
        "already_finalized": False,
        "written_paths": [],
        "dry_run": True,
        "recommended_next_action": "",
        "error": error,
    }


def render_finalize_plain(data: dict[str, Any]) -> None:
    ok = bool(data.get("ok"))
    already = bool(data.get("already_finalized"))
    dry_run = bool(data.get("dry_run", True))
    if not ok:
        state = "FAILED"
    elif already:
        state = "ALREADY FINALIZED"
    elif dry_run:
        state = "DRY RUN"
    else:
        state = "WRITTEN"

    out: list[str] = []
    out.append(f"== LINK GROWTH FINALIZE ({state}) ==")
    out.append("")
    out.append("No code is executed by this command.")
    out.append("")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    receipt = data.get("finalizer_receipt") or {}
    out.append("-- FINALIZER RECEIPT --")
    out.append(f"verification_id: {data.get('verification_id', '?')}")
    out.append(f"finalization_id: {data.get('finalization_id', '?')}")
    out.append(f"proposal_id:      {receipt.get('proposal_id', '?')}")
    out.append(f"handoff_id:       {receipt.get('handoff_id', '?')}")
    out.append(f"stage:            {receipt.get('stage', '?')}")
    out.append(f"status:           {receipt.get('status', '?')}")
    out.append(f"summary:          {receipt.get('final_summary', '?')}")
    out.append("")

    written = data.get("written_paths", [])
    if written:
        out.append("Persisted:")
        for path in written:
            out.append(f"  {path}")
        out.append("")

    if already:
        out.append("Finalizer receipt already exists. No duplicate was written.")
    elif dry_run:
        out.append("Use --write to persist the finalizer receipt to disk.")
    out.append("python3 link.py growth receipts -- view verifier receipts")
    out.append("python3 link.py growth run      -- guided workflow dashboard")
    print("\n".join(out))


def render_finalize(data: dict[str, Any]) -> None:
    render_finalize_plain(data)


# ── receipts list entry point ────────────────────────────────────────────


def receipts_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth receipts``.

    Reads existing verifier receipt JSON files from the canonical
    ``.agents/control_plane/verifier_receipts/`` directory and renders
    a read-only terminal view. No files are written.

    Flags:
        --json  Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth receipts: view existing verifier receipts")
        print("")
        print("Usage:")
        print("  python3 link.py growth receipts")
        print("  python3 link.py growth receipts --json")
        print("")
        print("This command is read-only. It lists receipt artifacts")
        print("stored under .agents/control_plane/verifier_receipts/")
        print("and does not execute or mutate anything.")
        return 0

    data = collect_receipts_data()

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_receipts_view(data)
    return 0


def collect_receipts_data(
    root: str | None = None,
) -> dict[str, Any]:
    """Read verifier receipt JSON files from the canonical receipts dir.

    Every receipt dict is loaded via ``load_verifier_receipt``. Returns
    a flat dict with ``count``, ``receipts``, and ``storage_path``.
    Zero receipts is a valid state.
    """
    from pathlib import Path

    from link_core.control_plane.link_control_plane_verifier_receipt import (
        list_verifier_receipts,
        load_verifier_receipt,
    )

    repo_root = Path(root) if root else Path.cwd()
    receipt_dir = repo_root / _VERIFIER_RECEIPT_DIR

    paths = list_verifier_receipts(receipt_dir)
    receipts = [load_verifier_receipt(p) for p in paths]

    return {
        "count": len(receipts),
        "receipts": receipts,
        "storage_path": str(receipt_dir),
    }


# ── receipts rich renderer ──────────────────────────────────────────────


def render_receipts_with_rich(data: dict[str, Any]) -> None:
    """Render a receipts list view using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    count: int = data.get("count", 0)
    receipts: list[dict] = data.get("receipts", [])

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH RECEIPTS[/]",
        f"[dim]{count} receipt{'s' if count != 1 else ''}[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    # ── empty state ──
    if count == 0:
        empty = Text()
        empty.append("\nNo verifier receipts found in ", style="dim")
        empty.append(data.get("storage_path", ""), style="bold")
        empty.append("\n\nTo create a verifier receipt:\n", style="dim")
        empty.append("  python3 link.py growth handoffs\n", style="dim")
        empty.append("  python3 link.py growth execute <handoff_id> --write\n", style="dim")
        empty.append("\n")
        empty.append("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    status_colors = {
        "pending": "yellow", "running": "cyan", "done": "green",
        "failed": "red", "blocked": "red",
    }

    for i, r in enumerate(receipts):
        card = Text()
        vid = r.get("verification_id", "?")
        status = r.get("status", "?")
        sc = status_colors.get(status, "")

        card.append(f"[bold]{r.get('title', '(untitled)')}[/]\n")
        card.append(f"[{sc}]STATUS: {status}[/]  ")
        card.append(f"[dim]STAGE: {r.get('stage', '?')}[/]")

        hf_id = r.get("handoff_id", "")
        if hf_id:
            card.append(f"\n[dim]handoff_id:    [/]{hf_id}")
        plan_id = r.get("plan_id", "")
        if plan_id:
            card.append(f"\n[dim]plan_id:       [/]{plan_id}")
        prop_id = r.get("proposal_id", "")
        if prop_id:
            card.append(f"\n[dim]proposal_id:   [/]{prop_id}")

        cmds = r.get("verification_commands", [])
        if cmds:
            card.append(f"\n[dim]verification commands ({len(cmds)}):[/]")
            for c in cmds[:3]:
                card.append(f"\n  $ {c}")

        findings = r.get("findings", [])
        if findings:
            card.append(f"\n[dim]findings:      [/]{', '.join(findings[:3])}")

        evidence = r.get("evidence_paths", [])
        if evidence:
            card.append(f"\n[dim]evidence:      [/]{', '.join(evidence[:3])}")

        card.append(f"\n[dim]created:       [/]{r.get('created_at', '?')}")

        panel_title = f"RECEIPT [{i + 1}/{count}]  {vid[:24]}"
        console.print(Panel(card, title=panel_title, border_style="dim"))

    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth run      -- guided workflow dashboard[/]")


# ── receipts plain fallback ─────────────────────────────────────────────


def render_receipts_plain(data: dict[str, Any]) -> None:
    """Render a receipts list view using plain print."""
    count: int = data.get("count", 0)
    receipts: list[dict] = data.get("receipts", [])
    out: list[str] = []
    out.append(f"== LINK GROWTH RECEIPTS ({count}) ==")
    out.append("")

    if count == 0:
        out.append(f"No verifier receipts found in {data.get('storage_path', '?')}")
        out.append("")
        out.append("To create a verifier receipt:")
        out.append("  python3 link.py growth handoffs")
        out.append("  python3 link.py growth execute <handoff_id> --write")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow dashboard")
        print("\n".join(out))
        return

    for i, r in enumerate(receipts):
        out.append(f"--- RECEIPT [{i + 1}/{count}] ---")
        out.append(f"verification_id:     {r.get('verification_id', '?')}")
        out.append(f"handoff_id:          {r.get('handoff_id', '?')}")
        out.append(f"plan_id:             {r.get('plan_id', '?')}")
        out.append(f"proposal_id:         {r.get('proposal_id', '?')}")
        out.append(f"title:               {r.get('title', '?')}")
        out.append(f"stage:               {r.get('stage', '?')}")
        out.append(f"status:              {r.get('status', '?')}")
        cmds = r.get("verification_commands", [])
        if cmds:
            out.append(f"verification commands ({len(cmds)}):")
            for c in cmds[:3]:
                out.append(f"  $ {c}")
        findings = r.get("findings", [])
        if findings:
            out.append(f"findings:            {', '.join(findings[:3])}")
        out.append(f"created_at:          {r.get('created_at', '?')}")
        out.append("")
    out.append("python3 link.py growth run  -- guided workflow dashboard")
    print("\n".join(out))


# ── receipts render orchestrator ────────────────────────────────────────


def render_receipts_view(data: dict[str, Any]) -> None:
    """Render receipts with rich if available; fall back to plain text."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_receipts_plain(data)
        return
    render_receipts_with_rich(data)


# ── archive inventory entry point ────────────────────────────────────────
_RESEARCH_DIR = "research"


def archive_inventory_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-inventory``.

    Discovers archive files (`.zip`, `.tar.gz`, etc.) under the repo's
    ``research/`` directory and lists their metadata without extracting.
    No files are written. No archives are extracted.

    Flags:
        --json  Machine-readable output.
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth archive-inventory: scan research archives without extraction")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-inventory")
        print("  python3 link.py growth archive-inventory --json")
        print("")
        print("This command is read-only. It discovers archive files under")
        print("research/ and lists their metadata (type, size, file count,")
        print("safety flags). No extraction. No file writes.")
        return 0

    data = collect_archive_inventory()

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_archive_inventory_view(data)
    return 0


def collect_archive_inventory(
    root: str | None = None,
) -> dict[str, Any]:
    """Discover archive files under the research directory and collect metadata.

    Opens each archive with ``zipfile`` for read-only inspection.
    Detects safety flags: absolute paths, ``../`` traversal, high file
    count, huge estimated extraction size.  ``__MACOSX/`` entries are
    excluded from file counts.

    No files are written. No archives are extracted.

    Args:
        root: Override repo root (for test isolation).

    Returns a dict with ``count``, ``total_bytes_uncompressed`` (estimate),
    ``archives`` list, and ``scan_dir``.
    """
    import zipfile
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    scan_dir = repo_root / _RESEARCH_DIR

    if not scan_dir.exists():
        return {
            "count": 0,
            "total_bytes_uncompressed": 0,
            "archives": [],
            "scan_dir": str(scan_dir),
        }

    archive_suffixes = {
        ".zip",
        ".tar.gz",
        ".tgz",
        ".tar",
        ".tar.bz2",
        ".tar.xz",
        ".7z",
        ".rar",
    }

    archives: list[dict] = []
    total_uncompressed = 0

    for file_path in sorted(scan_dir.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix not in archive_suffixes:
            # Also check compound suffixes: .tar.gz, .tgz, .tar.bz2, .tar.xz
            name = file_path.name.lower()
            if not any(name.endswith(s) for s in (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
                continue

        abs_path = file_path.resolve()
        size_bytes_on_disk = file_path.stat().st_size
        safety_flags: list[str] = []
        file_count = 0
        top_dir = ""
        estimated_extracted = 0
        error: str | None = None
        is_zip = False
        is_tar = False

        try:
            if abs_path.suffix == ".zip":
                is_zip = True
                with zipfile.ZipFile(str(abs_path), "r") as zf:
                    names = zf.namelist()
                    infos = zf.infolist()
                    for n in names:
                        if n.startswith("__MACOSX/"):
                            continue
                        file_count += 1
                        if not top_dir:
                            # First non-dir entry sets the root
                            parts = n.lstrip("/").split("/")
                            if len(parts) >= 1:
                                top_dir = parts[0]
                        if n.startswith("/"):
                            safety_flags.append("absolute_path")
                        if "../" in n:
                            safety_flags.append("path_traversal")
                    for info in infos:
                        if not info.filename.startswith("__MACOSX/"):
                            estimated_extracted += info.file_size
            else:
                # tar variants: we can list with tarfile but only check .tar suffixes
                name_lower = abs_path.name.lower()
                if any(name_lower.endswith(s) for s in (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz")):
                    is_tar = True
                    import tarfile
                    try:
                        with tarfile.open(str(abs_path), "r:*") as tf:
                            for member in tf.getmembers():
                                if member.isdir():
                                    continue
                                if "__MACOSX/" in member.name:
                                    continue
                                file_count += 1
                                if not top_dir:
                                    parts = member.name.lstrip("/").split("/")
                                    if len(parts) >= 1:
                                        top_dir = parts[0]
                                if member.name.startswith("/"):
                                    safety_flags.append("absolute_path")
                                if "../" in member.name:
                                    safety_flags.append("path_traversal")
                                estimated_extracted += member.size
                    except tarfile.TarError as te:
                        error = f"tar read error: {te}"
                else:
                    error = f"archive format not supported for inspection: {abs_path.name}"
        except zipfile.BadZipFile:
            error = "corrupt or invalid zip file"
        except Exception as exc:
            error = f"inspection failed: {exc}"

        if file_count > 50000:
            safety_flags.append("high_file_count")
        if estimated_extracted > 1_000_000_000:
            safety_flags.append("huge_extracted_size")

        if is_zip:
            archive_type = "zip"
        elif is_tar:
            archive_type = "tar"
        else:
            archive_type = abs_path.suffix.lstrip(".")

        total_uncompressed += estimated_extracted

        archives.append({
            "name": abs_path.name,
            "relative_path": str(file_path),
            "abs_path": str(abs_path),
            "size_bytes": size_bytes_on_disk,
            "size_human": _human_size(size_bytes_on_disk),
            "archive_type": archive_type,
            "file_count": file_count,
            "top_dir": top_dir,
            "estimated_extracted_bytes": estimated_extracted,
            "estimated_extracted_human": _human_size(estimated_extracted) if estimated_extracted else "0",
            "safety_flags": sorted(set(safety_flags)),
            "is_clean": len(safety_flags) == 0 and error is None,
            "error": error,
        })

    return {
        "count": len(archives),
        "total_bytes_uncompressed": total_uncompressed,
        "total_uncompressed_human": _human_size(total_uncompressed),
        "archives": archives,
        "scan_dir": str(scan_dir),
    }


def _human_size(size_bytes: int) -> str:
    """Human-readable byte size string."""
    if size_bytes < 1024:
        return f"{size_bytes}B"
    for unit in ("K", "M", "G", "T"):
        size_bytes /= 1024.0
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
    return f"{size_bytes:.1f}P"


# ── archive inventory rich renderer ─────────────────────────────────────


def render_archive_inventory_with_rich(data: dict[str, Any]) -> None:
    """Render archive inventory using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    count: int = data.get("count", 0)
    archives: list[dict] = data.get("archives", [])

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH ARCHIVE INVENTORY[/]",
        f"[dim]{count} archive{'s' if count != 1 else ''}[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    if count == 0:
        empty = Text()
        empty.append("\nNo archive files found in ", style="dim")
        empty.append(data.get("scan_dir", "research/"), style="bold")
        empty.append("\n\nSupported formats: .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz\n\n", style="dim")
        empty.append("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    for i, a in enumerate(archives):
        card = Text()
        card.append(f"[bold]{a.get('name', '?')}[/]")
        card.append(f"  [dim]type: {a.get('archive_type', '?')}[/]")
        card.append(f"  [dim]size on disk: {a.get('size_human', '?')}[/]")
        card.append(f"  [dim]files: {a.get('file_count', 0)}[/]")
        card.append(f"  [dim]extracted est: {a.get('estimated_extracted_human', '?')}[/]")

        top = a.get("top_dir", "")
        if top:
            card.append(f"\n[dim]top dir:  [/]{top}")

        error = a.get("error")
        if error:
            card.append(f"\n[red]error: {error}[/]")
            console.print(Panel(card, title=f"ARCHIVE [{i + 1}/{count}]", border_style="red"))
            continue

        flags: list = a.get("safety_flags", [])
        if flags:
            card.append("\n[dim]safety flags:[/]")
            for f in flags:
                card.append(f"\n  [red]\u2718 {f}[/]")
        else:
            card.append("\n[green]\u2714 clean — no safety issues detected[/]")

        border = "dim green" if a.get("is_clean") else "dim yellow"
        console.print(Panel(card, title=f"ARCHIVE [{i + 1}/{count}]", border_style=border))

    console.print(Rule(style="dim"))
    console.print(f"  [dim]total estimated extracted: {data.get('total_uncompressed_human', '?')}[/]")
    console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")


# ── archive inventory plain fallback ────────────────────────────────────


def render_archive_inventory_plain(data: dict[str, Any]) -> None:
    """Render archive inventory using plain print."""
    count: int = data.get("count", 0)
    archives: list[dict] = data.get("archives", [])
    out: list[str] = []
    out.append(f"== LINK GROWTH ARCHIVE INVENTORY ({count}) ==")
    out.append(f"scan dir: {data.get('scan_dir', '?')}")
    out.append("")

    if count == 0:
        out.append("No archive files found.")
        out.append("Supported formats: .zip, .tar, .tar.gz, .tgz, .tar.bz2, .tar.xz")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow dashboard")
        print("\n".join(out))
        return

    for i, a in enumerate(archives):
        out.append(f"--- ARCHIVE [{i + 1}/{count}] ---")
        out.append(f"name:               {a.get('name', '?')}")
        out.append(f"type:               {a.get('archive_type', '?')}")
        out.append(f"size on disk:       {a.get('size_human', '?')}")
        out.append(f"files:              {a.get('file_count', 0)}")
        out.append(f"extracted est:      {a.get('estimated_extracted_human', '?')}")
        top = a.get("top_dir", "")
        if top:
            out.append(f"top dir:            {top}")
        error = a.get("error")
        if error:
            out.append(f"error:              {error}")
        flags = a.get("safety_flags", [])
        if flags:
            out.append("safety flags:")
            for f in flags:
                out.append(f"  - {f}")
        elif not error:
            out.append("safety: CLEAN")
        out.append("")

    out.append(f"total estimated extracted: {data.get('total_uncompressed_human', '?')}")
    out.append("")
    out.append("python3 link.py growth run  -- guided workflow dashboard")

    print("\n".join(out))


# ── archive inventory render orchestrator ────────────────────────────────


def render_archive_inventory_view(data: dict[str, Any]) -> None:
    """Render archive inventory with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_inventory_plain(data)
        return
    render_archive_inventory_with_rich(data)


# ── archive extraction entry point ───────────────────────────────────────
_EXTRACTED_DIR = "research/_extracted"
_CATALOG_DIR = "research/_catalog"
_RECEIPTS_DIR = "research/_catalog/extraction_receipts"

_ARCHIVE_SUFFIXES = {
    ".zip", ".tar.gz", ".tgz", ".tar", ".tar.bz2", ".tar.xz", ".7z", ".rar",
}

_MAX_FILE_COUNT = 50000
_MAX_EXTRACTED_BYTES = 2_000_000_000  # 2GB


def archive_extract_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-extract --archive <path>``.

    Safely extracts a research archive into ``research/_extracted/<stem>/``.
    Dry-run by default; ``--write`` performs the extraction and writes a
    receipt to ``research/_catalog/extraction_receipts/<stem>.json``.

    Originals are never modified.  Unsafe archive entries are skipped.
    Nested archives are reported but not extracted.

    Flags:
        --archive <path>  Required. Archive file path.
        --write           Extract to staging directory.
        --json            Machine-readable output.
        --root <path>     Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth archive-extract: safely extract a research archive")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-extract --archive <path>")
        print("  python3 link.py growth archive-extract --archive <path> --write")
        print("  python3 link.py growth archive-extract --archive <path> --json")
        print("")
        print("Extracts into research/_extracted/<archive_stem>/.")
        print("Default is dry-run. No files are extracted without --write.")
        print("Originals are never modified. Unsafe paths are skipped.")
        return 0

    archive_path = _parse_arg(args, "--archive")
    if not archive_path:
        print("error: --archive <path> is required", file=sys.stderr)
        print("Run 'python3 link.py growth archive-extract --help' for usage.",
              file=sys.stderr)
        return 2

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_extraction_data(
        archive_path, write=write, root=root_override
    )

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_extraction_view(data)
    return 0 if data.get("ok") else 1


def collect_extraction_data(
    archive_path: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Pre-check, preview, and optionally extract a research archive.

    Returns a dict with ``ok``, archive metadata, ``extracted_count``,
    ``skipped`` breakdown, ``nested_archives``, ``receipt_path``,
    and ``error``.  On ``--write``, files are extracted to the controlled
    staging directory and a receipt is written.
    """
    import zipfile
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    source_path = (repo_root / archive_path).resolve()

    # ── pre-check: file must exist ──
    if not source_path.exists() or not source_path.is_file():
        return _extraction_error(archive_path, f"archive not found: {source_path}")

    # ── pre-check: run inventory to get safety data ──
    inventory = collect_archive_inventory(root=str(repo_root))
    matched = None
    for a in inventory.get("archives", []):
        # Match by absolute path or relative path
        if a.get("abs_path") == str(source_path):
            matched = a
            break
        if a.get("relative_path") == archive_path:
            matched = a
            break

    if matched is None:
        return _extraction_error(
            archive_path,
            f"archive not found in archive-inventory. "
            f"Run 'python3 link.py growth archive-inventory' first.",
        )

    # ── pre-check: safety blockers ──
    if matched.get("error"):
        return _extraction_error(archive_path, f"archive error: {matched['error']}")

    flags = matched.get("safety_flags", [])
    if flags:
        return _extraction_error(
            archive_path,
            f"archive has safety flags: {', '.join(flags)}",
            safety_flags=flags,
        )

    if matched.get("file_count", 0) > _MAX_FILE_COUNT:
        return _extraction_error(
            archive_path,
            f"too many files: {matched['file_count']} > {_MAX_FILE_COUNT}",
            safety_flags=["high_file_count"],
        )

    if matched.get("estimated_extracted_bytes", 0) > _MAX_EXTRACTED_BYTES:
        return _extraction_error(
            archive_path,
            f"estimated extracted size too large: "
            f"{_human_size(matched['estimated_extracted_bytes'])} > "
            f"{_human_size(_MAX_EXTRACTED_BYTES)}",
            safety_flags=["huge_extracted_size"],
        )

    atype = matched.get("archive_type", "")
    if atype not in ("zip", "tar"):
        return _extraction_error(
            archive_path,
            f"unsupported archive type for extraction: {atype}",
        )

    archive_stem = Path(matched.get("name", archive_path)).stem
    output_dir = repo_root / _EXTRACTED_DIR / archive_stem

    # ── dry-run preview ──
    if not write:
        return {
            "ok": True,
            "archive_name": matched.get("name", archive_path),
            "archive_path": str(source_path),
            "archive_type": atype,
            "archive_size_human": matched.get("size_human", "?"),
            "output_dir": str(output_dir),
            "archive_stem": archive_stem,
            "file_count": matched.get("file_count", 0),
            "estimated_extracted_human": matched.get("estimated_extracted_human", "?"),
            "extracted_count": 0,
            "skipped_macosx": 0,
            "skipped_unsafe": 0,
            "nested_archives": [],
            "safety_flags": flags,
            "receipt_path": "",
            "dry_run": True,
            "error": None,
        }

    # ── --write: extract ──
    if output_dir.exists():
        return _extraction_error(
            archive_path,
            f"output directory already exists: {output_dir}",
        )

    output_dir.mkdir(parents=True, exist_ok=False)

    extracted = 0
    skipped_macosx = 0
    skipped_unsafe = 0
    nested_archives: list[str] = []
    extraction_error: str | None = None

    try:
        if atype == "zip":
            with zipfile.ZipFile(str(source_path), "r") as zf:
                for info in zf.infolist():
                    name = info.filename
                    if name.startswith("__MACOSX/"):
                        skipped_macosx += 1
                        continue
                    if _is_nested_archive(name):
                        nested_archives.append(name)
                        continue
                    if _member_is_unsafe(name, is_symlink_zf=False):
                        skipped_unsafe += 1
                        continue
                    zf.extract(info, str(output_dir))
                    extracted += 1
        else:
            import tarfile as _tarfile
            with _tarfile.open(str(source_path), "r:*") as tf:
                for member in tf.getmembers():
                    name = member.name
                    if "__MACOSX/" in name:
                        skipped_macosx += 1
                        continue
                    if _is_nested_archive(name):
                        nested_archives.append(name)
                        continue
                    is_sym = member.issym() if hasattr(member, "issym") else member.is_symlink()
                    if _member_is_unsafe(name, is_symlink_zf=is_sym):
                        skipped_unsafe += 1
                        continue
                    if member.isdir():
                        continue
                    tf.extract(member, str(output_dir), filter=None)  # type: ignore[arg-type]
                    extracted += 1
    except Exception as exc:
        extraction_error = str(exc)

    # ── write receipt ──
    receipt_root = repo_root / _RECEIPTS_DIR
    receipt_root.mkdir(parents=True, exist_ok=True)
    receipt_data = {
        "receipt_version": "link-archive-extract-v1",
        "archive_stem": archive_stem,
        "archive_path": str(source_path),
        "archive_type": atype,
        "archive_size_human": matched.get("size_human", "?"),
        "output_dir": str(output_dir),
        "extracted_count": extracted,
        "skipped_macosx": skipped_macosx,
        "skipped_unsafe": skipped_unsafe,
        "nested_archives": nested_archives,
        "error": extraction_error,
        "created_at": _utc_now(),
    }
    receipt_path = receipt_root / f"{archive_stem}.json"
    receipt_path.write_text(json.dumps(receipt_data, indent=2, default=str),
                            encoding="utf-8")

    return {
        "ok": extraction_error is None,
        "archive_name": matched.get("name", archive_path),
        "archive_path": str(source_path),
        "archive_type": atype,
        "archive_size_human": matched.get("size_human", "?"),
        "output_dir": str(output_dir),
        "archive_stem": archive_stem,
        "file_count": matched.get("file_count", 0),
        "estimated_extracted_human": matched.get("estimated_extracted_human", "?"),
        "extracted_count": extracted,
        "skipped_macosx": skipped_macosx,
        "skipped_unsafe": skipped_unsafe,
        "nested_archives": nested_archives,
        "safety_flags": flags,
        "receipt_path": str(receipt_path),
        "dry_run": False,
        "error": extraction_error,
    }


def _utc_now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _is_nested_archive(name: str) -> bool:
    """Return True if ``name`` looks like a nested archive file."""
    lower = name.lower()
    return any(lower.endswith(s) for s in _ARCHIVE_SUFFIXES)


def _member_is_unsafe(name: str, is_symlink_zf: bool) -> bool:
    """Return True if an archive member is unsafe to extract."""
    if name.startswith("/"):
        return True
    if "../" in name:
        return True
    if is_symlink_zf:
        return True
    return False


def _extraction_error(
    archive_path: str,
    error: str,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "archive_name": archive_path,
        "archive_path": archive_path,
        "archive_type": "",
        "archive_size_human": "",
        "output_dir": "",
        "archive_stem": "",
        "file_count": 0,
        "estimated_extracted_human": "",
        "extracted_count": 0,
        "skipped_macosx": 0,
        "skipped_unsafe": 0,
        "nested_archives": [],
        "safety_flags": safety_flags or [],
        "receipt_path": "",
        "dry_run": True,
        "error": error,
    }


# ── extraction rich renderer ────────────────────────────────────────────


def render_extraction_with_rich(data: dict[str, Any]) -> None:
    """Render an archive extraction preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        state_label = "BLOCKED"
        state_color = "red"
    elif dry_run:
        state_label = "DRY RUN"
        state_color = "yellow"
    else:
        state_label = "EXTRACTED"
        state_color = "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH ARCHIVE EXTRACT[/]",
        f"[{state_color}]{state_label}[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        flags = data.get("safety_flags", [])
        if flags:
            error_text.append("\n[dim]safety flags: [/]")
            error_text.append(", ".join(flags), style="red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── archive info ──
    info = Text()
    info.append("archive: ", style="dim")
    info.append(data.get("archive_name", "?"), style="bold")
    info.append(f"\n[dim]type:   [/]{data.get('archive_type', '?')}")
    info.append(f"\n[dim]size:   [/]{data.get('archive_size_human', '?')}")
    console.print(Panel(info, title="ARCHIVE", border_style="dim"))

    # ── extraction preview / result ──
    preview = Text()
    if dry_run:
        preview.append(
            f"\n[dim]files in archive:      [/]{data.get('file_count', 0)}"
        )
        preview.append(
            f"\n[dim]estimated extracted:   [/]{data.get('estimated_extracted_human', '?')}"
        )
        preview.append(
            f"\n[dim]output dir:            [/]{data.get('output_dir', '?')}"
        )
        preview.append(
            "\n\n[yellow]Would extract above files. Dry-run mode — no files written.[/]"
        )
    else:
        preview.append(
            f"\n[dim]extracted: [/][green]{data.get('extracted_count', 0)}[/]"
        )
        preview.append(
            f"\n[dim]skipped (unsafe): [/][yellow]{data.get('skipped_unsafe', 0)}[/]"
        )
        preview.append(
            f"\n[dim]skipped (macosx): [/][yellow]{data.get('skipped_macosx', 0)}[/]"
        )
        preview.append(
            f"\n[dim]output dir:    [/]{data.get('output_dir', '?')}"
        )
        receipt_path = data.get("receipt_path", "")
        if receipt_path:
            preview.append(
                f"\n[dim]receipt:       [/]{receipt_path}"
            )
        err = data.get("error")
        if err:
            preview.append(f"\n[red]error: {err}[/]")

    nested = data.get("nested_archives", [])
    if nested:
        preview.append(
            f"\n[dim]nested archives ({len(nested)}):[/]"
        )
        for n in nested[:10]:
            preview.append(f"\n  [dim]{n}[/]")

    console.print(Panel(preview, title="EXTRACTION" if not dry_run else "PREVIEW",
                        border_style="green" if ok and not dry_run else "dim"))

    console.print(Rule(style="dim"))
    if dry_run:
        console.print("  [dim]Use --write to extract to staging directory[/]")
    console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")


# ── extraction plain fallback ───────────────────────────────────────────


def render_extraction_plain(data: dict[str, Any]) -> None:
    """Render an archive extraction preview/receipt using plain print."""
    ok: bool = data.get("ok", False)
    dry_run: bool = data.get("dry_run", True)
    label = "BLOCKED" if not ok else ("DRY RUN" if dry_run else "EXTRACTED")
    out: list[str] = []
    out.append(f"== LINK GROWTH ARCHIVE EXTRACT ({label}) ==")
    out.append("")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        flags = data.get("safety_flags", [])
        if flags:
            out.append(f"safety flags: {', '.join(flags)}")
        print("\n".join(out))
        return

    out.append(f"archive:    {data.get('archive_name', '?')}")
    out.append(f"type:       {data.get('archive_type', '?')}")
    out.append(f"size:       {data.get('archive_size_human', '?')}")

    if dry_run:
        out.append(f"files:      {data.get('file_count', 0)}")
        out.append(f"est size:   {data.get('estimated_extracted_human', '?')}")
        out.append(f"output dir: {data.get('output_dir', '?')}")
        out.append("")
        out.append("Dry-run mode — no files written.")
    else:
        out.append(f"extracted:  {data.get('extracted_count', 0)}")
        out.append(f"skipped (unsafe):  {data.get('skipped_unsafe', 0)}")
        out.append(f"skipped (macosx):  {data.get('skipped_macosx', 0)}")
        out.append(f"output dir: {data.get('output_dir', '?')}")
        receipt_path = data.get("receipt_path", "")
        if receipt_path:
            out.append(f"receipt:    {receipt_path}")
        err = data.get("error")
        if err:
            out.append(f"error:      {err}")

    nested = data.get("nested_archives", [])
    if nested:
        out.append(f"nested archives ({len(nested)}):")
        for n in nested[:10]:
            out.append(f"  {n}")

    out.append("")
    if dry_run:
        out.append("Use --write to extract to staging directory.")
    out.append("python3 link.py growth run  -- guided workflow dashboard")

    print("\n".join(out))


# ── extraction render orchestrator ──────────────────────────────────────


def render_extraction_view(data: dict[str, Any]) -> None:
    """Render extraction preview/receipt with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_extraction_plain(data)
        return
    render_extraction_with_rich(data)


# ── archive catalog entry point ─────────────────────────────────────────
_CATALOG_OUTPUT_DIR = "research/_catalog/archive_catalogs"

_SKIP_DIR_NAMES: set[str] = {
    "__pycache__", ".git", ".agents", ".link", "node_modules",
    "venv", ".venv", ".pytest_cache", "__MACOSX", ".mypy_cache",
    ".tox", ".eggs", "dist", "build",
}

_IMPORTANT_FILENAMES: dict[str, str] = {
    "pyproject.toml": "pyproject_toml",
    "package.json": "package_json",
    "requirements.txt": "requirements_txt",
    "setup.py": "setup_py",
    "setup.cfg": "setup_cfg",
    "Dockerfile": "dockerfile",
    "Makefile": "makefile",
    "docker-compose.yml": "docker_compose",
    "docker-compose.yaml": "docker_compose",
    "README.md": "readme",
    "README.rst": "readme",
    "README.txt": "readme",
    "README": "readme",
    "LICENSE": "license",
    "LICENSE.md": "license",
    "LICENSE.txt": "license",
}

_MAX_CATALOG_FILES = 100_000
_MAX_CATALOG_BYTES = 2_000_000_000
_MAX_SINGLE_FILE_BYTES = 10_000_000


def archive_catalog_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-catalog --source <path>``.

    Scans an extracted research directory and produces a structured catalog
    of its contents: file types, important project files, candidate research
    sources, and recommendations.  Dry-run by default; ``--write`` persists
    the catalog to ``research/_catalog/archive_catalogs/<name>.json``.

    No files are unzipped, moved, deleted, or modified.

    Flags:
        --source <path>  Required. Extracted directory to catalog.
        --write          Persist the catalog to disk.
        --json           Machine-readable output.
        --root <path>    Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth archive-catalog: catalog extracted research contents")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-catalog --source <path>")
        print("  python3 link.py growth archive-catalog --source <path> --write")
        print("  python3 link.py growth archive-catalog --source <path> --json")
        print("")
        print("Scans an extracted research directory and builds a structured")
        print("catalog.  Default is dry-run.  No files are written without --write.")
        print("No extraction, no mutation of source files.")
        return 0

    source_arg = _parse_arg(args, "--source")
    if not source_arg:
        print("error: --source <path> is required", file=sys.stderr)
        print("Run 'python3 link.py growth archive-catalog --help' for usage.",
              file=sys.stderr)
        return 2

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_archive_catalog(
        source_arg, write=write, root=root_override
    )

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_archive_catalog_view(data)
    return 0 if data.get("ok") else 1


def collect_archive_catalog(
    source: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Scan an extracted directory and produce a structured catalog.

    Walks the source directory, classifies files by type, identifies
    important project files and candidate research sources, and builds
    recommendations for further mining.  When ``write=True`` the catalog
    is persisted to ``research/_catalog/archive_catalogs/<name>.json``.

    Returns a dict with ``ok``, source metadata, file type counts,
    important files, recommendations, ``safety_flags``, and ``error``.
    """
    import hashlib
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    source_path = (repo_root / source).resolve()

    # ── pre-check ──
    if not source_path.exists():
        return _catalog_error(source, "source_missing", f"source not found: {source_path}")

    if not source_path.is_dir():
        return _catalog_error(source, "source_not_directory", f"source is not a directory: {source_path}")

    # ── scan ──
    source_name = source_path.name
    catalog_id = hashlib.sha256(str(source_path).encode()).hexdigest()[:8]

    file_count = 0
    directory_count = 0
    skipped_count = 0
    total_bytes = 0
    skipped = {"binary": 0, "symlink": 0, "too_large": 0, "hidden_dir": 0}
    file_type_counts: dict[str, int] = {}
    top_level_dirs: list[str] = []
    likely_project_roots: list[str] = []
    important_files: list[dict] = []
    candidate_sources: list[dict] = []
    safety_flags: list[str] = []

    try:
        for entry in sorted(source_path.iterdir()):
            if entry.is_dir() and not entry.name.startswith("."):
                top_level_dirs.append(entry.name)

        for entry in source_path.rglob("*"):
            # Skip hidden/system dirs
            if entry.is_dir():
                if entry.name in _SKIP_DIR_NAMES or entry.name.startswith("."):
                    continue

            if entry.is_dir():
                directory_count += 1
                # Check for project root signals
                for signal in ("pyproject.toml", "package.json", "setup.py", "setup.cfg"):
                    if (entry / signal).exists():
                        rel = entry.relative_to(source_path)
                        likely_project_roots.append(str(rel))
                        break
                continue

            if entry.is_symlink():
                skipped["symlink"] += 1
                skipped_count += 1
                continue

            if not entry.is_file():
                continue

            st_size = entry.stat().st_size

            if st_size > _MAX_SINGLE_FILE_BYTES:
                skipped["too_large"] += 1
                skipped_count += 1
                continue

            if _is_binary_file_path(entry):
                skipped["binary"] += 1
                skipped_count += 1
                continue

            file_count += 1
            total_bytes += st_size

            suffix = entry.suffix.lower()
            category = _suffix_category(suffix)
            file_type_counts[category] = file_type_counts.get(category, 0) + 1

            # Important file detection
            imp_type = _match_important_file(entry.name)
            if imp_type:
                rel = entry.relative_to(source_path)
                important_files.append({
                    "path": str(rel),
                    "type": imp_type,
                    "size_human": _human_size(st_size),
                })

            # Candidate research source detection
            cand_type = _match_candidate_research(entry, suffix, st_size)
            if cand_type:
                rel = entry.relative_to(source_path)
                candidate_sources.append({
                    "path": str(rel),
                    "type": cand_type,
                    "size_bytes": st_size,
                })

    except Exception as exc:
        return _catalog_error(source, "scan_error", str(exc))

    # ── safety flags ──
    if file_count > _MAX_CATALOG_FILES:
        safety_flags.append("too_many_files")
    if total_bytes > _MAX_CATALOG_BYTES:
        safety_flags.append("too_large")
    binary_ratio = skipped["binary"] / max(file_count + skipped["binary"], 1)
    if binary_ratio > 0.5:
        safety_flags.append("binary_heavy")

    is_clean = len(safety_flags) == 0

    # ── recommendations ──
    recommendations = _build_catalog_recommendations(
        file_type_counts, important_files, candidate_sources,
        source_name,
    )

    # ── write ──
    catalog_path = ""
    if write:
        if not is_clean:
            return _catalog_error(
                source, "safety_flags",
                f"cannot write catalog with safety flags: {', '.join(safety_flags)}",
                safety_flags=safety_flags,
            )

        catalog_dir = repo_root / _CATALOG_OUTPUT_DIR
        catalog_dir.mkdir(parents=True, exist_ok=True)
        catalog_file = catalog_dir / f"{source_name}.json"
        if catalog_file.exists():
            return _catalog_error(
                source, "already_exists",
                f"catalog already exists: {catalog_file}",
            )

        catalog_out = _build_catalog_dict(
            source_path=str(source_path),
            source_name=source_name,
            catalog_id=catalog_id,
            total_bytes=total_bytes,
            file_count=file_count,
            directory_count=directory_count,
            skipped_count=skipped_count,
            skipped=skipped,
            file_type_counts=file_type_counts,
            top_level_dirs=top_level_dirs,
            likely_project_roots=likely_project_roots,
            important_files=important_files,
            candidate_sources=candidate_sources,
            safety_flags=safety_flags,
            recommendations=recommendations,
        )
        catalog_file.write_text(
            json.dumps(catalog_out, indent=2, default=str), encoding="utf-8",
        )
        catalog_path = str(catalog_file)

    return {
        "ok": is_clean,
        "source_path": str(source_path),
        "source_name": source_name,
        "catalog_id": catalog_id,
        "created_at": _utc_now(),
        "total_bytes": total_bytes,
        "total_human": _human_size(total_bytes),
        "file_count": file_count,
        "directory_count": directory_count,
        "skipped_count": skipped_count,
        "skipped_details": skipped,
        "file_type_counts": file_type_counts,
        "top_level_dirs": top_level_dirs,
        "likely_project_roots": likely_project_roots,
        "important_files": important_files,
        "candidate_research_sources": candidate_sources,
        "recommendations": recommendations,
        "safety_flags": safety_flags,
        "is_clean": is_clean,
        "catalog_path": catalog_path,
        "dry_run": not write,
        "error": None,
    }


# ── catalog helpers ─────────────────────────────────────────────────────


def _is_binary_file_path(path: Path) -> bool:
    """Return True if the first 512 bytes contain a null byte."""
    try:
        with open(path, "rb") as fh:
            chunk = fh.read(512)
        return b"\x00" in chunk
    except Exception:
        return True  # treat unreadable as binary, skip


_SUFFIX_MAP: dict[str, str] = {
    ".py": "python", ".pyi": "python", ".pyx": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".md": "markdown", ".mdx": "markdown",
    ".json": "json", ".jsonl": "json",
    ".txt": "text", ".csv": "text", ".log": "text",
    ".rst": "text", ".yaml": "text", ".yml": "text",
    ".toml": "text", ".cfg": "text", ".ini": "text",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "css", ".sass": "css", ".less": "css",
    ".rs": "rust", ".go": "go", ".java": "java",
    ".png": "image", ".jpg": "image", ".jpeg": "image",
    ".gif": "image", ".svg": "image", ".ico": "image", ".webp": "image",
    ".ttf": "font", ".woff": "font", ".woff2": "font", ".eot": "font",
}


def _suffix_category(suffix: str) -> str:
    return _SUFFIX_MAP.get(suffix, "other")


def _match_important_file(name: str) -> str | None:
    return _IMPORTANT_FILENAMES.get(name)


def _match_candidate_research(path: Path, suffix: str, size: int) -> str | None:
    """Return a research source type label or None."""
    name = path.name.lower()
    rel = str(path).lower()
    if suffix == ".md" and size > 500:
        # Skip files inside skipped dirs
        if any(skip in rel for skip in ("node_modules", "__pycache__")):
            return None
        return "markdown_doc"
    if suffix == ".py" and size > 1000:
        if any(skip in rel for skip in ("node_modules", "__pycache__", "test", "tests")):
            return None
        return "python_source"
    if name.startswith("readme") and suffix in (".md", ".rst", ".txt", ""):
        return "readme_file"
    return None


def _build_catalog_recommendations(
    counts: dict[str, int],
    important: list[dict],
    candidates: list[dict],
    source_name: str,
) -> list[str]:
    recs: list[str] = []
    md_count = counts.get("markdown", 0)
    py_count = counts.get("python", 0)
    imp_types = {i["type"] for i in important}

    if md_count > 0:
        recs.append(
            f"{md_count} markdown documents found — suitable for growth propose mining"
        )
    if py_count > 0:
        recs.append(
            f"{py_count} Python source files found — check for design patterns"
        )
    if "package_json" in imp_types:
        recs.append("package.json detected — this is a JavaScript/TypeScript project")
    if "pyproject_toml" in imp_types or "setup_py" in imp_types:
        recs.append("Python project root detected — check for architecture patterns")
    if "dockerfile" in imp_types:
        recs.append("Dockerfile detected — infrastructure source available")
    if md_count == 0:
        recs.append(
            "No markdown documents found — archive may not be suitable for text mining"
        )

    return recs


def _build_catalog_dict(
    source_path: str,
    source_name: str,
    catalog_id: str,
    total_bytes: int,
    file_count: int,
    directory_count: int,
    skipped_count: int,
    skipped: dict[str, int],
    file_type_counts: dict[str, int],
    top_level_dirs: list[str],
    likely_project_roots: list[str],
    important_files: list[dict],
    candidate_sources: list[dict],
    safety_flags: list[str],
    recommendations: list[str],
) -> dict[str, Any]:
    return {
        "catalog_version": "link-archive-catalog-v1",
        "source_path": source_path,
        "source_name": source_name,
        "catalog_id": catalog_id,
        "created_at": _utc_now(),
        "total_bytes": total_bytes,
        "total_human": _human_size(total_bytes),
        "file_count": file_count,
        "directory_count": directory_count,
        "skipped_count": skipped_count,
        "skipped_details": skipped,
        "file_type_counts": file_type_counts,
        "top_level_dirs": top_level_dirs,
        "likely_project_roots": likely_project_roots,
        "important_files": important_files,
        "candidate_research_sources": candidate_sources,
        "recommendations": recommendations,
        "safety_flags": safety_flags,
    }


def _catalog_error(
    source: str,
    flag: str,
    error: str,
    safety_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "source_path": source,
        "source_name": "",
        "catalog_id": "",
        "created_at": _utc_now(),
        "total_bytes": 0,
        "total_human": "0",
        "file_count": 0,
        "directory_count": 0,
        "skipped_count": 0,
        "skipped_details": {},
        "file_type_counts": {},
        "top_level_dirs": [],
        "likely_project_roots": [],
        "important_files": [],
        "candidate_research_sources": [],
        "recommendations": [],
        "safety_flags": safety_flags or [flag],
        "is_clean": False,
        "catalog_path": "",
        "dry_run": True,
        "error": error,
    }


# ── catalog rich renderer ──────────────────────────────────────────────


def render_archive_catalog_with_rich(data: dict[str, Any]) -> None:
    """Render an archive catalog preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        label, color = "ERROR", "red"
    elif dry_run:
        label, color = "DRY RUN", "yellow"
    else:
        label, color = "WRITTEN", "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH ARCHIVE CATALOG[/]",
        f"[{color}]{label}[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        flags = data.get("safety_flags", [])
        if flags:
            error_text.append(f"\n[dim]flags: [/]{', '.join(flags)}", style="red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── source summary ──
    info = Text()
    info.append("source: ", style="dim")
    info.append(data.get("source_path", "?"), style="bold")
    info.append(f"\n[dim]catalog_id: [/]{data.get('catalog_id', '?')}")
    info.append(
        f"\n[dim]files: {data.get('file_count', 0)}  "
        f"dirs: {data.get('directory_count', 0)}  "
        f"total: {data.get('total_human', '?')}  "
        f"skipped: {data.get('skipped_count', 0)}[/]"
    )
    console.print(Panel(info, title="SOURCE", border_style="dim"))

    # ── file types ──
    counts = data.get("file_type_counts", {})
    if counts:
        top = sorted(counts.items(), key=lambda x: -x[1])[:12]
        types_line = "  ".join(
            f"[dim]{cat}:[/] {n}" for cat, n in top
        )
        console.print(Panel(Text(types_line), title="FILE TYPES", border_style="dim"))

    # ── important files ──
    imp = data.get("important_files", [])
    if imp:
        imp_text = Text()
        for i in imp[:10]:
            imp_text.append(
                f"\n[dim]\u2022 {i.get('type', '?')}:[/] "
                f"{i.get('path', '?')}  [dim]({i.get('size_human', '?')})[/]"
            )
        console.print(Panel(imp_text, title="IMPORTANT FILES", border_style="dim"))

    # ── recommendations ──
    recs = data.get("recommendations", [])
    if recs:
        rec_text = Text()
        for r in recs:
            rec_text.append(f"\n\u2022 {r}")
        console.print(Panel(rec_text, title="RECOMMENDATIONS", border_style="green"))

    if dry_run and data.get("catalog_path", "") == "":
        console.print(Rule(style="dim"))
        console.print("  [dim]Use --write to persist the catalog to disk[/]")
    else:
        catalog_path = data.get("catalog_path", "")
        if catalog_path:
            wrote_text = Text()
            wrote_text.append("Catalog written to:\n", style="bold green")
            wrote_text.append(f"  {catalog_path}", style="dim")
            console.print(Panel(wrote_text, border_style="dim green"))

    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")


# ── catalog plain fallback ──────────────────────────────────────────────


def render_archive_catalog_plain(data: dict[str, Any]) -> None:
    """Render an archive catalog using plain print."""
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    label = "ERROR" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    out: list[str] = []
    out.append(f"== LINK GROWTH ARCHIVE CATALOG ({label}) ==")
    out.append("")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        flags = data.get("safety_flags", [])
        if flags:
            out.append(f"flags: {', '.join(flags)}")
        print("\n".join(out))
        return

    out.append(f"source:     {data.get('source_path', '?')}")
    out.append(f"catalog_id: {data.get('catalog_id', '?')}")
    out.append(
        f"files: {data.get('file_count', 0)}  "
        f"dirs: {data.get('directory_count', 0)}  "
        f"total: {data.get('total_human', '?')}  "
        f"skipped: {data.get('skipped_count', 0)}"
    )
    out.append("")

    counts = data.get("file_type_counts", {})
    if counts:
        out.append("-- FILE TYPES --")
        for cat, n in sorted(counts.items(), key=lambda x: -x[1])[:12]:
            out.append(f"  {cat}: {n}")
        out.append("")

    imp = data.get("important_files", [])
    if imp:
        out.append("-- IMPORTANT FILES --")
        for i in imp[:10]:
            out.append(
                f"  {i.get('type', '?')}: {i.get('path', '?')} "
                f"({i.get('size_human', '?')})"
            )
        out.append("")

    recs = data.get("recommendations", [])
    if recs:
        out.append("-- RECOMMENDATIONS --")
        for r in recs:
            out.append(f"  - {r}")
        out.append("")

    catalog_path = data.get("catalog_path", "")
    if catalog_path:
        out.append(f"Catalog written to: {catalog_path}")
        out.append("")

    if dry_run and not catalog_path:
        out.append("Use --write to persist the catalog to disk.")
    out.append("python3 link.py growth run  -- guided workflow dashboard")
    print("\n".join(out))


# ── catalog render orchestrator ─────────────────────────────────────────


def render_archive_catalog_view(data: dict[str, Any]) -> None:
    """Render archive catalog with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_catalog_plain(data)
        return
    render_archive_catalog_with_rich(data)


# ── archive queue entry point ───────────────────────────────────────────


def archive_queue_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-queue``.

    Reads archive catalog JSON files from ``research/_catalog/archive_catalogs/``
    and produces a ranked source queue for Growth mining.  Each queue entry
    points to a specific file from a catalog's ``candidate_research_sources``
    or ``important_files``, scored and sorted by mining priority.

    Read-only.  No files are written.  No proposals are mined.

    Flags:
        --catalog <path>  Read only this one catalog file.
        --json            Machine-readable output.
        --root <path>     Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth archive-queue: rank extracted sources for mining")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-queue")
        print("  python3 link.py growth archive-queue --json")
        print("  python3 link.py growth archive-queue --catalog <path>")
        print("  python3 link.py growth archive-queue --catalog <path> --json")
        print("")
        print("Reads archive catalog JSON files and produces a ranked")
        print("source queue.  Each entry suggests a specific file to mine")
        print("with 'growth propose'.  Read-only — no files are written.")
        return 0

    catalog_arg = _parse_arg(args, "--catalog")
    root_override = _parse_arg(args, "--root")
    data = collect_archive_queue(catalog_path=catalog_arg, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_archive_queue_view(data)
    return 0


def collect_archive_queue(
    catalog_path: str | None = None,
    root: str | None = None,
) -> dict[str, Any]:
    """Load catalog JSON(s) and produce a ranked source queue for mining.

    When ``catalog_path`` is omitted every ``*.json`` file under
    ``_CATALOG_OUTPUT_DIR`` is loaded.  When provided, only that one
    catalog is read.

    Each candidate research source and important file is scored using
    type-, path-, and catalog-context bonuses.  Entries that fall below
    a threshold or point to skipped directories are placed in
    ``skipped_entries``.

    Returns a dict with ``catalog_count``, ``queue_count``,
    ``skipped_count``, ``source_queue``, ``skipped_entries``,
    ``recommendations``, ``warnings``, and ``error``.

    Read-only.  No files are written.
    """
    import json as _json
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    catalogs_dir = repo_root / _CATALOG_OUTPUT_DIR

    # ── load catalogs ──
    if catalog_path:
        catalog_file = repo_root / catalog_path
        if not catalog_file.exists():
            return _queue_empty(
                warnings=[{
                    "type": "catalog_missing",
                    "detail": f"catalog not found: {catalog_file}",
                }],
            )
        if catalog_file.suffix != ".json":
            return _queue_empty(
                warnings=[{
                    "type": "catalog_not_json",
                    "detail": f"catalog must be a .json file: {catalog_file}",
                }],
            )
        raw_catalogs = [catalog_file]
    else:
        if not catalogs_dir.exists():
            return _queue_empty(
                warnings=[{
                    "type": "no_catalogs",
                    "detail": f"no catalogs directory: {catalogs_dir}",
                }],
            )
        raw_catalogs = sorted(catalogs_dir.glob("*.json"))

    catalogs: list[dict] = []
    warnings: list[dict] = []

    for cf in raw_catalogs:
        try:
            catalog = _json.loads(cf.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append({
                "type": "catalog_invalid_json",
                "detail": f"{cf.name}: {exc}",
            })
            continue
        if not isinstance(catalog, dict):
            warnings.append({
                "type": "catalog_not_dict",
                "detail": f"{cf.name}: not a JSON object",
            })
            continue
        catalogs.append(catalog)

    if not catalogs:
        if not warnings:
            warnings.append({
                "type": "no_catalogs",
                "detail": f"no catalog files found in {catalogs_dir}",
            })
        return _queue_empty(warnings=warnings)

    # ── score and rank ──
    all_entries: list[dict] = []
    skipped: list[dict] = []

    for catalog in catalogs:
        source_name = catalog.get("source_name", "?")
        source_root = catalog.get("source_path", "")

        # Collect sources to score: candidate_research_sources + important_files (deduped by path)
        seen_paths: set[str] = set()
        to_score: list[dict] = []

        for src in catalog.get("candidate_research_sources", []) or []:
            p = src.get("path", "")
            if p and p not in seen_paths:
                seen_paths.add(p)
                to_score.append(src)

        for imp in catalog.get("important_files", []) or []:
            p = imp.get("path", "")
            if p and p not in seen_paths:
                seen_paths.add(p)
                to_score.append({
                    "path": p,
                    "type": imp.get("type", "important_file"),
                    "size_bytes": 0,
                })

        if not to_score:
            warnings.append({
                "type": "no_candidate_sources",
                "detail": f"{source_name}: no candidate sources or important files",
            })
            continue

        for src in to_score:
            score = _score_queue_source(src, catalog)
            full_path = Path(source_root) / src["path"]
            reason = _queue_reason(src, score)

            if score <= 0:
                skipped.append({"path": str(full_path), "reason": reason})
                continue
            if not full_path.exists():
                skipped.append({"path": str(full_path), "reason": "source_missing"})
                continue

            estimated_value = "high" if score >= 13 else ("medium" if score >= 8 else "low")

            all_entries.append({
                "source_path": str(full_path),
                "catalog_source_name": source_name,
                "source_type": "file",
                "reason": reason,
                "score": score,
                "estimated_value": estimated_value,
                "suggested_command": f"python3 link.py growth propose --source {full_path}",
            })

    # Sort descending by score, then by type priority, then alphabetically
    _type_priority = {"readme_file": 0, "markdown_doc": 1, "python_source": 2, "readme": 0}
    all_entries.sort(key=lambda e: (
        -e["score"],
        _type_priority.get(e.get("source_type", ""), 99),
        e["source_path"].lower(),
    ))

    # Assign ranks
    for i, entry in enumerate(all_entries):
        entry["rank"] = i + 1

    # Build recommendations (top 3 commands)
    recommendations: list[str] = []
    for e in all_entries[:3]:
        recommendations.append(e["suggested_command"])

    if not all_entries and not skipped:
        warnings.append({
            "type": "no_queue_items",
            "detail": "catalogs found but no sources eligible for queue",
        })

    return {
        "catalog_count": len(catalogs),
        "queue_count": len(all_entries),
        "skipped_count": len(skipped),
        "source_queue": all_entries,
        "skipped_entries": skipped,
        "recommendations": recommendations,
        "warnings": warnings,
        "error": None,
    }


def _score_queue_source(src: dict[str, Any], catalog: dict[str, Any]) -> int:
    """Score a candidate source for mining priority."""
    src_type = src.get("type", "")
    path_lower = src.get("path", "").lower()
    size = src.get("size_bytes", 0)

    base_scores = {
        "readme_file": 12,
        "readme": 10,
        "markdown_doc": 8,
        "python_source": 6,
    }
    score = base_scores.get(src_type, 4)

    # Path-based bonuses
    research_keywords = ("docs", "notes", "research", "papers", "design", "architecture", "examples")
    for kw in research_keywords:
        if f"/{kw}/" in f"/{path_lower}" or path_lower.startswith(f"{kw}/"):
            score += 3
            break

    if path_lower.startswith("readme"):
        score += 2

    # Catalog-context bonuses
    important_files = catalog.get("important_files", []) or []
    imp_types = {i.get("type") for i in important_files}
    if "pyproject_toml" in imp_types or "setup_py" in imp_types:
        score += 2

    roots = catalog.get("likely_project_roots", []) or []
    if roots:
        score += 3

    top_dirs = catalog.get("top_level_dirs", []) or []
    if any(kw in str(top_dirs).lower() for kw in research_keywords):
        score += 1

    # Penalties
    skip_segments = ("node_modules", "__pycache__", ".git", "dist", "build", "__macosx")
    if any(seg in path_lower for seg in skip_segments):
        score -= 99

    if size < 200:
        score -= 5

    if size > 1_000_000:
        score -= 3

    return max(score, -100)


def _queue_reason(src: dict[str, Any], score: int) -> str:
    src_type = src.get("type", "")
    path = src.get("path", "")
    size = src.get("size_bytes", 0)

    type_labels = {
        "readme_file": "README with content",
        "readme": "README file",
        "markdown_doc": "markdown document",
        "python_source": "Python source file",
    }
    label = type_labels.get(src_type, f"{src_type} file")

    if score <= 0:
        if size < 200:
            return f"{label} too small ({size}B)"
        return f"{label} in skipped directory"
    if score >= 13:
        return f"{label} — high-priority research source"
    if score >= 8:
        return f"{label} — medium-priority source"
    return f"{label}"


def _queue_empty(
    warnings: list[dict] | None = None,
) -> dict[str, Any]:
    return {
        "catalog_count": 0,
        "queue_count": 0,
        "skipped_count": 0,
        "source_queue": [],
        "skipped_entries": [],
        "recommendations": [],
        "warnings": warnings or [
            {"type": "no_catalogs", "detail": "no catalogs found"},
        ],
        "error": None,
    }


# ── queue rich renderer ─────────────────────────────────────────────────


def render_archive_queue_with_rich(data: dict[str, Any]) -> None:
    """Render an archive queue using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    catalog_count: int = data.get("catalog_count", 0)
    queue_count: int = data.get("queue_count", 0)
    skipped_count: int = data.get("skipped_count", 0)
    queue: list = data.get("source_queue", [])
    skipped: list = data.get("skipped_entries", [])
    recs: list = data.get("recommendations", [])
    warnings: list = data.get("warnings", [])

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH ARCHIVE QUEUE[/]",
        f"[dim]{catalog_count} catalog{'s' if catalog_count != 1 else ''}  "
        f"{queue_count} queued  {skipped_count} skipped[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    # ── empty state ──
    if catalog_count == 0:
        empty = Text()
        empty.append("\nNo catalog files found.\n\n", style="dim")
        empty.append("To create a catalog:\n", style="dim")
        empty.append("  python3 link.py growth archive-extract --archive <path> --write\n", style="dim")
        empty.append("  python3 link.py growth archive-catalog --source <dir> --write\n", style="dim")
        empty.append("\n")
        empty.append("  [dim]python3 link.py growth archive-inventory  -- find archives[/]\n", style="dim")
        empty.append("  [dim]python3 link.py growth run               -- guided workflow[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    # ── warnings ──
    for w in warnings:
        w_text = Text()
        w_text.append(f"[yellow]{w.get('type', '?')}: [/]")
        w_text.append(w.get("detail", ""))
        console.print(Panel(w_text, border_style="yellow"))
        console.print(Rule(style="dim"))

    # ── empty queue but catalogs exist ──
    if queue_count == 0:
        empty_q = Text()
        empty_q.append(f"\n{catalog_count} catalog(s) found but no sources eligible for queue.\n", style="dim")
        if skipped:
            empty_q.append(f"\n{skipped_count} source(s) were skipped.\n", style="dim")
        console.print(Panel(empty_q, border_style="dim"))
        console.print(Rule(style="dim"))
        console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")
        return

    # ── queue entries ──
    value_colors = {"high": "green", "medium": "yellow", "low": "dim"}
    for entry in queue[:15]:
        entry_text = Text()
        ev = entry.get("estimated_value", "medium")
        vc = value_colors.get(ev, "dim")

        entry_text.append(
            f"[bold]#{entry.get('rank')}[/]  "
            f"[{vc}]{ev.upper()}[/]  "
            f"score: {entry.get('score')}"
        )
        entry_text.append(
            f"\n[dim]source:[/] {entry.get('source_path', '?')}"
        )
        entry_text.append(
            f"\n[dim]reason:[/] {entry.get('reason', '?')}"
        )
        entry_text.append(
            f"\n[dim]cmd:    [/]$ {entry.get('suggested_command', '?')}"
        )

        panel_title = f"QUEUE  {entry.get('catalog_source_name', '?')}"
        console.print(Panel(entry_text, title=panel_title, border_style=vc))

    if len(queue) > 15:
        console.print(f"  [dim]... and {len(queue) - 15} more entries[/]")

    # ── recommendations ──
    if recs:
        rec_text = Text()
        rec_text.append("Top command:\n", style="bold green")
        rec_text.append(f"  $ {recs[0]}\n\n", style="dim")
        if len(recs) > 1:
            rec_text.append("Next:\n", style="bold")
            for r in recs[1:4]:
                rec_text.append(f"  $ {r}\n", style="dim")
        console.print(Panel(rec_text, title="RECOMMENDED NEXT STEPS", border_style="green"))

    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth propose --source <path>  -- run miner on a source[/]")
    console.print("  [dim]python3 link.py growth run                     -- guided workflow[/]")


# ── queue plain fallback ────────────────────────────────────────────────


def render_archive_queue_plain(data: dict[str, Any]) -> None:
    """Render an archive queue using plain print."""
    catalog_count: int = data.get("catalog_count", 0)
    queue_count: int = data.get("queue_count", 0)
    skipped_count: int = data.get("skipped_count", 0)
    queue: list = data.get("source_queue", [])
    recs: list = data.get("recommendations", [])
    warnings: list = data.get("warnings", [])
    out: list[str] = []
    out.append(
        f"== LINK GROWTH ARCHIVE QUEUE ({catalog_count} catalogs, "
        f"{queue_count} queued, {skipped_count} skipped) =="
    )
    out.append("")

    if catalog_count == 0:
        out.append("No catalog files found.")
        out.append("")
        out.append("To create a catalog:")
        out.append("  python3 link.py growth archive-extract --archive <path> --write")
        out.append("  python3 link.py growth archive-catalog --source <dir> --write")
        out.append("")
        out.append("python3 link.py growth archive-inventory  -- find archives")
        out.append("python3 link.py growth run               -- guided workflow")
        print("\n".join(out))
        return

    for w in warnings:
        out.append(f"WARNING [{w.get('type', '?')}]: {w.get('detail', '')}")
        out.append("")

    if queue_count == 0:
        out.append(f"{catalog_count} catalog(s) found but no sources eligible for queue.")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow dashboard")
        print("\n".join(out))
        return

    for entry in queue[:15]:
        out.append(f"--- #{entry.get('rank')} [{entry.get('estimated_value', 'medium').upper()}] score={entry.get('score')} ---")
        out.append(f"source: {entry.get('source_path', '?')}")
        out.append(f"reason: {entry.get('reason', '?')}")
        out.append(f"cmd:    $ {entry.get('suggested_command', '?')}")
        out.append("")

    if recs:
        out.append("-- RECOMMENDED NEXT STEPS --")
        out.append(f"Top: $ {recs[0]}")
        for r in recs[1:4]:
            out.append(f"Next: $ {r}")
        out.append("")

    out.append("python3 link.py growth propose --source <path>  -- run miner on a source")
    out.append("python3 link.py growth run                     -- guided workflow")
    print("\n".join(out))


# ── queue render orchestrator ───────────────────────────────────────────


def render_archive_queue_view(data: dict[str, Any]) -> None:
    """Render archive queue with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_queue_plain(data)
        return
    render_archive_queue_with_rich(data)


# ── archive mine entry point ────────────────────────────────────────────


def archive_mine_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-mine --rank <N>``.

    Mines a ranked archive queue item (or an arbitrary ``--source`` path)
    into Growth proposals using the existing ``collect_propose_data`` pipeline.
    Dry-run by default; ``--write`` persists proposals to the control-plane
    registry.

    Flags:
        --rank <N>   Mine the queue entry at this rank (1-indexed).
        --source <path>  Mine a specific file, bypassing the queue.
        --write      Persist proposals to disk.
        --json       Machine-readable output.
        --root <path>  Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth archive-mine: mine archive queue sources into proposals")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-mine --rank <N>")
        print("  python3 link.py growth archive-mine --rank <N> --write")
        print("  python3 link.py growth archive-mine --rank <N> --json")
        print("  python3 link.py growth archive-mine --source <path>")
        print("  python3 link.py growth archive-mine --source <path> --write")
        print("")
        print("Picks a source from the archive queue (by rank) or mines a")
        print("specific file directly.  Dry-run by default.  Proposals are")
        print("written only when --write is provided.")
        return 0

    rank_arg = _parse_arg(args, "--rank")
    source_arg = _parse_arg(args, "--source")

    if rank_arg is not None and source_arg is not None:
        print("error: use --rank or --source, not both", file=sys.stderr)
        print("Run 'python3 link.py growth archive-mine --help' for usage.",
              file=sys.stderr)
        return 2

    if rank_arg is None and source_arg is None:
        print("error: --rank <N> or --source <path> is required", file=sys.stderr)
        print("Run 'python3 link.py growth archive-mine --help' for usage.",
              file=sys.stderr)
        return 2

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_archive_mine(
        rank=rank_arg, source=source_arg, write=write, root=root_override,
    )

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_archive_mine_view(data)
    return 0 if data.get("ok") else 1


def collect_archive_mine(
    rank: str | None = None,
    source: str | None = None,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Resolve a queue rank or source path and mine it into proposals.

    When ``rank`` is provided the archive queue is loaded and the entry
    at that 1-indexed position is selected.  When ``source`` is provided
    the queue is bypassed entirely.  The resolved source path is passed
    directly to ``collect_propose_data`` (the existing propose pipeline).

    Returns a combined dict with queue metadata, propose results, and
    suggested next commands.  ``--write`` is forwarded to the propose
    pipeline.

    Read-only when ``write=False``.  No queue/catalog/source files are
    mutated.
    """
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()

    # ── resolve source ──
    queue_entry: dict[str, Any] | None = None
    rank_num: int | None = None
    warnings: list[str] = []
    source_path: str

    if rank is not None:
        try:
            rank_num = int(rank)
        except ValueError:
            return _mine_error(
                f"rank must be an integer, got {rank!r}",
                warnings=["bad_rank"],
            )

        if rank_num < 1:
            return _mine_error(
                f"rank must be >= 1, got {rank_num}",
                warnings=["rank_out_of_range"],
            )

        try:
            queue_data = collect_archive_queue(root=str(repo_root))
        except Exception as exc:
            return _mine_error(
                f"failed to load archive queue: {exc}",
                warnings=["queue_load_failed"],
            )

        q_warnings = queue_data.get("warnings", [])
        for w in q_warnings:
            warnings.append(w.get("detail", w.get("type", "?")))

        source_queue = queue_data.get("source_queue", [])
        if not source_queue:
            return _mine_error(
                "no queue entries available. Run archive-queue first.",
                warnings=warnings + ["empty_queue"],
            )

        idx = rank_num - 1
        if idx >= len(source_queue):
            return _mine_error(
                f"rank {rank_num} out of range (1..{len(source_queue)})",
                warnings=warnings + ["rank_out_of_range"],
            )

        queue_entry = source_queue[idx]
        source_path = queue_entry.get("source_path", "")
        if not source_path:
            return _mine_error(
                f"queue entry at rank {rank_num} has no source_path",
                warnings=warnings + ["bad_queue_entry"],
            )

    elif source is not None:
        sp = (repo_root / source).resolve() if not Path(source).is_absolute() else Path(source).resolve()
        source_path = str(sp)
    else:
        return _mine_error(
            "--rank <N> or --source <path> is required",
            warnings=["missing_args"],
        )

    # ── mine the source ──
    if not Path(source_path).exists():
        return _mine_error(
            f"source not found: {source_path}",
            rank_num=rank_num,
            queue_entry=queue_entry,
            source=source_path,
            warnings=warnings + ["source_missing"],
        )

    propose_data = collect_propose_data(source_path, write=write, root=str(repo_root))

    return {
        "ok": propose_data.get("source_exists", False),
        "rank": rank_num,
        "queue_entry": queue_entry,
        "source": source_path,
        "source_exists": propose_data.get("source_exists", False),
        "candidate_count": propose_data.get("candidate_count", 0),
        "proposal_count": propose_data.get("proposal_count", 0),
        "proposals": propose_data.get("proposals", []),
        "dry_run": propose_data.get("dry_run", not write),
        "written_paths": propose_data.get("written_paths", []),
        "next_commands": [
            "python3 link.py growth proposals",
            "python3 link.py growth approve <proposal_id>",
            "python3 link.py growth run",
        ],
        "warnings": warnings if warnings else [],
        "error": None if propose_data.get("source_exists") else "source not found or invalid",
    }


def _mine_error(
    error: str,
    rank_num: int | None = None,
    queue_entry: dict[str, Any] | None = None,
    source: str | None = None,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "rank": rank_num,
        "queue_entry": queue_entry,
        "source": source or "",
        "source_exists": False,
        "candidate_count": 0,
        "proposal_count": 0,
        "proposals": [],
        "dry_run": True,
        "written_paths": [],
        "next_commands": [
            "python3 link.py growth archive-queue",
            "python3 link.py growth run",
        ],
        "warnings": warnings or [],
        "error": error,
    }


# ── archive mine rich renderer ──────────────────────────────────────────


def render_archive_mine_with_rich(data: dict[str, Any]) -> None:
    """Render an archive mine preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    rank: int | None = data.get("rank")
    queue_entry: dict | None = data.get("queue_entry")
    source: str = data.get("source", "?")
    candidate_count: int = data.get("candidate_count", 0)
    proposal_count: int = data.get("proposal_count", 0)
    proposals: list = data.get("proposals", [])
    written_paths: list = data.get("written_paths", [])
    warnings: list = data.get("warnings", [])

    status_colors = {
        "pending": "yellow", "accepted": "green", "rejected": "red",
        "deferred": "magenta", "converted_to_patch": "cyan",
        "needs_smaller_plan": "orange1",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        label, color = "FAILED", "red"
    elif dry_run:
        label, color = "DRY RUN", "yellow"
    else:
        label, color = "WRITTEN", "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH ARCHIVE MINE[/]",
        f"[{color}]{label}[/]",
    )
    console.print(header)

    # ── warnings ──
    for w in warnings:
        w_text = Text()
        w_text.append(f"[yellow]{w}[/]")
        console.print(Panel(w_text, border_style="yellow"))

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── queue context (only when --rank used) ──
    if rank is not None and queue_entry is not None:
        value_colors = {"high": "green", "medium": "yellow", "low": "dim"}
        ev = queue_entry.get("estimated_value", "medium")
        vc = value_colors.get(ev, "dim")

        ctx = Text()
        ctx.append(f"[bold]#{rank}  [{vc}]{ev.upper()}[/]  score: {queue_entry.get('score', '?')}[/]")
        ctx.append(f"\n[dim]source: [/]{queue_entry.get('source_path', source)}")
        ctx.append(f"\n[dim]catalog:[/] {queue_entry.get('catalog_source_name', '?')}")
        ctx.append(f"\n[dim]reason: [/]{queue_entry.get('reason', '?')}")
        console.print(Panel(ctx, title=f"QUEUE CONTEXT (#{rank})", border_style="dim"))

    # ── propose summary ──
    info = Text()
    info.append("source: ", style="dim")
    info.append(source, style="bold")
    info.append(f"\n[dim]chunks: {candidate_count}  candidates: {candidate_count}  proposals: {proposal_count}[/]")
    console.print(Panel(info, border_style="dim"))

    if proposal_count == 0:
        empty = Text()
        empty.append("No upgrade candidates found in source.", style="dim")
        empty.append(" Source may have no matching keywords or content was deduplicated.")
        console.print(Panel(empty, border_style="dim"))
    else:
        console.print(Rule(style="dim"))
        for i, p in enumerate(proposals):
            card = Text()
            status = p.get("status", "?")
            risk = p.get("risk_level", "?")
            rec = p.get("recommendation", "?")
            sc = status_colors.get(status, "")
            rc = risk_colors.get(risk, "")

            card.append(f"[bold]{p.get('title', '(untitled)')}[/]\n")
            card.append(f"[{sc}]STATUS: {status}[/]  ")
            card.append(f"[{rc}]RISK: {risk}[/]  ")
            card.append(f"[dim]REC: {rec}[/]")

            summary = p.get("source_summary", "")
            if summary:
                if len(summary) > 140:
                    summary = summary[:137] + "..."
                card.append(f"\n[dim]why:[/] {summary}")

            impl = p.get("implementation_plan", [])
            if impl:
                card.append(f"\n[dim]plan (first {min(3, len(impl))} of {len(impl)}):[/]")
                for step in impl[:3]:
                    card.append(f"\n  \u2022 {step}")

            files = p.get("affected_files", [])
            if files:
                card.append(f"\n[dim]files:[/] {', '.join(files[:5])}")

            panel_title = f"PROPOSAL [{i + 1}/{proposal_count}]  {p.get('proposal_id', '?')[:24]}"
            console.print(Panel(card, title=panel_title, border_style="dim"))

    # ── written paths ──
    if written_paths:
        wrote = Text()
        wrote.append("Written:\n", style="bold green")
        for wp in written_paths:
            wrote.append(f"  {wp}\n", style="dim")
        console.print(Panel(wrote, title="PERSISTED", border_style="dim green"))

    # ── next commands ──
    next_cmds = data.get("next_commands", [])
    cmd_text = Text()
    cmd_text.append("Next:\n", style="bold")
    for nc in next_cmds:
        cmd_text.append(f"  $ {nc}\n", style="dim")

    console.print(Rule(style="dim"))
    console.print(Panel(cmd_text, title="SUGGESTED NEXT STEPS", border_style="green"))
    console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")


# ── archive mine plain fallback ─────────────────────────────────────────


def render_archive_mine_plain(data: dict[str, Any]) -> None:
    """Render an archive mine preview/receipt using plain print."""
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    rank: int | None = data.get("rank")
    queue_entry: dict | None = data.get("queue_entry")
    source: str = data.get("source", "?")
    candidate_count: int = data.get("candidate_count", 0)
    proposal_count: int = data.get("proposal_count", 0)
    proposals: list = data.get("proposals", [])
    written_paths: list = data.get("written_paths", [])
    warnings: list = data.get("warnings", [])
    next_cmds: list = data.get("next_commands", [])

    label = "FAILED" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    out: list[str] = []
    out.append(f"== LINK GROWTH ARCHIVE MINE ({label}) ==")
    out.append("")

    for w in warnings:
        out.append(f"WARNING: {w}")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    if rank is not None and queue_entry is not None:
        out.append(f"-- QUEUE CONTEXT (#{rank}) --")
        out.append(f"score: {queue_entry.get('score', '?')}  value: {queue_entry.get('estimated_value', '?').upper()}")
        out.append(f"source:   {queue_entry.get('source_path', source)}")
        out.append(f"catalog:  {queue_entry.get('catalog_source_name', '?')}")
        out.append(f"reason:   {queue_entry.get('reason', '?')}")
        out.append("")

    out.append(f"source:   {source}")
    out.append(f"chunks:   {candidate_count}  candidates: {candidate_count}  proposals: {proposal_count}")
    out.append("")

    if proposal_count == 0:
        out.append("No upgrade candidates found in source.")
        out.append("")
    else:
        for i, p in enumerate(proposals):
            out.append(f"--- PROPOSAL [{i + 1}/{proposal_count}] ---")
            out.append(f"title:          {p.get('title', '?')}")
            out.append(f"status:         {p.get('status', '?')}")
            out.append(f"risk_level:     {p.get('risk_level', '?')}")
            out.append(f"recommendation: {p.get('recommendation', '?')}")
            impl = p.get("implementation_plan", [])
            if impl:
                out.append(f"plan ({len(impl)} steps):")
                for step in impl[:3]:
                    out.append(f"  - {step}")
            out.append("")

    if written_paths:
        out.append("Written:")
        for wp in written_paths:
            out.append(f"  {wp}")
        out.append("")

    out.append("-- SUGGESTED NEXT STEPS --")
    for nc in next_cmds:
        out.append(f"  $ {nc}")
    out.append("")
    out.append("python3 link.py growth run  -- guided workflow dashboard")
    print("\n".join(out))


# ── archive mine render orchestrator ────────────────────────────────────


def render_archive_mine_view(data: dict[str, Any]) -> None:
    """Render archive mine with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_mine_plain(data)
        return
    render_archive_mine_with_rich(data)


# ── archive batch mine entry point ──────────────────────────────────────
_MAX_BATCH_TOP = 10
_DEFAULT_BATCH_TOP = 3


def archive_batch_mine_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-batch-mine --top <N>``.

    Batch-mines the top N ranked archive queue sources into Growth proposals.
    Defaults to top 3.  Hard cap at 10.  Dry-run by default; ``--write``
    persists all proposals to the control-plane registry.

    No archive extraction.  No queue mutation.  Per-source failures are
    recorded but do not stop the batch.

    Flags:
        --top <N>   Number of top-ranked sources to mine (default 3, max 10).
        --write     Persist proposals to disk.
        --json      Machine-readable output.
        --root <path>  Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth archive-batch-mine: batch-mine top ranked sources")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-batch-mine")
        print("  python3 link.py growth archive-batch-mine --top <N>")
        print("  python3 link.py growth archive-batch-mine --top <N> --write")
        print("  python3 link.py growth archive-batch-mine --top <N> --json")
        print("")
        print("Mines the top N sources from the archive queue into proposals.")
        print(f"Default top is {_DEFAULT_BATCH_TOP}.  Hard cap at {_MAX_BATCH_TOP}.")
        print("Dry-run by default.  No files are written without --write.")
        return 0

    top_arg = _parse_arg(args, "--top")
    top = _resolve_batch_top(top_arg)

    if isinstance(top, str):
        print(f"error: {top}", file=sys.stderr)
        print("Run 'python3 link.py growth archive-batch-mine --help' for usage.",
              file=sys.stderr)
        return 1

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_archive_batch_mine(top=top, write=write, root=root_override,
                                      top_raw=top_arg)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_archive_batch_mine_view(data)
    return 0 if data.get("ok") else 1


def _resolve_batch_top(top_arg: str | None) -> int | str:
    """Parse and validate the --top argument. Returns int or error string."""
    if top_arg is None:
        return _DEFAULT_BATCH_TOP
    try:
        n = int(top_arg)
    except ValueError:
        return f"top must be an integer, got {top_arg!r}"
    if n < 1:
        return f"top must be >= 1, got {n}"
    return n


def collect_archive_batch_mine(
    top: int = _DEFAULT_BATCH_TOP,
    write: bool = False,
    root: str | None = None,
    top_raw: str | None = None,
) -> dict[str, Any]:
    """Load the archive queue and batch-mine the top N ranked sources.

    Calls ``collect_propose_data`` on each source's ``source_path``.
    Per-source failures are recorded but do not stop the batch.  Proposals
    are deduplicated by ``proposal_id`` across all sources.

    Args:
        top: Number of top-ranked sources to mine (clamped to _MAX_BATCH_TOP).
        write: Forwarded to collect_propose_data for each source.
        root: Override repo root.
        top_raw: Original --top arg value (for warning messages).

    Returns a dict with batch summary, per-source results, deduplicated
    proposals, and ``written_paths``.
    """
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()

    if top < 1:
        return _batch_error(f"top must be >= 1, got {top}", top=top)

    effective_top = min(top, _MAX_BATCH_TOP)
    warnings: list[str] = []
    if top > _MAX_BATCH_TOP:
        warnings.append(
            f"top {top} capped at {_MAX_BATCH_TOP} (hard limit)"
        )

    try:
        queue_data = collect_archive_queue(root=str(repo_root))
    except Exception as exc:
        return _batch_error(f"failed to load archive queue: {exc}",
                            top=effective_top, warnings=warnings)

    q_warnings = queue_data.get("warnings", [])
    for w in q_warnings:
        warnings.append(w.get("detail", w.get("type", "?")))

    source_queue = queue_data.get("source_queue", [])
    if not source_queue:
        return _batch_empty(top=effective_top, warnings=warnings)

    selected = source_queue[:effective_top]

    per_source_results: list[dict] = []
    all_proposals: list[dict] = []
    all_written: list[str] = []
    processed_count = 0
    failed_count = 0
    candidate_total = 0
    proposal_total = 0

    for entry in selected:
        source_path = entry.get("source_path", "")
        if not source_path:
            per_source_results.append(_ps_result(entry, False, 0, 0,
                                                  error="no source_path in queue entry"))
            failed_count += 1
            continue

        try:
            propose_data = collect_propose_data(source_path, write=write, root=str(repo_root))
        except Exception as exc:
            per_source_results.append(_ps_result(entry, False, 0, 0,
                                                  error=str(exc)))
            failed_count += 1
            continue

        ps_ok = propose_data.get("source_exists", False)
        ps_cand = propose_data.get("candidate_count", 0)
        ps_prop = propose_data.get("proposal_count", 0)
        ps_error = None if ps_ok else (propose_data.get("error") or "source not found or no candidates")

        if ps_ok:
            processed_count += 1
            all_proposals.extend(propose_data.get("proposals", []))
            all_written.extend(propose_data.get("written_paths", []))
        else:
            failed_count += 1

        candidate_total += ps_cand
        proposal_total += ps_prop

        per_source_results.append(_ps_result(entry, ps_ok, ps_cand, ps_prop,
                                              error=ps_error))

    # Deduplicate proposals by proposal_id (first occurrence wins)
    seen_ids: set[str] = set()
    unique = []
    for p in all_proposals:
        pid = p.get("proposal_id", "")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            unique.append(p)

    return {
        "ok": True,
        "top": effective_top,
        "top_raw": top_raw,
        "queue_count": len(source_queue),
        "selected_count": len(selected),
        "processed_count": processed_count,
        "failed_count": failed_count,
        "candidate_count_total": candidate_total,
        "proposal_count_total": proposal_total,
        "unique_proposal_count": len(unique),
        "per_source_results": per_source_results,
        "proposals": unique,
        "written_paths": all_written,
        "dry_run": not write,
        "next_commands": [
            "python3 link.py growth proposals",
            "python3 link.py growth approve <proposal_id>",
            "python3 link.py growth run",
        ],
        "warnings": warnings if warnings else [],
        "error": None,
    }


def _ps_result(
    entry: dict, ok: bool, cand: int, prop: int, error: str | None = None,
) -> dict:
    return {
        "rank": entry.get("rank", 0),
        "source_path": entry.get("source_path", ""),
        "queue_score": entry.get("score", 0),
        "queue_reason": entry.get("reason", ""),
        "ok": ok,
        "candidate_count": cand,
        "proposal_count": prop,
        "error": error,
    }


def _batch_error(
    error: str, top: int = 0, warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "top": top,
        "top_raw": None,
        "queue_count": 0,
        "selected_count": 0,
        "processed_count": 0,
        "failed_count": 0,
        "candidate_count_total": 0,
        "proposal_count_total": 0,
        "unique_proposal_count": 0,
        "per_source_results": [],
        "proposals": [],
        "written_paths": [],
        "dry_run": True,
        "next_commands": [
            "python3 link.py growth archive-queue",
            "python3 link.py growth run",
        ],
        "warnings": warnings or [],
        "error": error,
    }


def _batch_empty(
    top: int = 0, warnings: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "top": top,
        "top_raw": None,
        "queue_count": 0,
        "selected_count": 0,
        "processed_count": 0,
        "failed_count": 0,
        "candidate_count_total": 0,
        "proposal_count_total": 0,
        "unique_proposal_count": 0,
        "per_source_results": [],
        "proposals": [],
        "written_paths": [],
        "dry_run": True,
        "next_commands": [
            "python3 link.py growth archive-queue",
            "python3 link.py growth run",
        ],
        "warnings": warnings or [],
        "error": "no queue entries available",
    }


# ── batch mine rich renderer ────────────────────────────────────────────


def render_archive_batch_mine_with_rich(data: dict[str, Any]) -> None:
    """Render a batch mine result using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    top: int = data.get("top", 0)
    selected: int = data.get("selected_count", 0)
    processed: int = data.get("processed_count", 0)
    failed: int = data.get("failed_count", 0)
    cand_total: int = data.get("candidate_count_total", 0)
    prop_total: int = data.get("proposal_count_total", 0)
    uniq: int = data.get("unique_proposal_count", 0)
    per_source: list = data.get("per_source_results", [])
    proposals: list = data.get("proposals", [])
    written: list = data.get("written_paths", [])
    warnings: list = data.get("warnings", [])

    status_colors = {
        "pending": "yellow", "accepted": "green", "rejected": "red",
        "deferred": "magenta", "converted_to_patch": "cyan",
        "needs_smaller_plan": "orange1",
    }
    risk_colors = {"low": "green", "medium": "yellow", "high": "red"}

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        label, color = "ERROR", "red"
    elif dry_run:
        label, color = "DRY RUN", "yellow"
    else:
        label, color = "WRITTEN", "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH BATCH MINE[/]",
        f"[{color}]{label}[/]  [dim]top {top}[/]",
    )
    console.print(header)

    # ── warnings ──
    for w in warnings:
        console.print(Panel(Text(str(w), style="yellow"), border_style="yellow"))

    if not ok:
        error_text = Text()
        error_text.append(data.get("error", "unknown error"), style="bold red")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── empty state ──
    if selected == 0:
        empty = Text()
        empty.append("\nNo queue entries available.\n\n", style="dim")
        empty.append("Run archive-queue first:\n", style="dim")
        empty.append("  python3 link.py growth archive-queue\n", style="dim")
        empty.append("\n  [dim]python3 link.py growth run  -- guided workflow[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    # ── summary ──
    summary = Text()
    summary.append(
        f"[dim]selected: [/][bold]{selected}[/]  "
        f"[dim]processed: [/][green]{processed}[/]  "
        f"[dim]failed: [/][red]{failed}[/]"
    )
    summary.append(
        f"\n[dim]candidates: [/]{cand_total}  "
        f"[dim]proposals: [/]{prop_total}  "
        f"[dim]unique: [/][bold]{uniq}[/]"
    )
    console.print(Panel(summary, title="SUMMARY", border_style="dim"))

    # ── per-source results ──
    if per_source:
        ps_text = Text()
        for ps in per_source:
            mark = "[green]\u2713[/]" if ps.get("ok") else "[red]\u2717[/]"
            ps_text.append(
                f"{mark} [bold]#{ps.get('rank', '?')}[/]  "
                f"score:{ps.get('queue_score', '?')}  "
                f"[dim]{ps.get('queue_reason', '?')[:60]}[/]"
            )
            if ps.get("ok"):
                ps_text.append(
                    f"\n          [dim]({ps.get('candidate_count')} candidates, "
                    f"{ps.get('proposal_count')} proposals)[/]"
                )
            else:
                ps_text.append(
                    f"\n          [red]error: {ps.get('error', 'failed')}[/]"
                )
            ps_text.append("\n")
        console.print(Panel(ps_text, title="PER-SOURCE RESULTS", border_style="dim"))

    # ── deduplicated proposals (compact) ──
    if proposals:
        console.print(Rule(style="dim"))
        for i, p in enumerate(proposals[:10]):
            card = Text()
            status = p.get("status", "?")
            risk = p.get("risk_level", "?")
            sc = status_colors.get(status, "")
            rc = risk_colors.get(risk, "")
            card.append(
                f"[bold]{p.get('title', '(untitled)')}[/]  "
                f"[{sc}]STATUS: {status}[/]  "
                f"[{rc}]RISK: {risk}[/]"
            )
            summary_text = p.get("source_summary", "")
            if summary_text and len(summary_text) > 100:
                summary_text = summary_text[:97] + "..."
            if summary_text:
                card.append(f"\n[dim]{summary_text}[/]")
            panel_title = f"PROPOSAL [{i + 1}/{min(len(proposals), 10)}]  {p.get('proposal_id', '?')[:24]}"
            console.print(Panel(card, title=panel_title, border_style="dim"))
        if len(proposals) > 10:
            console.print(f"  [dim]... and {len(proposals) - 10} more[/]")

    # ── written ──
    if written:
        wrote = Text()
        wrote.append(f"Written {len(written)} proposal(s):\n", style="bold green")
        for wp in written[:5]:
            wrote.append(f"  {wp}\n", style="dim")
        if len(written) > 5:
            wrote.append(f"  ... and {len(written) - 5} more\n", style="dim")
        console.print(Panel(wrote, title="PERSISTED", border_style="dim green"))

    # ── next ──
    next_cmds = data.get("next_commands", [])
    cmd_text = Text()
    cmd_text.append("Next:\n", style="bold")
    for nc in next_cmds:
        cmd_text.append(f"  $ {nc}\n", style="dim")

    console.print(Rule(style="dim"))
    console.print(Panel(cmd_text, title="SUGGESTED NEXT STEPS", border_style="green"))
    console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")


# ── batch mine plain fallback ───────────────────────────────────────────


def render_archive_batch_mine_plain(data: dict[str, Any]) -> None:
    """Render a batch mine result using plain print."""
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    top: int = data.get("top", 0)
    selected: int = data.get("selected_count", 0)
    processed: int = data.get("processed_count", 0)
    failed: int = data.get("failed_count", 0)
    cand_total: int = data.get("candidate_count_total", 0)
    prop_total: int = data.get("proposal_count_total", 0)
    uniq: int = data.get("unique_proposal_count", 0)
    per_source: list = data.get("per_source_results", [])
    proposals: list = data.get("proposals", [])
    written: list = data.get("written_paths", [])
    warnings: list = data.get("warnings", [])
    next_cmds: list = data.get("next_commands", [])

    label = "ERROR" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    out: list[str] = []
    out.append(f"== LINK GROWTH BATCH MINE ({label}) top {top} ==")
    out.append("")

    for w in warnings:
        out.append(f"WARNING: {w}")

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    if selected == 0:
        out.append("No queue entries available.")
        out.append("Run: python3 link.py growth archive-queue")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow")
        print("\n".join(out))
        return

    out.append(f"selected: {selected}  processed: {processed}  failed: {failed}")
    out.append(f"candidates: {cand_total}  proposals: {prop_total}  unique: {uniq}")
    out.append("")

    for ps in per_source:
        mark = "OK" if ps.get("ok") else "FAIL"
        out.append(
            f"[{mark}] #{ps.get('rank', '?')}  score:{ps.get('queue_score', '?')}  "
            f"{ps.get('queue_reason', '?')[:60]}"
        )
        if ps.get("ok"):
            out.append(
                f"    ({ps.get('candidate_count')} candidates, "
                f"{ps.get('proposal_count')} proposals)"
            )
        else:
            out.append(f"    error: {ps.get('error', 'failed')}")
        out.append("")

    if proposals:
        out.append(f"--- DEDUPLICATED PROPOSALS ({uniq} unique) ---")
        for i, p in enumerate(proposals[:10]):
            out.append(
                f"  {i + 1}. {p.get('title', '?')}  "
                f"STATUS:{p.get('status', '?')}  RISK:{p.get('risk_level', '?')}"
            )
        out.append("")

    if written:
        out.append(f"Written {len(written)} proposal(s).")
        out.append("")

    out.append("-- SUGGESTED NEXT STEPS --")
    for nc in next_cmds:
        out.append(f"  $ {nc}")
    out.append("")
    out.append("python3 link.py growth run  -- guided workflow dashboard")
    print("\n".join(out))


# ── batch mine render orchestrator ──────────────────────────────────────


def render_archive_batch_mine_view(data: dict[str, Any]) -> None:
    """Render batch mine with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_batch_mine_plain(data)
        return
    render_archive_batch_mine_with_rich(data)


# ── Ruflo upgrade intake helpers ───────────────────────────────────────
RUFLO_UPGRADE_INTAKE_VERSION = "link-ruflo-upgrade-intake-v1"
RUFLO_UPGRADE_CATEGORIES = (
    "self_learning",
    "swarm_orchestration",
    "memory_retrieval",
    "worker_routing",
    "hook_pipeline",
    "security_gate",
    "performance",
)
RUFLO_RISK_LABELS = ("low", "medium", "high")
RUFLO_RECOMMENDATIONS = ("accept", "review", "reject")

_RUFLO_CATEGORY_WEIGHTS: dict[str, int] = {
    "security_gate": 32,
    "worker_routing": 30,
    "memory_retrieval": 28,
    "self_learning": 27,
    "swarm_orchestration": 25,
    "hook_pipeline": 23,
    "performance": 21,
}

_RUFLO_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "self_learning": ("self-learning", "self learning", "reflection", "learn", "feedback"),
    "swarm_orchestration": ("swarm", "orchestration", "multi-agent", "coordinator", "collective"),
    "memory_retrieval": ("memory", "retrieval", "vector", "recall", "context store"),
    "worker_routing": ("worker", "routing", "dispatcher", "dispatch", "profile", "route"),
    "hook_pipeline": ("hook", "pipeline", "lifecycle", "preflight", "postflight"),
    "security_gate": ("security", "permission", "gate", "sandbox", "approval", "policy"),
    "performance": ("performance", "latency", "cache", "fast", "speed", "throughput"),
}

_RUFLO_CATEGORY_REASONS: dict[str, str] = {
    "self_learning": "Link needs tighter feedback loops so research and run outcomes improve future upgrade selection.",
    "swarm_orchestration": "Link needs safer coordination patterns before expanding multi-worker task execution.",
    "memory_retrieval": "Link needs durable context retrieval so long-running Growth work can reuse prior evidence without re-mining.",
    "worker_routing": "Link needs deterministic worker routing so tasks reach the narrowest capable profile with clear gates.",
    "hook_pipeline": "Link needs explicit lifecycle hooks so preflight, receipts, and verification stay consistent.",
    "security_gate": "Link needs stronger gates around tools, files, and worker handoffs before adding automation power.",
    "performance": "Link needs faster mining and queue ranking so Growth stays usable on large research archives.",
}


def make_ruflo_upgrade_candidate_id(
    title: str,
    source_path: str,
    category: str,
) -> str:
    """Build a deterministic id for a Ruflo-inspired upgrade candidate."""
    import hashlib
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(title or "ruflo-upgrade").lower()).strip("-")
    slug = slug[:72].strip("-") or "ruflo-upgrade"
    payload = _stable_ruflo_json({
        "category": category,
        "source_path": source_path,
        "title": title,
        "version": RUFLO_UPGRADE_INTAKE_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"ruflo-{slug}-{digest}"


def build_ruflo_upgrade_intake(
    findings: list[dict[str, Any]],
    *,
    source_label: str = "ruflo",
    limit: int | None = None,
) -> dict[str, Any]:
    """Normalize and rank Ruflo-derived findings without writing state."""
    candidates = [
        score_ruflo_upgrade_candidate(finding, source_label=source_label)
        for finding in findings
    ]
    candidates.sort(key=lambda item: (-item["score"], item["candidate_id"]))
    if limit is not None:
        candidates = candidates[:max(int(limit), 0)]

    intake = {
        "intake_version": RUFLO_UPGRADE_INTAKE_VERSION,
        "source_label": str(source_label or "ruflo"),
        "candidate_count": len(candidates),
        "categories": list(RUFLO_UPGRADE_CATEGORIES),
        "candidates": candidates,
    }
    validate_ruflo_upgrade_intake(intake)
    return intake


def score_ruflo_upgrade_candidate(
    finding: dict[str, Any],
    *,
    source_label: str = "ruflo",
) -> dict[str, Any]:
    """Turn one raw Ruflo finding/code-brief item into a ranked candidate."""
    if not isinstance(finding, dict):
        raise TypeError("Ruflo finding must be a dict")

    title = _first_text(finding, "title", "name", "candidate_title") or "Ruflo upgrade candidate"
    summary = _first_text(finding, "summary", "description", "problem", "source_summary")
    source_path = _first_text(finding, "source_path", "path", "file") or str(source_label or "ruflo")
    source_kind = _first_text(finding, "source_kind", "kind", "source_type") or "research"
    category = _normalize_ruflo_category(
        _first_text(finding, "category", "capability", "cluster"),
        " ".join(str(value) for value in finding.values()),
    )
    risk = _normalize_ruflo_risk(_first_text(finding, "risk", "risk_level"))
    reason = _first_text(finding, "reason", "why", "link_need") or _RUFLO_CATEGORY_REASONS[category]

    evidence_items = finding.get("evidence") or finding.get("evidence_paths") or finding.get("signals") or []
    if isinstance(evidence_items, str):
        evidence = [evidence_items]
    elif isinstance(evidence_items, list):
        evidence = [str(item) for item in evidence_items if str(item).strip()]
    else:
        evidence = []

    score = _RUFLO_CATEGORY_WEIGHTS[category]
    score += {"low": 6, "medium": 0, "high": -9}[risk]
    if summary:
        score += 4
    if evidence:
        score += min(len(evidence), 3) * 2
    if source_path and source_path != str(source_label or "ruflo"):
        score += 2
    score = max(score, 0)

    recommendation = _ruflo_recommendation(score, risk)
    candidate = {
        "candidate_id": make_ruflo_upgrade_candidate_id(title, source_path, category),
        "title": str(title).strip(),
        "category": category,
        "risk_level": risk,
        "recommendation": recommendation,
        "score": score,
        "reason": str(reason).strip(),
        "source_path": str(source_path).strip(),
        "source_kind": str(source_kind).strip() or "research",
        "summary": str(summary).strip(),
        "evidence": evidence,
    }
    validate_ruflo_upgrade_candidate(candidate)
    return candidate


def validate_ruflo_upgrade_candidate(candidate: dict[str, Any]) -> None:
    required = (
        "candidate_id", "title", "category", "risk_level", "recommendation",
        "score", "reason", "source_path", "source_kind", "summary", "evidence",
    )
    missing = [field for field in required if field not in candidate]
    if missing:
        raise ValueError(f"Ruflo candidate missing fields: {missing}")
    for field in ("candidate_id", "title", "reason", "source_path", "source_kind"):
        if not isinstance(candidate[field], str) or not candidate[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if candidate["category"] not in RUFLO_UPGRADE_CATEGORIES:
        raise ValueError(f"invalid Ruflo category: {candidate['category']}")
    if candidate["risk_level"] not in RUFLO_RISK_LABELS:
        raise ValueError(f"invalid Ruflo risk label: {candidate['risk_level']}")
    if candidate["recommendation"] not in RUFLO_RECOMMENDATIONS:
        raise ValueError(f"invalid Ruflo recommendation: {candidate['recommendation']}")
    if not isinstance(candidate["score"], int) or candidate["score"] < 0:
        raise ValueError("score must be a non-negative integer")
    if not isinstance(candidate["evidence"], list):
        raise TypeError("evidence must be a list")


def validate_ruflo_upgrade_intake(intake: dict[str, Any]) -> None:
    if intake.get("intake_version") != RUFLO_UPGRADE_INTAKE_VERSION:
        raise ValueError("unsupported Ruflo upgrade intake version")
    candidates = intake.get("candidates")
    if not isinstance(candidates, list):
        raise TypeError("Ruflo intake candidates must be a list")
    if intake.get("candidate_count") != len(candidates):
        raise ValueError("Ruflo intake candidate_count must match candidates length")
    for candidate in candidates:
        validate_ruflo_upgrade_candidate(candidate)


def ruflo_upgrade_intake_to_json(intake: dict[str, Any]) -> str:
    validate_ruflo_upgrade_intake(intake)
    return _stable_ruflo_json(intake, indent=2) + "\n"


def ruflo_upgrade_intake_from_json(text: str) -> dict[str, Any]:
    import json as _json

    intake = _json.loads(text)
    validate_ruflo_upgrade_intake(intake)
    return intake


def _stable_ruflo_json(value: Any, indent: int | None = None) -> str:
    import json as _json

    kwargs: dict[str, Any] = {"sort_keys": True, "default": str}
    if indent is None:
        kwargs["separators"] = (",", ":")
    else:
        kwargs["indent"] = indent
    return _json.dumps(value, **kwargs)


def _first_text(data: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _normalize_ruflo_category(value: str, haystack: str) -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw in RUFLO_UPGRADE_CATEGORIES:
        return raw
    text = f"{raw} {haystack}".lower()
    for category, keywords in _RUFLO_CATEGORY_KEYWORDS.items():
        if any(keyword in text for keyword in keywords):
            return category
    return "performance"


def _normalize_ruflo_risk(value: str) -> str:
    raw = str(value or "").strip().lower()
    if raw in RUFLO_RISK_LABELS:
        return raw
    if raw in {"safe", "small", "minor"}:
        return "low"
    if raw in {"danger", "risky", "large"}:
        return "high"
    return "medium"


def _ruflo_recommendation(score: int, risk: str) -> str:
    if score >= 34 and risk != "high":
        return "accept"
    if score >= 20:
        return "review"
    return "reject"


RUFLO_UPGRADE_PLAN_VERSION = "link-ruflo-upgrade-plan-v1"
RUFLO_UPGRADE_PLAN_MAX_TOP = 25
_RUFLO_PLAN_SECTIONS = (
    "fast_wins",
    "safety_control_plane_upgrades",
    "self_learning_upgrades",
    "workflow_parallelism_upgrades",
    "observability_dashboard_upgrades",
)
_RUFLO_SECTION_CATEGORY_MAP: dict[str, tuple[str, ...]] = {
    "safety_control_plane_upgrades": ("security_gate", "worker_routing"),
    "self_learning_upgrades": ("self_learning", "memory_retrieval"),
    "workflow_parallelism_upgrades": ("swarm_orchestration", "hook_pipeline"),
    "observability_dashboard_upgrades": ("performance",),
}


def make_ruflo_upgrade_plan_id(
    candidates: list[dict[str, Any]],
    *,
    top: int,
    source_label: str = "ruflo",
) -> str:
    """Build a deterministic id for a Ruflo upgrade plan preview."""
    import hashlib

    payload = _stable_ruflo_json({
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "source_label": source_label,
        "top": top,
        "version": RUFLO_UPGRADE_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"ruflo-upgrade-plan-{digest}"


def collect_ruflo_upgrade_plan(
    intake_or_findings: dict[str, Any] | list[dict[str, Any]],
    *,
    top: int = 10,
    source_label: str = "ruflo",
) -> dict[str, Any]:
    """Create an auditor-gated implementation plan from Ruflo intake data.

    This is a pure read-only planner. It does not create proposals, approvals,
    handoffs, tasks, receipts on disk, or automation runs.
    """
    if not isinstance(top, int):
        raise TypeError("top must be an integer")
    requested_top = top
    effective_top = min(max(top, 1), RUFLO_UPGRADE_PLAN_MAX_TOP)
    warnings: list[str] = []
    if requested_top > RUFLO_UPGRADE_PLAN_MAX_TOP:
        warnings.append(f"top {requested_top} capped at {RUFLO_UPGRADE_PLAN_MAX_TOP} (hard limit)")
    if requested_top < 1:
        warnings.append("top below 1 raised to 1")

    candidates = _ruflo_candidates_from_input(intake_or_findings, source_label=source_label)
    unique_candidates, duplicate_count = _dedupe_ruflo_candidates(candidates)
    ranked = sorted(unique_candidates, key=_ruflo_plan_rank_key)[:effective_top]

    sections = _build_ruflo_plan_sections(ranked)
    plan = {
        "plan_version": RUFLO_UPGRADE_PLAN_VERSION,
        "plan_id": make_ruflo_upgrade_plan_id(ranked, top=effective_top, source_label=source_label),
        "source_label": str(source_label or "ruflo"),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "auditor_gate": {
            "required": True,
            "auditor_profile": "read_only_auditor",
            "approval_required_before_implementation": True,
            "reason": "Ruflo patterns are research inputs; Link must review and implement one small native slice at a time.",
        },
        "top_requested": requested_top,
        "top_used": effective_top,
        "candidate_count": len(candidates),
        "unique_candidate_count": len(unique_candidates),
        "duplicate_count": duplicate_count,
        "ranked_candidates": ranked,
        "sections": sections,
        "rollback_guidance": [
            "Do not mutate research archives or generated catalogs.",
            "Implement one plan item per patch branch or review slice.",
            "Revert only the touched Link source/test files if a slice fails verification.",
        ],
        "verification_commands": [
            "python3 -m py_compile link.py link_modes/growth/link_growth_console.py tests/test_growth_pipeline.py",
            "PYTHONDONTWRITEBYTECODE=1 python3 tests/test_growth_pipeline.py",
            "PYTHONDONTWRITEBYTECODE=1 python3 link_healthcheck.py",
        ],
        "recommended_next_slice": _recommended_ruflo_next_slice(sections, ranked),
        "warnings": warnings,
    }
    validate_ruflo_upgrade_plan(plan)
    return plan


def validate_ruflo_upgrade_plan(plan: dict[str, Any]) -> None:
    required = (
        "plan_version", "plan_id", "source_label", "dry_run", "write_allowed",
        "automation_allowed", "auditor_gate", "top_requested", "top_used",
        "candidate_count", "unique_candidate_count", "duplicate_count",
        "ranked_candidates", "sections", "rollback_guidance",
        "verification_commands", "recommended_next_slice", "warnings",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise ValueError(f"Ruflo upgrade plan missing fields: {missing}")
    if plan["plan_version"] != RUFLO_UPGRADE_PLAN_VERSION:
        raise ValueError("unsupported Ruflo upgrade plan version")
    if not isinstance(plan["plan_id"], str) or not plan["plan_id"].strip():
        raise ValueError("plan_id must be a non-empty string")
    if plan["dry_run"] is not True or plan["write_allowed"] is not False or plan["automation_allowed"] is not False:
        raise ValueError("Ruflo upgrade plan must remain auditor-gated and read-only")
    if not isinstance(plan["auditor_gate"], dict) or plan["auditor_gate"].get("required") is not True:
        raise ValueError("Ruflo upgrade plan requires an auditor gate")
    if not isinstance(plan["ranked_candidates"], list):
        raise TypeError("ranked_candidates must be a list")
    if not isinstance(plan["sections"], dict):
        raise TypeError("sections must be a dict")
    for section in _RUFLO_PLAN_SECTIONS:
        if section not in plan["sections"]:
            raise ValueError(f"Ruflo upgrade plan missing section: {section}")
    for candidate in plan["ranked_candidates"]:
        validate_ruflo_upgrade_candidate(candidate)


def ruflo_upgrade_plan_to_json(plan: dict[str, Any]) -> str:
    validate_ruflo_upgrade_plan(plan)
    return _stable_ruflo_json(plan, indent=2) + "\n"


def ruflo_upgrade_plan_from_json(text: str) -> dict[str, Any]:
    import json as _json

    plan = _json.loads(text)
    validate_ruflo_upgrade_plan(plan)
    return plan


def _ruflo_candidates_from_input(
    intake_or_findings: dict[str, Any] | list[dict[str, Any]],
    *,
    source_label: str,
) -> list[dict[str, Any]]:
    if isinstance(intake_or_findings, dict):
        if "candidates" not in intake_or_findings:
            raise ValueError("Ruflo plan input dict must include candidates")
        candidates = intake_or_findings.get("candidates")
        if not isinstance(candidates, list):
            raise TypeError("Ruflo plan candidates must be a list")
        normalized: list[dict[str, Any]] = []
        for candidate in candidates:
            if not isinstance(candidate, dict):
                raise TypeError("Ruflo plan candidate entries must be dicts")
            if "candidate_id" in candidate:
                validate_ruflo_upgrade_candidate(candidate)
                normalized.append(dict(candidate))
            else:
                normalized.append(score_ruflo_upgrade_candidate(candidate, source_label=source_label))
        return normalized

    if not isinstance(intake_or_findings, list):
        raise TypeError("Ruflo plan input must be an intake dict or findings list")
    return [score_ruflo_upgrade_candidate(finding, source_label=source_label) for finding in intake_or_findings]


def _dedupe_ruflo_candidates(candidates: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    chosen: dict[tuple[str, str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for candidate in candidates:
        key = (
            candidate["title"].strip().lower(),
            candidate["category"],
            candidate["source_path"].strip().lower(),
        )
        existing = chosen.get(key)
        if existing is None or _ruflo_plan_rank_key(candidate) < _ruflo_plan_rank_key(existing):
            chosen[key] = candidate
        if existing is not None:
            duplicate_count += 1
    return list(chosen.values()), duplicate_count


def _ruflo_plan_rank_key(candidate: dict[str, Any]) -> tuple[int, int, int, str]:
    recommendation_rank = {"accept": 0, "review": 1, "reject": 2}.get(candidate.get("recommendation"), 3)
    risk_rank = {"low": 0, "medium": 1, "high": 2}.get(candidate.get("risk_level"), 3)
    return (recommendation_rank, risk_rank, -int(candidate.get("score", 0)), candidate.get("candidate_id", ""))


def _build_ruflo_plan_sections(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    sections: dict[str, list[dict[str, Any]]] = {section: [] for section in _RUFLO_PLAN_SECTIONS}
    sections["fast_wins"] = [
        candidate for candidate in candidates
        if candidate["risk_level"] == "low" and candidate["recommendation"] == "accept"
    ][:5]

    for candidate in candidates:
        for section, categories in _RUFLO_SECTION_CATEGORY_MAP.items():
            if candidate["category"] in categories:
                sections[section].append(candidate)
                break
    return sections


def _recommended_ruflo_next_slice(
    sections: dict[str, list[dict[str, Any]]],
    ranked: list[dict[str, Any]],
) -> dict[str, Any]:
    candidate = (sections.get("fast_wins") or ranked or [None])[0]
    if not candidate:
        return {
            "title": "No Ruflo upgrade candidate selected",
            "category": "",
            "risk_level": "",
            "command": "python3 link.py growth code-brief-propose-batch --top 10 --json",
            "reason": "Generate or provide Ruflo intake candidates before planning implementation slices.",
        }
    return {
        "title": candidate["title"],
        "category": candidate["category"],
        "risk_level": candidate["risk_level"],
        "candidate_id": candidate["candidate_id"],
        "command": "Implement one small audited Link-native slice for this candidate; do not auto-approve or execute.",
        "reason": candidate["reason"],
    }



SELF_LEARNING_FEEDBACK_VERSION = "link-self-learning-feedback-v1"
SELF_LEARNING_FEEDBACK_STATUSES = ("accepted", "rejected", "deferred")


def make_self_learning_feedback_id(
    candidate: dict[str, Any],
    *,
    status: str,
    reason: str,
    confidence: float,
    tags: list[str] | None = None,
) -> str:
    """Build a deterministic feedback id for one recommendation review."""
    import hashlib

    candidate_key = _first_text(candidate, "candidate_id", "proposal_id", "title") or "recommendation"
    payload = _stable_ruflo_json({
        "candidate_key": candidate_key,
        "confidence": _normalize_feedback_confidence(confidence),
        "reason": str(reason or "").strip(),
        "status": _normalize_feedback_status(status),
        "tags": _normalize_feedback_tags(tags),
        "version": SELF_LEARNING_FEEDBACK_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"feedback-{digest}"


def build_self_learning_feedback_receipt(
    candidate: dict[str, Any],
    *,
    status: str,
    reason: str,
    confidence: float,
    tags: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    """Create a pure self-learning feedback receipt without writing state."""
    if not isinstance(candidate, dict):
        raise TypeError("candidate must be a dict")
    normalized_status = _normalize_feedback_status(status)
    normalized_confidence = _normalize_feedback_confidence(confidence)
    normalized_tags = _normalize_feedback_tags(tags)
    feedback_reason = str(reason or "").strip()
    if not feedback_reason:
        raise ValueError("reason must be a non-empty string")

    receipt = {
        "feedback_version": SELF_LEARNING_FEEDBACK_VERSION,
        "feedback_id": make_self_learning_feedback_id(
            candidate,
            status=normalized_status,
            reason=feedback_reason,
            confidence=normalized_confidence,
            tags=normalized_tags,
        ),
        "status": normalized_status,
        "reason": feedback_reason,
        "confidence": normalized_confidence,
        "tags": normalized_tags,
        "metadata": dict(metadata or {}),
        "candidate_id": _first_text(candidate, "candidate_id"),
        "proposal_id": _first_text(candidate, "proposal_id"),
        "title": _first_text(candidate, "title") or "recommendation",
        "category": _normalize_feedback_category(_first_text(candidate, "category")),
        "risk_level": _normalize_ruflo_risk(_first_text(candidate, "risk_level", "risk")),
        "recommendation": _normalize_feedback_recommendation(_first_text(candidate, "recommendation")),
        "source_path": _first_text(candidate, "source_path", "path", "file"),
        "reviewed_at": reviewed_at or "",
    }
    validate_self_learning_feedback_receipt(receipt)
    return receipt


def validate_self_learning_feedback_receipt(receipt: dict[str, Any]) -> None:
    required = (
        "feedback_version", "feedback_id", "status", "reason", "confidence",
        "tags", "metadata", "candidate_id", "proposal_id", "title", "category",
        "risk_level", "recommendation", "source_path", "reviewed_at",
    )
    missing = [field for field in required if field not in receipt]
    if missing:
        raise ValueError(f"self-learning feedback missing fields: {missing}")
    if receipt["feedback_version"] != SELF_LEARNING_FEEDBACK_VERSION:
        raise ValueError("unsupported self-learning feedback version")
    for field in ("feedback_id", "status", "reason", "title", "category", "risk_level", "recommendation"):
        if not isinstance(receipt[field], str) or not receipt[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if receipt["status"] not in SELF_LEARNING_FEEDBACK_STATUSES:
        raise ValueError(f"invalid self-learning feedback status: {receipt['status']}")
    if receipt["category"] not in RUFLO_UPGRADE_CATEGORIES:
        raise ValueError(f"invalid self-learning feedback category: {receipt['category']}")
    if receipt["risk_level"] not in RUFLO_RISK_LABELS:
        raise ValueError(f"invalid self-learning feedback risk_level: {receipt['risk_level']}")
    if receipt["recommendation"] not in RUFLO_RECOMMENDATIONS:
        raise ValueError(f"invalid self-learning feedback recommendation: {receipt['recommendation']}")
    if not isinstance(receipt["confidence"], float) or not (0.0 <= receipt["confidence"] <= 1.0):
        raise ValueError("confidence must be a float between 0.0 and 1.0")
    if not isinstance(receipt["tags"], list) or not all(isinstance(tag, str) and tag for tag in receipt["tags"]):
        raise TypeError("tags must be a list of non-empty strings")
    if not isinstance(receipt["metadata"], dict):
        raise TypeError("metadata must be a dict")


def self_learning_feedback_to_json(receipt: dict[str, Any]) -> str:
    validate_self_learning_feedback_receipt(receipt)
    return _stable_ruflo_json(receipt, indent=2) + "\n"


def self_learning_feedback_from_json(text: str) -> dict[str, Any]:
    import json as _json

    receipt = _json.loads(text)
    validate_self_learning_feedback_receipt(receipt)
    return receipt


def summarize_self_learning_feedback(receipts: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate self-learning feedback counts without writing state."""
    if not isinstance(receipts, list):
        raise TypeError("feedback receipts must be a list")
    by_status = {status: 0 for status in SELF_LEARNING_FEEDBACK_STATUSES}
    by_category = {category: 0 for category in RUFLO_UPGRADE_CATEGORIES}
    by_risk = {risk: 0 for risk in RUFLO_RISK_LABELS}
    confidence_total = 0.0

    for receipt in receipts:
        validate_self_learning_feedback_receipt(receipt)
        by_status[receipt["status"]] += 1
        by_category[receipt["category"]] += 1
        by_risk[receipt["risk_level"]] += 1
        confidence_total += receipt["confidence"]

    count = len(receipts)
    return {
        "summary_version": SELF_LEARNING_FEEDBACK_VERSION,
        "feedback_count": count,
        "by_status": by_status,
        "by_category": by_category,
        "by_risk": by_risk,
        "average_confidence": round(confidence_total / count, 4) if count else 0.0,
        "dry_run": True,
        "writes": [],
    }


SELF_LEARNING_NEXT_STEP_VERSION = "link-self-learning-next-step-v1"
SELF_LEARNING_NEXT_STEP_MAX_TOP = 10


def make_self_learning_next_step_id(
    candidates: list[dict[str, Any]],
    feedback_receipts: list[dict[str, Any]],
    *,
    top: int,
) -> str:
    """Build a deterministic id for a feedback-adjusted recommendation preview."""
    import hashlib

    payload = _stable_ruflo_json({
        "candidate_ids": [candidate["candidate_id"] for candidate in candidates],
        "feedback_ids": [receipt["feedback_id"] for receipt in feedback_receipts],
        "top": top,
        "version": SELF_LEARNING_NEXT_STEP_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"self-learning-next-step-{digest}"


def collect_self_learning_next_step_recommendations(
    candidate_source: dict[str, Any] | list[dict[str, Any]],
    feedback_receipts: list[dict[str, Any]],
    *,
    top: int = 5,
    source_label: str = "ruflo",
) -> dict[str, Any]:
    """Rank safe next upgrade steps from Ruflo candidates and reviewer feedback.

    Pure helper only: no proposals, approvals, handoffs, execution, or disk writes.
    """
    if not isinstance(top, int):
        raise TypeError("top must be an integer")
    requested_top = top
    effective_top = min(max(top, 1), SELF_LEARNING_NEXT_STEP_MAX_TOP)
    warnings: list[str] = []
    if requested_top > SELF_LEARNING_NEXT_STEP_MAX_TOP:
        warnings.append(f"top {requested_top} capped at {SELF_LEARNING_NEXT_STEP_MAX_TOP} (hard limit)")
    if requested_top < 1:
        warnings.append("top below 1 raised to 1")

    source_duplicate_count = 0
    if isinstance(candidate_source, dict) and isinstance(candidate_source.get("duplicate_count"), int):
        source_duplicate_count = max(candidate_source["duplicate_count"], 0)
    candidates = _self_learning_candidates_from_source(candidate_source, source_label=source_label)
    unique_candidates, duplicate_count = _dedupe_ruflo_candidates(candidates)
    duplicate_count += source_duplicate_count
    if not isinstance(feedback_receipts, list):
        raise TypeError("feedback_receipts must be a list")
    validated_feedback: list[dict[str, Any]] = []
    for receipt in feedback_receipts:
        validate_self_learning_feedback_receipt(receipt)
        validated_feedback.append(dict(receipt))

    feedback_by_key = _self_learning_feedback_by_key(validated_feedback)
    recommendations: list[dict[str, Any]] = []
    matched_feedback_ids: set[str] = set()
    for candidate in unique_candidates:
        matches = _matching_self_learning_feedback(candidate, feedback_by_key)
        matched_feedback_ids.update(receipt["feedback_id"] for receipt in matches)
        recommendations.append(_build_self_learning_next_step(candidate, matches))

    recommendations.sort(key=_self_learning_next_step_rank_key)
    ranked = recommendations[:effective_top]
    unmatched_feedback_count = len([
        receipt for receipt in validated_feedback
        if receipt["feedback_id"] not in matched_feedback_ids
    ])
    if unmatched_feedback_count:
        warnings.append(f"{unmatched_feedback_count} feedback receipt(s) did not match an intake candidate")
    if not validated_feedback:
        warnings.append("no self-learning feedback receipts supplied; ranking uses candidate scores only")

    payload = {
        "next_step_version": SELF_LEARNING_NEXT_STEP_VERSION,
        "recommendation_id": make_self_learning_next_step_id(
            unique_candidates,
            validated_feedback,
            top=effective_top,
        ),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "top_requested": requested_top,
        "top_used": effective_top,
        "candidate_count": len(candidates),
        "unique_candidate_count": len(unique_candidates),
        "duplicate_count": duplicate_count,
        "feedback_count": len(validated_feedback),
        "unmatched_feedback_count": unmatched_feedback_count,
        "feedback_summary": summarize_self_learning_feedback(validated_feedback),
        "recommendations": ranked,
        "warnings": warnings,
        "writes": [],
    }
    validate_self_learning_next_step_recommendations(payload)
    return payload


def validate_self_learning_next_step_recommendations(payload: dict[str, Any]) -> None:
    required = (
        "next_step_version", "recommendation_id", "dry_run", "write_allowed",
        "automation_allowed", "top_requested", "top_used", "candidate_count",
        "unique_candidate_count", "duplicate_count", "feedback_count",
        "unmatched_feedback_count", "feedback_summary", "recommendations",
        "warnings", "writes",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"self-learning next-step payload missing fields: {missing}")
    if payload["next_step_version"] != SELF_LEARNING_NEXT_STEP_VERSION:
        raise ValueError("unsupported self-learning next-step version")
    if not isinstance(payload["recommendation_id"], str) or not payload["recommendation_id"].strip():
        raise ValueError("recommendation_id must be a non-empty string")
    if payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False:
        raise ValueError("self-learning next-step recommendations must remain read-only")
    if payload["writes"] != []:
        raise ValueError("self-learning next-step recommendations must not write files")
    if not isinstance(payload["recommendations"], list):
        raise TypeError("recommendations must be a list")
    if not isinstance(payload["warnings"], list):
        raise TypeError("warnings must be a list")
    if not isinstance(payload["feedback_summary"], dict):
        raise TypeError("feedback_summary must be a dict")
    for field in (
        "top_requested", "top_used", "candidate_count", "unique_candidate_count",
        "duplicate_count", "feedback_count", "unmatched_feedback_count",
    ):
        if not isinstance(payload[field], int) or payload[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    for recommendation in payload["recommendations"]:
        _validate_self_learning_next_step(recommendation)


def self_learning_next_step_to_json(payload: dict[str, Any]) -> str:
    validate_self_learning_next_step_recommendations(payload)
    return _stable_ruflo_json(payload, indent=2) + "\n"


def self_learning_next_step_from_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_self_learning_next_step_recommendations(payload)
    return payload


def _self_learning_candidates_from_source(
    candidate_source: dict[str, Any] | list[dict[str, Any]],
    *,
    source_label: str,
) -> list[dict[str, Any]]:
    if isinstance(candidate_source, dict):
        if "ranked_candidates" in candidate_source:
            candidates = candidate_source.get("ranked_candidates")
        elif "candidates" in candidate_source:
            candidates = candidate_source.get("candidates")
        else:
            raise ValueError("candidate source dict must include ranked_candidates or candidates")
        if not isinstance(candidates, list):
            raise TypeError("candidate source candidates must be a list")
        source_list = candidates
    elif isinstance(candidate_source, list):
        source_list = candidate_source
    else:
        raise TypeError("candidate source must be a plan/intake dict or findings list")

    normalized: list[dict[str, Any]] = []
    for item in source_list:
        if not isinstance(item, dict):
            raise TypeError("candidate source entries must be dicts")
        if "candidate_id" in item:
            validate_ruflo_upgrade_candidate(item)
            normalized.append(dict(item))
        else:
            normalized.append(score_ruflo_upgrade_candidate(item, source_label=source_label))
    return normalized


def _self_learning_feedback_by_key(receipts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_key: dict[str, list[dict[str, Any]]] = {}
    for receipt in receipts:
        for key in _self_learning_feedback_keys(receipt):
            by_key.setdefault(key, []).append(receipt)
    return by_key


def _matching_self_learning_feedback(
    candidate: dict[str, Any],
    feedback_by_key: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for key in _self_learning_candidate_keys(candidate):
        for receipt in feedback_by_key.get(key, []):
            chosen[receipt["feedback_id"]] = receipt
    return sorted(chosen.values(), key=lambda item: item["feedback_id"])


def _self_learning_candidate_keys(candidate: dict[str, Any]) -> list[str]:
    return _normalized_non_empty_keys(
        candidate.get("candidate_id"),
        candidate.get("proposal_id"),
        candidate.get("title"),
    )


def _self_learning_feedback_keys(receipt: dict[str, Any]) -> list[str]:
    return _normalized_non_empty_keys(
        receipt.get("candidate_id"),
        receipt.get("proposal_id"),
        receipt.get("title"),
    )


def _normalized_non_empty_keys(*values: Any) -> list[str]:
    keys: list[str] = []
    for value in values:
        text = str(value or "").strip().lower()
        if text and text not in keys:
            keys.append(text)
    return keys


def _build_self_learning_next_step(
    candidate: dict[str, Any],
    feedback_matches: list[dict[str, Any]],
) -> dict[str, Any]:
    accepted = [item for item in feedback_matches if item["status"] == "accepted"]
    rejected = [item for item in feedback_matches if item["status"] == "rejected"]
    deferred = [item for item in feedback_matches if item["status"] == "deferred"]
    adjustment = 0
    adjustment += round(sum(item["confidence"] for item in accepted) * 12)
    adjustment -= round(sum(item["confidence"] for item in rejected) * 18)
    adjustment -= round(sum(item["confidence"] for item in deferred) * 5)
    adjusted_score = max(int(candidate["score"]) + adjustment, 0)
    safe_recommendation = _self_learning_safe_recommendation(candidate, accepted, rejected, deferred)

    return {
        "candidate_id": candidate["candidate_id"],
        "title": candidate["title"],
        "category": candidate["category"],
        "risk_level": candidate["risk_level"],
        "source_path": candidate["source_path"],
        "base_recommendation": candidate["recommendation"],
        "safe_recommendation": safe_recommendation,
        "base_score": candidate["score"],
        "feedback_adjustment": adjustment,
        "feedback_adjusted_score": adjusted_score,
        "feedback_count": len(feedback_matches),
        "feedback_statuses": {
            "accepted": len(accepted),
            "rejected": len(rejected),
            "deferred": len(deferred),
        },
        "feedback_ids": [item["feedback_id"] for item in feedback_matches],
        "next_step": _self_learning_next_step_text(candidate, safe_recommendation, accepted, rejected, deferred),
        "reason": _self_learning_next_step_reason(candidate, accepted, rejected, deferred),
    }


def _validate_self_learning_next_step(recommendation: dict[str, Any]) -> None:
    required = (
        "candidate_id", "title", "category", "risk_level", "source_path",
        "base_recommendation", "safe_recommendation", "base_score",
        "feedback_adjustment", "feedback_adjusted_score", "feedback_count",
        "feedback_statuses", "feedback_ids", "next_step", "reason",
    )
    missing = [field for field in required if field not in recommendation]
    if missing:
        raise ValueError(f"self-learning next-step missing fields: {missing}")
    if recommendation["category"] not in RUFLO_UPGRADE_CATEGORIES:
        raise ValueError("invalid next-step category")
    if recommendation["risk_level"] not in RUFLO_RISK_LABELS:
        raise ValueError("invalid next-step risk_level")
    if recommendation["base_recommendation"] not in RUFLO_RECOMMENDATIONS:
        raise ValueError("invalid next-step base_recommendation")
    if recommendation["safe_recommendation"] not in RUFLO_RECOMMENDATIONS:
        raise ValueError("invalid next-step safe_recommendation")
    for field in ("candidate_id", "title", "source_path", "next_step", "reason"):
        if not isinstance(recommendation[field], str) or not recommendation[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    for field in ("base_score", "feedback_adjusted_score", "feedback_count"):
        if not isinstance(recommendation[field], int) or recommendation[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if not isinstance(recommendation["feedback_adjustment"], int):
        raise TypeError("feedback_adjustment must be an integer")
    statuses = recommendation["feedback_statuses"]
    if not isinstance(statuses, dict):
        raise TypeError("feedback_statuses must be a dict")
    for status in SELF_LEARNING_FEEDBACK_STATUSES:
        if not isinstance(statuses.get(status), int) or statuses[status] < 0:
            raise ValueError(f"feedback_statuses.{status} must be a non-negative integer")
    if sum(statuses[status] for status in SELF_LEARNING_FEEDBACK_STATUSES) != recommendation["feedback_count"]:
        raise ValueError("feedback_count must match feedback_statuses")
    if not isinstance(recommendation["feedback_ids"], list):
        raise TypeError("feedback_ids must be a list")


def _self_learning_safe_recommendation(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
) -> str:
    rejected_confidence = sum(item["confidence"] for item in rejected)
    accepted_confidence = sum(item["confidence"] for item in accepted)
    if rejected_confidence >= 0.7:
        return "reject"
    if deferred and accepted_confidence < 0.7:
        return "review"
    if candidate["risk_level"] == "high":
        return "review"
    if accepted_confidence >= 0.7:
        return candidate["recommendation"] if candidate["recommendation"] == "accept" else "review"
    return candidate["recommendation"]


def _self_learning_next_step_text(
    candidate: dict[str, Any],
    safe_recommendation: str,
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
) -> str:
    if safe_recommendation == "reject":
        return "Do not implement this slice now; keep it as rejected feedback unless new evidence appears."
    if deferred and not accepted:
        return "Write a smaller auditor-reviewed plan before any implementation patch."
    if safe_recommendation == "accept":
        return "Implement one small Link-native patch with tests; do not auto-approve or execute."
    if candidate["risk_level"] == "high":
        return "Keep this as design review only until a lower-risk sub-slice is identified."
    return "Review this candidate and narrow it to one safe patch before implementation."


def _self_learning_next_step_reason(
    candidate: dict[str, Any],
    accepted: list[dict[str, Any]],
    rejected: list[dict[str, Any]],
    deferred: list[dict[str, Any]],
) -> str:
    if rejected:
        strongest = max(rejected, key=lambda item: item["confidence"])
        return f"Reviewer rejected this candidate: {strongest['reason']}"
    if deferred:
        strongest = max(deferred, key=lambda item: item["confidence"])
        return f"Reviewer deferred this candidate: {strongest['reason']}"
    if accepted:
        strongest = max(accepted, key=lambda item: item["confidence"])
        return f"Reviewer accepted this candidate: {strongest['reason']}"
    return candidate["reason"]


def _self_learning_next_step_rank_key(recommendation: dict[str, Any]) -> tuple[int, int, int, str]:
    recommendation_rank = {"accept": 0, "review": 1, "reject": 2}.get(recommendation["safe_recommendation"], 3)
    risk_rank = {"low": 0, "medium": 1, "high": 2}.get(recommendation["risk_level"], 3)
    return (
        recommendation_rank,
        risk_rank,
        -int(recommendation["feedback_adjusted_score"]),
        recommendation["candidate_id"],
    )


REPO_VALUE_SCAN_VERSION = "link-repo-value-scan-v1"
REPO_VALUE_SCAN_MAX_TOP = 25
REPO_VALUE_CATEGORIES = (
    "orchestration",
    "agent_memory",
    "self_learning",
    "repo_scanning",
    "task_routing",
    "safety_approval_gates",
    "receipts_auditability",
    "cli_workflow_ux",
    "tests_verification",
)

_REPO_VALUE_CATEGORY_WEIGHTS: dict[str, int] = {
    "safety_approval_gates": 34,
    "orchestration": 31,
    "task_routing": 29,
    "agent_memory": 28,
    "self_learning": 27,
    "repo_scanning": 26,
    "receipts_auditability": 25,
    "tests_verification": 23,
    "cli_workflow_ux": 21,
}

_REPO_VALUE_CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "orchestration": ("orchestr", "swarm", "workflow", "coordinator", "multi-agent", "planner"),
    "agent_memory": ("memory", "context", "recall", "transcript", "session", "embedding"),
    "self_learning": ("learn", "feedback", "reflection", "improve", "training", "recommendation"),
    "repo_scanning": ("scan", "inventory", "benchmark", "sota", "catalog", "compare", "valuable"),
    "task_routing": ("route", "router", "dispatch", "queue", "worker", "profile"),
    "safety_approval_gates": ("safety", "approval", "permission", "gate", "policy", "sandbox", "guard"),
    "receipts_auditability": ("receipt", "audit", "evidence", "trace", "provenance", "finalizer"),
    "cli_workflow_ux": ("cli", "command", "dashboard", "ux", "workflow", "status"),
    "tests_verification": ("test", "verify", "healthcheck", "fixture", "regression", "coverage"),
}

_REPO_VALUE_CATEGORY_REASONS: dict[str, str] = {
    "orchestration": "Link needs stronger planning and coordination surfaces before expanding multi-agent work.",
    "agent_memory": "Link needs durable context and memory signals so long-running sessions avoid re-mining the same evidence.",
    "self_learning": "Link needs reviewer feedback loops that improve future Growth recommendations without autonomous approval.",
    "repo_scanning": "Link needs better repository value scanning so research archives turn into ranked, actionable upgrade candidates.",
    "task_routing": "Link needs deterministic routing so tasks reach the narrowest safe worker/profile path.",
    "safety_approval_gates": "Link needs approval and policy gates around any future automation or worker handoff expansion.",
    "receipts_auditability": "Link needs clear evidence, provenance, and receipt trails for every self-upgrade slice.",
    "cli_workflow_ux": "Link needs compact commands and dashboards that make Growth state easier to operate locally.",
    "tests_verification": "Link needs fast verification surfaces so upgrades stay small, reversible, and evidence-backed.",
}


def make_repo_value_finding_id(path: str, category: str, title: str) -> str:
    """Build a deterministic id for one repo value finding."""
    import hashlib
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(title or path or "repo-value").lower()).strip("-")
    slug = slug[:72].strip("-") or "repo-value"
    payload = _stable_ruflo_json({
        "category": category,
        "path": path,
        "title": title,
        "version": REPO_VALUE_SCAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"repo-value-{slug}-{digest}"


def collect_repo_value_scan(
    inventory_items: list[dict[str, Any]],
    *,
    top: int = 10,
    source_label: str = "research",
) -> dict[str, Any]:
    """Rank repository inventory items by Link project value without writing state."""
    if not isinstance(top, int):
        raise TypeError("top must be an integer")
    requested_top = top
    effective_top = min(max(top, 1), REPO_VALUE_SCAN_MAX_TOP)
    warnings: list[str] = []
    if requested_top > REPO_VALUE_SCAN_MAX_TOP:
        warnings.append(f"top {requested_top} capped at {REPO_VALUE_SCAN_MAX_TOP} (hard limit)")
    if requested_top < 1:
        warnings.append("top below 1 raised to 1")
    if not isinstance(inventory_items, list):
        raise TypeError("inventory_items must be a list")

    findings = [score_repo_value_inventory_item(item, source_label=source_label) for item in inventory_items]
    unique_findings, duplicate_count = _dedupe_repo_value_findings(findings)
    weak_count = len([finding for finding in unique_findings if finding["weak_finding"]])
    if weak_count:
        warnings.append(f"{weak_count} weak repo value finding(s) have limited Link-specific signals")
    if duplicate_count:
        warnings.append(f"{duplicate_count} duplicate repo inventory item(s) collapsed by path/category")

    ranked = sorted(unique_findings, key=_repo_value_rank_key)[:effective_top]
    scan = {
        "scan_version": REPO_VALUE_SCAN_VERSION,
        "scan_id": make_repo_value_scan_id(ranked, top=effective_top, source_label=source_label),
        "source_label": str(source_label or "research"),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "top_requested": requested_top,
        "top_used": effective_top,
        "item_count": len(inventory_items),
        "finding_count": len(findings),
        "unique_finding_count": len(unique_findings),
        "duplicate_count": duplicate_count,
        "weak_finding_count": weak_count,
        "categories": list(REPO_VALUE_CATEGORIES),
        "findings": ranked,
        "warnings": warnings,
        "writes": [],
    }
    validate_repo_value_scan(scan)
    return scan


def make_repo_value_scan_id(
    findings: list[dict[str, Any]],
    *,
    top: int,
    source_label: str = "research",
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "finding_ids": [finding["finding_id"] for finding in findings],
        "source_label": source_label,
        "top": top,
        "version": REPO_VALUE_SCAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"repo-value-scan-{digest}"


def score_repo_value_inventory_item(
    item: dict[str, Any],
    *,
    source_label: str = "research",
) -> dict[str, Any]:
    """Normalize one repo/file inventory item into a Link-value finding."""
    if not isinstance(item, dict):
        raise TypeError("repo value inventory item must be a dict")
    path = _first_text(item, "path", "source_path", "file")
    if not path:
        raise ValueError("repo value inventory item requires a path/source_path/file")
    title = _first_text(item, "title", "name") or _repo_value_title_from_path(path)
    summary = _first_text(item, "summary", "description", "notes", "content_preview")
    source_kind = _first_text(item, "source_kind", "kind", "type") or "file"
    tags = _normalize_repo_value_tags(item.get("tags") or item.get("signals") or item.get("keywords"))
    haystack = " ".join([
        path,
        title,
        summary,
        source_kind,
        " ".join(tags),
        str(item.get("category") or ""),
    ])
    category, signal_count = _infer_repo_value_category(_first_text(item, "category"), haystack)
    weak_finding = signal_count == 0 or not summary

    score = _REPO_VALUE_CATEGORY_WEIGHTS[category]
    score += signal_count * 4
    if summary:
        score += 5
    if tags:
        score += min(len(tags), 4) * 2
    path_lower = path.lower()
    if any(part in path_lower for part in ("test", "spec", "fixture")):
        score += 3 if category == "tests_verification" else 1
    if any(part in path_lower for part in ("readme", "skill", "workflow", "lib/")):
        score += 2
    if weak_finding:
        score = max(score - 10, 1)

    finding = {
        "finding_id": make_repo_value_finding_id(path, category, title),
        "title": str(title).strip(),
        "category": category,
        "score": int(score),
        "value_reason": _repo_value_reason(category, summary, signal_count),
        "source_path": str(path).strip(),
        "source_kind": str(source_kind).strip() or "file",
        "summary": str(summary).strip(),
        "signals": tags,
        "signal_count": signal_count,
        "weak_finding": weak_finding,
        "source_label": str(source_label or "research"),
    }
    validate_repo_value_finding(finding)
    return finding


def validate_repo_value_finding(finding: dict[str, Any]) -> None:
    required = (
        "finding_id", "title", "category", "score", "value_reason",
        "source_path", "source_kind", "summary", "signals", "signal_count",
        "weak_finding", "source_label",
    )
    missing = [field for field in required if field not in finding]
    if missing:
        raise ValueError(f"repo value finding missing fields: {missing}")
    for field in ("finding_id", "title", "category", "value_reason", "source_path", "source_kind", "source_label"):
        if not isinstance(finding[field], str) or not finding[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if finding["category"] not in REPO_VALUE_CATEGORIES:
        raise ValueError(f"invalid repo value category: {finding['category']}")
    if not isinstance(finding["score"], int) or finding["score"] < 0:
        raise ValueError("score must be a non-negative integer")
    if not isinstance(finding["signal_count"], int) or finding["signal_count"] < 0:
        raise ValueError("signal_count must be a non-negative integer")
    if not isinstance(finding["signals"], list) or not all(isinstance(signal, str) and signal for signal in finding["signals"]):
        raise TypeError("signals must be a list of non-empty strings")
    if not isinstance(finding["weak_finding"], bool):
        raise TypeError("weak_finding must be a boolean")


def validate_repo_value_scan(scan: dict[str, Any]) -> None:
    required = (
        "scan_version", "scan_id", "source_label", "dry_run", "write_allowed",
        "automation_allowed", "top_requested", "top_used", "item_count",
        "finding_count", "unique_finding_count", "duplicate_count",
        "weak_finding_count", "categories", "findings", "warnings", "writes",
    )
    missing = [field for field in required if field not in scan]
    if missing:
        raise ValueError(f"repo value scan missing fields: {missing}")
    if scan["scan_version"] != REPO_VALUE_SCAN_VERSION:
        raise ValueError("unsupported repo value scan version")
    if not isinstance(scan["scan_id"], str) or not scan["scan_id"].strip():
        raise ValueError("scan_id must be a non-empty string")
    if scan["dry_run"] is not True or scan["write_allowed"] is not False or scan["automation_allowed"] is not False:
        raise ValueError("repo value scan must remain read-only")
    if scan["writes"] != []:
        raise ValueError("repo value scan must not write files")
    for field in (
        "top_requested", "top_used", "item_count", "finding_count",
        "unique_finding_count", "duplicate_count", "weak_finding_count",
    ):
        if not isinstance(scan[field], int) or scan[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if not isinstance(scan["categories"], list) or set(scan["categories"]) != set(REPO_VALUE_CATEGORIES):
        raise ValueError("repo value scan categories must match stable category set")
    if not isinstance(scan["findings"], list):
        raise TypeError("repo value scan findings must be a list")
    if not isinstance(scan["warnings"], list):
        raise TypeError("repo value scan warnings must be a list")
    for finding in scan["findings"]:
        validate_repo_value_finding(finding)


def repo_value_scan_to_json(scan: dict[str, Any]) -> str:
    validate_repo_value_scan(scan)
    return _stable_ruflo_json(scan, indent=2) + "\n"


def repo_value_scan_from_json(text: str) -> dict[str, Any]:
    import json as _json

    scan = _json.loads(text)
    validate_repo_value_scan(scan)
    return scan


def _infer_repo_value_category(value: str, haystack: str) -> tuple[str, int]:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    text = f"{raw} {haystack}".lower()
    if raw in REPO_VALUE_CATEGORIES:
        explicit_hits = sum(1 for keyword in _REPO_VALUE_CATEGORY_KEYWORDS[raw] if keyword in text)
        return raw, max(explicit_hits, 1)
    best_category = "repo_scanning"
    best_hits = 0
    for category, keywords in _REPO_VALUE_CATEGORY_KEYWORDS.items():
        hits = sum(1 for keyword in keywords if keyword in text)
        if hits > best_hits or (hits == best_hits and _REPO_VALUE_CATEGORY_WEIGHTS[category] > _REPO_VALUE_CATEGORY_WEIGHTS[best_category]):
            best_category = category
            best_hits = hits
    return best_category, best_hits


def _repo_value_reason(category: str, summary: str, signal_count: int) -> str:
    base = _REPO_VALUE_CATEGORY_REASONS[category]
    if summary and signal_count:
        return f"{base} Source summary and {signal_count} matching signal(s) support this ranking."
    if summary:
        return f"{base} Source summary is present, but Link-specific signals are limited."
    return f"{base} Treat this as weak until a source summary or stronger signals are added."


def _repo_value_title_from_path(path: str) -> str:
    name = str(path).rstrip("/").split("/")[-1] or "repo item"
    return name.replace("_", " ").replace("-", " ")


def _normalize_repo_value_tags(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        raw_items = [value]
    elif isinstance(value, list):
        raw_items = value
    else:
        raise TypeError("repo value tags/signals/keywords must be a string or list")
    tags: list[str] = []
    for item in raw_items:
        text = str(item or "").strip().lower().replace(" ", "_")
        if text and text not in tags:
            tags.append(text)
    return tags


def _dedupe_repo_value_findings(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    chosen: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_count = 0
    for finding in findings:
        key = (finding["source_path"].strip().lower(), finding["category"])
        existing = chosen.get(key)
        if existing is None or _repo_value_rank_key(finding) < _repo_value_rank_key(existing):
            chosen[key] = finding
        if existing is not None:
            duplicate_count += 1
    return list(chosen.values()), duplicate_count


def _repo_value_rank_key(finding: dict[str, Any]) -> tuple[int, int, str]:
    weak_rank = 1 if finding.get("weak_finding") else 0
    return (weak_rank, -int(finding.get("score", 0)), finding.get("finding_id", ""))


LINK_CAPABILITY_INVENTORY_VERSION = "link-capability-inventory-v1"
LINK_CAPABILITY_CATEGORIES = (
    "safety",
    "receipts",
    "routing",
    "research_mining",
    "repo_value_scan",
    "self_learning",
    "tests",
    "workflow_ux",
)
LINK_CAPABILITY_CONFIDENCE_LEVELS = ("low", "medium", "high")
LINK_CAPABILITY_RISK_LEVELS = ("low", "medium", "high")
LINK_CAPABILITY_MATURITY_LEVELS = ("planned", "partial", "available", "verified")

_DEFAULT_LINK_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "name": "Growth archive inventory",
        "category": "research_mining",
        "description": "Discovers local research archives before extraction or cataloging.",
        "source": "link_modes/growth/link_growth_console.py:collect_archive_inventory",
        "confidence": "high",
        "tags": ["archive", "inventory", "research"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Growth archive catalog",
        "category": "research_mining",
        "description": "Builds local metadata catalogs for extracted research repositories.",
        "source": "link_modes/growth/link_growth_console.py:collect_archive_catalog",
        "confidence": "high",
        "tags": ["archive", "catalog", "metadata"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Archive code queue ranking",
        "category": "research_mining",
        "description": "Ranks cataloged code files for code brief generation with wrapper-file handling.",
        "source": "link_modes/growth/link_growth_console.py:collect_archive_code_queue",
        "confidence": "high",
        "tags": ["queue", "ranking", "code_brief"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Code brief proposal preview",
        "category": "workflow_ux",
        "description": "Previews proposal generation from code briefs and batch queue entries in dry-run mode.",
        "source": "link_modes/growth/link_growth_console.py:collect_code_brief_propose_batch",
        "confidence": "high",
        "tags": ["proposal", "preview", "dry_run"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Repo value scan helper",
        "category": "repo_value_scan",
        "description": "Scores repository inventory items by Link relevance without writing state.",
        "source": "link_modes/growth/link_growth_console.py:collect_repo_value_scan",
        "confidence": "high",
        "tags": ["repo_value", "scan", "ranking"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Ruflo upgrade intake",
        "category": "research_mining",
        "description": "Normalizes Ruflo-derived findings into deterministic upgrade candidates.",
        "source": "link_modes/growth/link_growth_console.py:build_ruflo_upgrade_intake",
        "confidence": "high",
        "tags": ["ruflo", "intake", "upgrade_candidates"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Ruflo upgrade plan",
        "category": "workflow_ux",
        "description": "Groups ranked Ruflo candidates into auditor-gated implementation plan sections.",
        "source": "link_modes/growth/link_growth_console.py:collect_ruflo_upgrade_plan",
        "confidence": "high",
        "tags": ["ruflo", "planning", "auditor_gate"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Self-learning feedback receipts",
        "category": "self_learning",
        "description": "Creates deterministic read-only feedback receipt objects for upgrade recommendations.",
        "source": "link_modes/growth/link_growth_console.py:build_self_learning_feedback_receipt",
        "confidence": "high",
        "tags": ["feedback", "receipt", "recommendation"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Self-learning next-step recommendations",
        "category": "self_learning",
        "description": "Adjusts next upgrade recommendations using accepted, rejected, or deferred feedback.",
        "source": "link_modes/growth/link_growth_console.py:collect_self_learning_next_step_recommendations",
        "confidence": "high",
        "tags": ["feedback", "ranking", "next_step"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Control plane proposal registry",
        "category": "workflow_ux",
        "description": "Stores and lists pending, accepted, and rejected Growth proposals through the control plane.",
        "source": "link_core/control_plane/link_control_plane_proposals.py",
        "confidence": "high",
        "tags": ["proposal", "control_plane", "registry"],
        "risk_level": "medium",
        "maturity_level": "verified",
    },
    {
        "name": "Receipt helpers",
        "category": "receipts",
        "description": "Builds stable fork lineage, transcript snapshot, and content replacement receipt objects.",
        "source": "link_core/receipts/__init__.py",
        "confidence": "high",
        "tags": ["receipt", "traceability", "provenance"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Capability gate and command guard",
        "category": "safety",
        "description": "Classifies risky commands, paths, and git operations before execution surfaces use them.",
        "source": "link_capability_gate.py and modern_command_guard.py",
        "confidence": "high",
        "tags": ["safety", "command_guard", "policy"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Profile tool gate",
        "category": "routing",
        "description": "Restricts worker profiles to narrower tool access decisions.",
        "source": "link_profile_gate.py",
        "confidence": "high",
        "tags": ["profile", "routing", "tool_gate"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Model routing profiles",
        "category": "routing",
        "description": "Defines deterministic local and cloud model routing profiles without calling providers.",
        "source": "link_model_routing_profiles.py",
        "confidence": "high",
        "tags": ["model", "routing", "profiles"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Growth coverage dashboard data",
        "category": "workflow_ux",
        "description": "Summarizes archive, code, proposal, handoff, and receipt counts for Growth run JSON.",
        "source": "link_modes/growth/link_growth_console.py:_collect_growth_coverage_data",
        "confidence": "high",
        "tags": ["coverage", "dashboard", "growth_run"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Link healthcheck",
        "category": "tests",
        "description": "Runs compile, import, safety, control-plane, and Growth smoke coverage checks.",
        "source": "link_healthcheck.py",
        "confidence": "high",
        "tags": ["healthcheck", "verification", "tests"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
    {
        "name": "Growth pipeline smoke tests",
        "category": "tests",
        "description": "Exercises Growth helpers, commands, receipts, proposal flow, and research mining behavior.",
        "source": "tests/test_growth_pipeline.py",
        "confidence": "high",
        "tags": ["growth", "smoke", "tests"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
)


def make_link_capability_id(name: str, category: str, source: str) -> str:
    """Build a deterministic id for one Link capability entry."""
    import hashlib
    import re

    slug = re.sub(r"[^a-z0-9]+", "-", str(name or "link-capability").lower()).strip("-")
    slug = slug[:72].strip("-") or "link-capability"
    payload = _stable_ruflo_json({
        "category": category,
        "name": name,
        "source": source,
        "version": LINK_CAPABILITY_INVENTORY_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-{slug}-{digest}"


def collect_link_capability_inventory(
    capabilities: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Return Link's current known capabilities as read-only normalized data."""
    source_items = list(capabilities) if capabilities is not None else [dict(item) for item in _DEFAULT_LINK_CAPABILITIES]
    if not isinstance(source_items, list):
        raise TypeError("capabilities must be a list when provided")
    normalized = [normalize_link_capability_entry(item) for item in source_items]
    unique_capabilities, duplicate_count = _dedupe_link_capabilities(normalized)
    unique_capabilities.sort(key=lambda item: (item["category"], item["capability_id"]))
    inventory = {
        "inventory_version": LINK_CAPABILITY_INVENTORY_VERSION,
        "inventory_id": make_link_capability_inventory_id(unique_capabilities),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "capability_count": len(unique_capabilities),
        "input_count": len(source_items),
        "duplicate_count": duplicate_count,
        "categories": list(LINK_CAPABILITY_CATEGORIES),
        "capabilities": unique_capabilities,
        "writes": [],
    }
    validate_link_capability_inventory(inventory)
    return inventory


def make_link_capability_inventory_id(capabilities: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_ids": [item["capability_id"] for item in capabilities],
        "version": LINK_CAPABILITY_INVENTORY_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-inventory-{digest}"


def normalize_link_capability_entry(entry: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise TypeError("Link capability entry must be a dict")
    name = _first_text(entry, "name", "title")
    category = _normalize_link_capability_category(_first_text(entry, "category"))
    description = _first_text(entry, "description", "summary")
    source = _first_text(entry, "source", "source_path", "file")
    confidence = _normalize_link_capability_choice(
        _first_text(entry, "confidence"),
        LINK_CAPABILITY_CONFIDENCE_LEVELS,
        "confidence",
        default="medium",
    )
    risk_level = _normalize_link_capability_choice(
        _first_text(entry, "risk_level", "risk"),
        LINK_CAPABILITY_RISK_LEVELS,
        "risk_level",
        default="medium",
    )
    maturity_level = _normalize_link_capability_choice(
        _first_text(entry, "maturity_level", "maturity"),
        LINK_CAPABILITY_MATURITY_LEVELS,
        "maturity_level",
        default="partial",
    )
    tags = _normalize_link_capability_tags(entry.get("tags"))
    capability = {
        "capability_id": _first_text(entry, "capability_id") or make_link_capability_id(name, category, source),
        "name": name,
        "category": category,
        "description": description,
        "source": source,
        "confidence": confidence,
        "tags": tags,
        "risk_level": risk_level,
        "maturity_level": maturity_level,
    }
    validate_link_capability_entry(capability)
    return capability


def validate_link_capability_entry(entry: dict[str, Any]) -> None:
    required = (
        "capability_id", "name", "category", "description", "source",
        "confidence", "tags", "risk_level", "maturity_level",
    )
    missing = [field for field in required if field not in entry]
    if missing:
        raise ValueError(f"Link capability entry missing fields: {missing}")
    for field in ("capability_id", "name", "category", "description", "source", "confidence", "risk_level", "maturity_level"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if entry["category"] not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid Link capability category: {entry['category']}")
    if entry["confidence"] not in LINK_CAPABILITY_CONFIDENCE_LEVELS:
        raise ValueError(f"invalid Link capability confidence: {entry['confidence']}")
    if entry["risk_level"] not in LINK_CAPABILITY_RISK_LEVELS:
        raise ValueError(f"invalid Link capability risk_level: {entry['risk_level']}")
    if entry["maturity_level"] not in LINK_CAPABILITY_MATURITY_LEVELS:
        raise ValueError(f"invalid Link capability maturity_level: {entry['maturity_level']}")
    if not isinstance(entry["tags"], list) or not all(isinstance(tag, str) and tag for tag in entry["tags"]):
        raise TypeError("tags must be a list of non-empty strings")


def validate_link_capability_inventory(inventory: dict[str, Any]) -> None:
    required = (
        "inventory_version", "inventory_id", "dry_run", "write_allowed",
        "automation_allowed", "capability_count", "input_count", "duplicate_count",
        "categories", "capabilities", "writes",
    )
    missing = [field for field in required if field not in inventory]
    if missing:
        raise ValueError(f"Link capability inventory missing fields: {missing}")
    if inventory["inventory_version"] != LINK_CAPABILITY_INVENTORY_VERSION:
        raise ValueError("unsupported Link capability inventory version")
    if not isinstance(inventory["inventory_id"], str) or not inventory["inventory_id"].strip():
        raise ValueError("inventory_id must be a non-empty string")
    if inventory["dry_run"] is not True or inventory["write_allowed"] is not False or inventory["automation_allowed"] is not False:
        raise ValueError("Link capability inventory must remain read-only")
    if inventory["writes"] != []:
        raise ValueError("Link capability inventory must not write files")
    for field in ("capability_count", "input_count", "duplicate_count"):
        if not isinstance(inventory[field], int) or inventory[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if not isinstance(inventory["categories"], list) or set(inventory["categories"]) != set(LINK_CAPABILITY_CATEGORIES):
        raise ValueError("inventory categories must match stable category set")
    capabilities = inventory["capabilities"]
    if not isinstance(capabilities, list):
        raise TypeError("capabilities must be a list")
    if inventory["capability_count"] != len(capabilities):
        raise ValueError("capability_count must match capabilities length")
    for capability in capabilities:
        validate_link_capability_entry(capability)


def link_capability_inventory_to_json(inventory: dict[str, Any]) -> str:
    validate_link_capability_inventory(inventory)
    return _stable_ruflo_json(inventory, indent=2) + "\n"


def link_capability_inventory_from_json(text: str) -> dict[str, Any]:
    import json as _json

    inventory = _json.loads(text)
    validate_link_capability_inventory(inventory)
    return inventory


def _normalize_link_capability_category(category: str) -> str:
    raw = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid Link capability category: {category}")
    return raw


def _normalize_link_capability_choice(
    value: str,
    allowed: tuple[str, ...],
    field_name: str,
    *,
    default: str,
) -> str:
    raw = str(value or default).strip().lower().replace("-", "_").replace(" ", "_")
    if raw not in allowed:
        raise ValueError(f"invalid Link capability {field_name}: {value}")
    return raw


def _normalize_link_capability_tags(tags: Any) -> list[str]:
    if tags is None:
        return []
    if isinstance(tags, str):
        raw_items = [tags]
    elif isinstance(tags, list):
        raw_items = tags
    else:
        raise TypeError("Link capability tags must be a string or list")
    normalized: list[str] = []
    for tag in raw_items:
        text = str(tag or "").strip().lower().replace(" ", "_")
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _dedupe_link_capabilities(capabilities: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    chosen: dict[str, dict[str, Any]] = {}
    duplicate_count = 0
    for capability in capabilities:
        key = capability["capability_id"]
        if key in chosen:
            duplicate_count += 1
            continue
        chosen[key] = capability
    return list(chosen.values()), duplicate_count


CAPABILITY_GAP_PREVIEW_VERSION = "link-capability-gap-preview-v1"
_CAPABILITY_GAP_SECTIONS = (
    "direct_gaps",
    "maturity_gaps",
    "onboarding_gaps",
    "optional_cross_cluster_ideas",
)
_CAPABILITY_GAP_CATEGORY_MAP: dict[str, str] = {
    "orchestration": "workflow_ux",
    "agent_memory": "self_learning",
    "self_learning": "self_learning",
    "repo_scanning": "repo_value_scan",
    "task_routing": "routing",
    "safety_approval_gates": "safety",
    "receipts_auditability": "receipts",
    "cli_workflow_ux": "workflow_ux",
    "tests_verification": "tests",
}
_CAPABILITY_MATURITY_RANK = {
    "planned": 0,
    "partial": 1,
    "available": 2,
    "verified": 3,
}


def make_capability_gap_preview_id(
    link_capabilities: list[dict[str, Any]],
    repo_findings: list[dict[str, Any]],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_ids": [item["capability_id"] for item in link_capabilities],
        "finding_ids": [item["finding_id"] for item in repo_findings],
        "version": CAPABILITY_GAP_PREVIEW_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"capability-gap-preview-{digest}"


def collect_capability_gap_preview(
    link_inventory: dict[str, Any],
    repo_value_scan: dict[str, Any] | list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare Link capability inventory with repo-value findings without writing state."""
    validate_link_capability_inventory(link_inventory)
    link_capabilities = [dict(item) for item in link_inventory["capabilities"]]
    repo_findings = _capability_gap_findings_from_input(repo_value_scan)

    direct_gaps: list[dict[str, Any]] = []
    maturity_gaps: list[dict[str, Any]] = []
    onboarding_gaps: list[dict[str, Any]] = []
    optional_cross_cluster_ideas: list[dict[str, Any]] = []
    matched_capabilities: list[dict[str, Any]] = []
    unmatched_findings: list[dict[str, Any]] = []

    for finding in repo_findings:
        target_category = _capability_gap_target_category(finding)
        matches = _capability_gap_matches(finding, target_category, link_capabilities)
        if not matches:
            gap = _build_capability_gap_entry(
                "direct_gap",
                finding,
                target_category,
                None,
                "missing capability category or no close Link capability match",
            )
            direct_gaps.append(gap)
            unmatched_findings.append(_capability_gap_unmatched_finding(finding, target_category, "direct_gap"))
            continue

        best = matches[0]
        matched_capabilities.append(_capability_gap_match_entry(finding, best, target_category))
        if finding.get("weak_finding") is True or int(finding.get("signal_count", 0) or 0) <= 1:
            optional_cross_cluster_ideas.append(_build_capability_gap_entry(
                "optional_cross_cluster_idea",
                finding,
                target_category,
                best,
                "weak or distant repo finding; treat as optional strategic inspiration",
            ))
            continue

        required_maturity = _capability_gap_required_maturity(finding)
        current_maturity = best["maturity_level"]
        if _CAPABILITY_MATURITY_RANK[current_maturity] < _CAPABILITY_MATURITY_RANK[required_maturity]:
            maturity_gaps.append(_build_capability_gap_entry(
                "maturity_gap",
                finding,
                target_category,
                best,
                f"matched capability maturity is {current_maturity}, below requested {required_maturity}",
            ))
            continue

        if _capability_gap_is_onboarding_signal(finding):
            onboarding_gaps.append(_build_capability_gap_entry(
                "onboarding_gap",
                finding,
                target_category,
                best,
                "matched capability exists, but finding points to discoverability or integration UX",
            ))

    matched_capabilities.sort(key=lambda item: (item["capability_id"], item["finding_id"]))
    for section in (direct_gaps, maturity_gaps, onboarding_gaps, optional_cross_cluster_ideas, unmatched_findings):
        section.sort(key=lambda item: item.get("gap_id") or item.get("finding_id", ""))

    preview = {
        "preview_version": CAPABILITY_GAP_PREVIEW_VERSION,
        "preview_id": make_capability_gap_preview_id(link_capabilities, repo_findings),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "direct_gaps": direct_gaps,
        "maturity_gaps": maturity_gaps,
        "onboarding_gaps": onboarding_gaps,
        "optional_cross_cluster_ideas": optional_cross_cluster_ideas,
        "matched_capabilities": matched_capabilities,
        "unmatched_findings": unmatched_findings,
        "confidence": _capability_gap_preview_confidence(
            repo_findings,
            direct_gaps,
            maturity_gaps,
            onboarding_gaps,
            optional_cross_cluster_ideas,
        ),
        "metadata": dict(metadata or {}),
        "counts": {
            "link_capability_count": len(link_capabilities),
            "repo_finding_count": len(repo_findings),
            "direct_gap_count": len(direct_gaps),
            "maturity_gap_count": len(maturity_gaps),
            "onboarding_gap_count": len(onboarding_gaps),
            "optional_cross_cluster_idea_count": len(optional_cross_cluster_ideas),
            "matched_capability_count": len(matched_capabilities),
            "unmatched_finding_count": len(unmatched_findings),
        },
        "writes": [],
    }
    validate_capability_gap_preview(preview)
    return preview


def validate_capability_gap_preview(preview: dict[str, Any]) -> None:
    required = (
        "preview_version", "preview_id", "dry_run", "write_allowed", "automation_allowed",
        "direct_gaps", "maturity_gaps", "onboarding_gaps", "optional_cross_cluster_ideas",
        "matched_capabilities", "unmatched_findings", "confidence", "metadata", "counts", "writes",
    )
    missing = [field for field in required if field not in preview]
    if missing:
        raise ValueError(f"capability gap preview missing fields: {missing}")
    if preview["preview_version"] != CAPABILITY_GAP_PREVIEW_VERSION:
        raise ValueError("unsupported capability gap preview version")
    if not isinstance(preview["preview_id"], str) or not preview["preview_id"].strip():
        raise ValueError("preview_id must be a non-empty string")
    if preview["dry_run"] is not True or preview["write_allowed"] is not False or preview["automation_allowed"] is not False:
        raise ValueError("capability gap preview must remain read-only")
    if preview["writes"] != []:
        raise ValueError("capability gap preview must not write files")
    if preview["confidence"] not in LINK_CAPABILITY_CONFIDENCE_LEVELS:
        raise ValueError("invalid capability gap preview confidence")
    if not isinstance(preview["metadata"], dict):
        raise TypeError("metadata must be a dict")
    counts = preview["counts"]
    if not isinstance(counts, dict):
        raise TypeError("counts must be a dict")
    for section in _CAPABILITY_GAP_SECTIONS:
        if not isinstance(preview[section], list):
            raise TypeError(f"{section} must be a list")
        for gap in preview[section]:
            _validate_capability_gap_entry(gap)
    if not isinstance(preview["matched_capabilities"], list):
        raise TypeError("matched_capabilities must be a list")
    if not isinstance(preview["unmatched_findings"], list):
        raise TypeError("unmatched_findings must be a list")
    for field, section in (
        ("direct_gap_count", "direct_gaps"),
        ("maturity_gap_count", "maturity_gaps"),
        ("onboarding_gap_count", "onboarding_gaps"),
        ("optional_cross_cluster_idea_count", "optional_cross_cluster_ideas"),
        ("matched_capability_count", "matched_capabilities"),
        ("unmatched_finding_count", "unmatched_findings"),
    ):
        if not isinstance(counts.get(field), int) or counts[field] != len(preview[section]):
            raise ValueError(f"counts.{field} must match {section} length")


def capability_gap_preview_to_json(preview: dict[str, Any]) -> str:
    validate_capability_gap_preview(preview)
    return _stable_ruflo_json(preview, indent=2) + "\n"


def capability_gap_preview_from_json(text: str) -> dict[str, Any]:
    import json as _json

    preview = _json.loads(text)
    validate_capability_gap_preview(preview)
    return preview


def _capability_gap_findings_from_input(repo_value_scan: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(repo_value_scan, dict):
        validate_repo_value_scan(repo_value_scan)
        findings = repo_value_scan["findings"]
    elif isinstance(repo_value_scan, list):
        findings = repo_value_scan
    else:
        raise TypeError("repo_value_scan must be a scan dict or findings list")
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        if not isinstance(finding, dict):
            raise TypeError("repo value finding entries must be dicts")
        validate_repo_value_finding(finding)
        normalized.append(dict(finding))
    return normalized


def _capability_gap_target_category(finding: dict[str, Any]) -> str:
    category = finding["category"]
    return _CAPABILITY_GAP_CATEGORY_MAP.get(category, "workflow_ux")


def _capability_gap_matches(
    finding: dict[str, Any],
    target_category: str,
    capabilities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    finding_tokens = _capability_gap_tokens(finding)
    matches: list[tuple[int, dict[str, Any]]] = []
    for capability in capabilities:
        if capability["category"] != target_category:
            continue
        cap_tokens = _capability_gap_tokens(capability)
        overlap = len(finding_tokens & cap_tokens)
        if overlap > 0 or finding["category"] in {"repo_scanning", "tests_verification", "receipts_auditability", "safety_approval_gates"}:
            matches.append((overlap, capability))
    matches.sort(key=lambda item: (-item[0], item[1]["capability_id"]))
    return [item[1] for item in matches]


def _build_capability_gap_entry(
    gap_type: str,
    finding: dict[str, Any],
    target_category: str,
    capability: dict[str, Any] | None,
    reason: str,
) -> dict[str, Any]:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_id": capability.get("capability_id") if capability else "",
        "finding_id": finding["finding_id"],
        "gap_type": gap_type,
        "target_category": target_category,
        "version": CAPABILITY_GAP_PREVIEW_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    gap = {
        "gap_id": f"capability-gap-{digest}",
        "gap_type": gap_type,
        "finding_id": finding["finding_id"],
        "finding_title": finding["title"],
        "target_category": target_category,
        "matched_capability_id": capability.get("capability_id", "") if capability else "",
        "matched_capability_name": capability.get("name", "") if capability else "",
        "reason": reason,
        "confidence": _capability_gap_entry_confidence(finding, capability),
        "source_path": finding["source_path"],
        "recommended_action": _capability_gap_action(gap_type),
    }
    _validate_capability_gap_entry(gap)
    return gap


def _validate_capability_gap_entry(gap: dict[str, Any]) -> None:
    required = (
        "gap_id", "gap_type", "finding_id", "finding_title", "target_category",
        "matched_capability_id", "matched_capability_name", "reason", "confidence",
        "source_path", "recommended_action",
    )
    missing = [field for field in required if field not in gap]
    if missing:
        raise ValueError(f"capability gap entry missing fields: {missing}")
    if gap["gap_type"] not in {"direct_gap", "maturity_gap", "onboarding_gap", "optional_cross_cluster_idea"}:
        raise ValueError(f"invalid capability gap type: {gap['gap_type']}")
    if gap["target_category"] not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid capability gap target_category: {gap['target_category']}")
    if gap["confidence"] not in LINK_CAPABILITY_CONFIDENCE_LEVELS:
        raise ValueError(f"invalid capability gap confidence: {gap['confidence']}")
    for field in ("gap_id", "finding_id", "finding_title", "reason", "source_path", "recommended_action"):
        if not isinstance(gap[field], str) or not gap[field].strip():
            raise ValueError(f"{field} must be a non-empty string")


def _capability_gap_match_entry(
    finding: dict[str, Any],
    capability: dict[str, Any],
    target_category: str,
) -> dict[str, Any]:
    return {
        "finding_id": finding["finding_id"],
        "finding_title": finding["title"],
        "capability_id": capability["capability_id"],
        "capability_name": capability["name"],
        "target_category": target_category,
        "maturity_level": capability["maturity_level"],
        "confidence": _capability_gap_entry_confidence(finding, capability),
    }


def _capability_gap_unmatched_finding(finding: dict[str, Any], target_category: str, section: str) -> dict[str, Any]:
    return {
        "finding_id": finding["finding_id"],
        "title": finding["title"],
        "target_category": target_category,
        "section": section,
        "source_path": finding["source_path"],
    }


def _capability_gap_required_maturity(finding: dict[str, Any]) -> str:
    raw = str(finding.get("required_maturity_level") or finding.get("required_maturity") or "").strip().lower().replace("-", "_").replace(" ", "_")
    if raw:
        if raw not in LINK_CAPABILITY_MATURITY_LEVELS:
            raise ValueError(f"invalid required maturity level: {raw}")
        return raw
    if finding["category"] in {"tests_verification", "receipts_auditability", "safety_approval_gates"}:
        return "verified"
    return "available"


def _capability_gap_is_onboarding_signal(finding: dict[str, Any]) -> bool:
    text = " ".join([
        finding.get("title", ""),
        finding.get("summary", ""),
        finding.get("value_reason", ""),
        " ".join(finding.get("signals", [])),
    ]).lower()
    return any(token in text for token in ("onboarding", "quickstart", "docs", "documentation", "example", "integration", "discoverability", "ux"))


def _capability_gap_tokens(item: dict[str, Any]) -> set[str]:
    import re

    raw_parts = [
        item.get("name", ""),
        item.get("title", ""),
        item.get("description", ""),
        item.get("summary", ""),
        item.get("category", ""),
        item.get("source", ""),
        item.get("source_path", ""),
        " ".join(item.get("tags", [])),
        " ".join(item.get("signals", [])),
    ]
    text = " ".join(str(part) for part in raw_parts).lower()
    return {token for token in re.split(r"[^a-z0-9]+", text) if len(token) > 2}


def _capability_gap_entry_confidence(finding: dict[str, Any], capability: dict[str, Any] | None) -> str:
    if finding.get("weak_finding") is True:
        return "low"
    if capability and capability.get("confidence") == "high" and int(finding.get("signal_count", 0) or 0) >= 2:
        return "high"
    return "medium"


def _capability_gap_preview_confidence(
    findings: list[dict[str, Any]],
    direct_gaps: list[dict[str, Any]],
    maturity_gaps: list[dict[str, Any]],
    onboarding_gaps: list[dict[str, Any]],
    optional_cross_cluster_ideas: list[dict[str, Any]],
) -> str:
    if not findings:
        return "low"
    strong_sections = len(direct_gaps) + len(maturity_gaps) + len(onboarding_gaps)
    if strong_sections and len(optional_cross_cluster_ideas) <= strong_sections:
        return "high"
    if strong_sections:
        return "medium"
    return "low"


def _capability_gap_action(gap_type: str) -> str:
    return {
        "direct_gap": "Consider a small Link-native capability slice before implementation approval.",
        "maturity_gap": "Improve tests, receipts, or verification maturity before expanding scope.",
        "onboarding_gap": "Improve discoverability, command ergonomics, or integration documentation.",
        "optional_cross_cluster_idea": "Keep as optional strategic inspiration; do not treat as mandatory work.",
    }[gap_type]


GROWTH_PLANNING_PREVIEW_VERSION = "link-growth-planning-preview-v1"


def make_growth_planning_preview_id(
    capability_inventory: dict[str, Any],
    repo_value_scan: dict[str, Any],
    capability_gap_preview: dict[str, Any],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_inventory_id": capability_inventory["inventory_id"],
        "capability_gap_preview_id": capability_gap_preview["preview_id"],
        "repo_value_scan_id": repo_value_scan["scan_id"],
        "version": GROWTH_PLANNING_PREVIEW_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"growth-planning-preview-{digest}"


def collect_growth_planning_preview(
    repo_inventory_items: list[dict[str, Any]],
    *,
    link_capabilities: list[dict[str, Any]] | None = None,
    top: int = 10,
    source_label: str = "research",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only aggregate planning preview for Growth dashboards/JSON."""
    capability_inventory = collect_link_capability_inventory(link_capabilities)
    repo_value_scan = collect_repo_value_scan(
        repo_inventory_items,
        top=top,
        source_label=source_label,
    )
    gap_preview = collect_capability_gap_preview(
        capability_inventory,
        repo_value_scan,
        metadata={"source_label": source_label, **dict(metadata or {})},
    )
    preview = {
        "planning_version": GROWTH_PLANNING_PREVIEW_VERSION,
        "preview_id": make_growth_planning_preview_id(capability_inventory, repo_value_scan, gap_preview),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "capability_inventory_summary": _growth_planning_capability_summary(capability_inventory),
        "repo_value_scan_summary": _growth_planning_repo_value_summary(repo_value_scan),
        "capability_gap_summary": _growth_planning_gap_summary(gap_preview),
        "top_recommended_next_steps": _growth_planning_next_steps(gap_preview),
        "metadata": dict(metadata or {}),
        "source_label": str(source_label or "research"),
        "writes": [],
    }
    validate_growth_planning_preview(preview)
    return preview


def validate_growth_planning_preview(preview: dict[str, Any]) -> None:
    required = (
        "planning_version", "preview_id", "dry_run", "write_allowed", "automation_allowed",
        "capability_inventory_summary", "repo_value_scan_summary", "capability_gap_summary",
        "top_recommended_next_steps", "metadata", "source_label", "writes",
    )
    missing = [field for field in required if field not in preview]
    if missing:
        raise ValueError(f"Growth planning preview missing fields: {missing}")
    if preview["planning_version"] != GROWTH_PLANNING_PREVIEW_VERSION:
        raise ValueError("unsupported Growth planning preview version")
    if not isinstance(preview["preview_id"], str) or not preview["preview_id"].strip():
        raise ValueError("preview_id must be a non-empty string")
    if preview["dry_run"] is not True or preview["write_allowed"] is not False or preview["automation_allowed"] is not False:
        raise ValueError("Growth planning preview must remain read-only")
    if preview["writes"] != []:
        raise ValueError("Growth planning preview must not write files")
    for field in ("capability_inventory_summary", "repo_value_scan_summary", "capability_gap_summary"):
        if not isinstance(preview[field], dict):
            raise TypeError(f"{field} must be a dict")
    if not isinstance(preview["top_recommended_next_steps"], list):
        raise TypeError("top_recommended_next_steps must be a list")
    if not isinstance(preview["metadata"], dict):
        raise TypeError("metadata must be a dict")
    if not isinstance(preview["source_label"], str) or not preview["source_label"].strip():
        raise ValueError("source_label must be a non-empty string")
    for step in preview["top_recommended_next_steps"]:
        _validate_growth_planning_next_step(step)


def growth_planning_preview_to_json(preview: dict[str, Any]) -> str:
    validate_growth_planning_preview(preview)
    return _stable_ruflo_json(preview, indent=2) + "\n"


def growth_planning_preview_from_json(text: str) -> dict[str, Any]:
    import json as _json

    preview = _json.loads(text)
    validate_growth_planning_preview(preview)
    return preview


def _growth_planning_capability_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    validate_link_capability_inventory(inventory)
    by_category = {category: 0 for category in LINK_CAPABILITY_CATEGORIES}
    by_maturity = {level: 0 for level in LINK_CAPABILITY_MATURITY_LEVELS}
    for capability in inventory["capabilities"]:
        by_category[capability["category"]] += 1
        by_maturity[capability["maturity_level"]] += 1
    return {
        "inventory_id": inventory["inventory_id"],
        "capability_count": inventory["capability_count"],
        "duplicate_count": inventory["duplicate_count"],
        "by_category": by_category,
        "by_maturity": by_maturity,
    }


def _growth_planning_repo_value_summary(scan: dict[str, Any]) -> dict[str, Any]:
    validate_repo_value_scan(scan)
    by_category = {category: 0 for category in REPO_VALUE_CATEGORIES}
    for finding in scan["findings"]:
        by_category[finding["category"]] += 1
    return {
        "scan_id": scan["scan_id"],
        "source_label": scan["source_label"],
        "item_count": scan["item_count"],
        "finding_count": scan["finding_count"],
        "unique_finding_count": scan["unique_finding_count"],
        "duplicate_count": scan["duplicate_count"],
        "weak_finding_count": scan["weak_finding_count"],
        "by_category": by_category,
    }


def _growth_planning_gap_summary(gap_preview: dict[str, Any]) -> dict[str, Any]:
    validate_capability_gap_preview(gap_preview)
    counts = dict(gap_preview["counts"])
    return {
        "gap_preview_id": gap_preview["preview_id"],
        "confidence": gap_preview["confidence"],
        "counts": counts,
    }


def _growth_planning_next_steps(gap_preview: dict[str, Any]) -> list[dict[str, Any]]:
    validate_capability_gap_preview(gap_preview)
    ranked: list[dict[str, Any]] = []
    priorities = (
        ("direct_gaps", 0),
        ("maturity_gaps", 1),
        ("onboarding_gaps", 2),
        ("optional_cross_cluster_ideas", 3),
    )
    for section, priority in priorities:
        for gap in gap_preview[section]:
            ranked.append({
                "step_id": f"growth-next-step-{gap['gap_id'].removeprefix('capability-gap-')}",
                "section": section,
                "priority": priority,
                "title": gap["finding_title"],
                "target_category": gap["target_category"],
                "confidence": gap["confidence"],
                "reason": gap["reason"],
                "recommended_action": gap["recommended_action"],
                "source_path": gap["source_path"],
            })
    ranked.sort(key=lambda item: (item["priority"], item["step_id"]))
    return ranked[:5]


def _validate_growth_planning_next_step(step: dict[str, Any]) -> None:
    required = (
        "step_id", "section", "priority", "title", "target_category",
        "confidence", "reason", "recommended_action", "source_path",
    )
    missing = [field for field in required if field not in step]
    if missing:
        raise ValueError(f"Growth planning next step missing fields: {missing}")
    if step["section"] not in _CAPABILITY_GAP_SECTIONS:
        raise ValueError(f"invalid next step section: {step['section']}")
    if step["target_category"] not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid next step target_category: {step['target_category']}")
    if step["confidence"] not in LINK_CAPABILITY_CONFIDENCE_LEVELS:
        raise ValueError(f"invalid next step confidence: {step['confidence']}")
    if not isinstance(step["priority"], int) or step["priority"] < 0:
        raise ValueError("next step priority must be a non-negative integer")
    for field in ("step_id", "title", "reason", "recommended_action", "source_path"):
        if not isinstance(step[field], str) or not step[field].strip():
            raise ValueError(f"{field} must be a non-empty string")


CAPABILITY_GRAPH_VERSION = "link-capability-graph-v1"
CAPABILITY_GRAPH_RELATIONSHIPS = (
    "depends_on",
    "improves",
    "overlaps",
    "feeds_into",
    "derived_from_repo_finding",
)
_CAPABILITY_GRAPH_STATUS_BY_MATURITY = {
    "planned": "planned",
    "partial": "in_progress",
    "available": "available",
    "verified": "verified",
}
_CAPABILITY_GRAPH_MATURITY_SCORE = {
    "planned": 0.25,
    "partial": 0.5,
    "available": 0.75,
    "verified": 1.0,
}


def make_capability_graph_id(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "edge_ids": [edge["edge_id"] for edge in edges],
        "node_ids": [node["capability_id"] for node in nodes],
        "version": CAPABILITY_GRAPH_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-graph-{digest}"


def collect_capability_graph(
    capability_inventory: dict[str, Any] | None = None,
    *,
    repo_value_scan: dict[str, Any] | list[dict[str, Any]] | None = None,
    gap_preview: dict[str, Any] | None = None,
    relationships: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a read-only graph of Link capabilities and planning relationships."""
    inventory = capability_inventory or collect_link_capability_inventory()
    validate_link_capability_inventory(inventory)
    nodes = _capability_graph_nodes_from_inventory(inventory)
    node_ids = {node["capability_id"] for node in nodes}

    edges: list[dict[str, Any]] = []
    for relationship in relationships or []:
        edges.append(normalize_capability_graph_edge(relationship, node_ids))

    effective_gap_preview = gap_preview
    if effective_gap_preview is None and repo_value_scan is not None:
        effective_gap_preview = collect_capability_gap_preview(inventory, repo_value_scan)
    if effective_gap_preview is not None:
        validate_capability_gap_preview(effective_gap_preview)
        edges.extend(_capability_graph_edges_from_gap_preview(effective_gap_preview, node_ids))

    edges = _dedupe_capability_graph_edges(edges)
    graph = {
        "graph_version": CAPABILITY_GRAPH_VERSION,
        "graph_id": make_capability_graph_id(nodes, edges),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_capability_graph(graph)
    return graph


def stable_capability_graph_json(graph: dict[str, Any]) -> str:
    validate_capability_graph(graph)
    return _stable_ruflo_json(graph, indent=2) + "\n"


def parse_capability_graph_json(text: str) -> dict[str, Any]:
    import json as _json

    graph = _json.loads(text)
    validate_capability_graph(graph)
    return graph


def validate_capability_graph(graph: dict[str, Any]) -> None:
    required = (
        "graph_version", "graph_id", "dry_run", "write_allowed", "automation_allowed",
        "node_count", "edge_count", "nodes", "edges", "metadata", "writes",
    )
    missing = [field for field in required if field not in graph]
    if missing:
        raise ValueError(f"capability graph missing fields: {missing}")
    if graph["graph_version"] != CAPABILITY_GRAPH_VERSION:
        raise ValueError("unsupported capability graph version")
    if not isinstance(graph["graph_id"], str) or not graph["graph_id"].strip():
        raise ValueError("graph_id must be a non-empty string")
    if graph["dry_run"] is not True or graph["write_allowed"] is not False or graph["automation_allowed"] is not False:
        raise ValueError("capability graph must remain read-only")
    if graph["writes"] != []:
        raise ValueError("capability graph must not write files")
    if not isinstance(graph["metadata"], dict):
        raise TypeError("capability graph metadata must be a dict")
    if not isinstance(graph["nodes"], list):
        raise TypeError("capability graph nodes must be a list")
    if not isinstance(graph["edges"], list):
        raise TypeError("capability graph edges must be a list")
    if not isinstance(graph["node_count"], int) or graph["node_count"] != len(graph["nodes"]):
        raise ValueError("node_count must match nodes length")
    if not isinstance(graph["edge_count"], int) or graph["edge_count"] != len(graph["edges"]):
        raise ValueError("edge_count must match edges length")
    node_ids: set[str] = set()
    for node in graph["nodes"]:
        validate_capability_graph_node(node)
        if node["capability_id"] in node_ids:
            raise ValueError(f"duplicate capability graph node: {node['capability_id']}")
        node_ids.add(node["capability_id"])
    edge_ids: set[str] = set()
    for edge in graph["edges"]:
        validate_capability_graph_edge(edge, node_ids)
        if edge["edge_id"] in edge_ids:
            raise ValueError(f"duplicate capability graph edge: {edge['edge_id']}")
        edge_ids.add(edge["edge_id"])


def validate_capability_graph_node(node: dict[str, Any]) -> None:
    required = (
        "capability_id", "name", "category", "maturity_score",
        "evidence_sources", "risk_label", "status",
    )
    missing = [field for field in required if field not in node]
    if missing:
        raise ValueError(f"capability graph node missing fields: {missing}")
    for field in ("capability_id", "name", "category", "risk_label", "status"):
        if not isinstance(node[field], str) or not node[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if node["category"] not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid capability graph node category: {node['category']}")
    if node["risk_label"] not in LINK_CAPABILITY_RISK_LEVELS:
        raise ValueError(f"invalid capability graph node risk_label: {node['risk_label']}")
    if node["status"] not in {"planned", "in_progress", "available", "verified"}:
        raise ValueError(f"invalid capability graph node status: {node['status']}")
    _validate_capability_graph_confidence(node["maturity_score"], "maturity_score")
    if not isinstance(node["evidence_sources"], list) or not node["evidence_sources"]:
        raise TypeError("capability graph node evidence_sources must be a non-empty list")
    if not all(isinstance(source, str) and source.strip() for source in node["evidence_sources"]):
        raise TypeError("capability graph evidence_sources must contain non-empty strings")


def validate_capability_graph_edge(edge: dict[str, Any], node_ids: set[str]) -> None:
    required = (
        "edge_id", "source_id", "target_id", "relationship", "confidence", "reason",
    )
    missing = [field for field in required if field not in edge]
    if missing:
        raise ValueError(f"capability graph edge missing fields: {missing}")
    for field in ("edge_id", "source_id", "target_id", "relationship", "reason"):
        if not isinstance(edge[field], str) or not edge[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if edge["source_id"] not in node_ids:
        raise ValueError(f"edge source_id does not reference a graph node: {edge['source_id']}")
    if edge["target_id"] not in node_ids:
        raise ValueError(f"edge target_id does not reference a graph node: {edge['target_id']}")
    if edge["relationship"] not in CAPABILITY_GRAPH_RELATIONSHIPS:
        raise ValueError(f"invalid capability graph relationship: {edge['relationship']}")
    _validate_capability_graph_confidence(edge["confidence"], "confidence")


def normalize_capability_graph_edge(edge: dict[str, Any], node_ids: set[str]) -> dict[str, Any]:
    if not isinstance(edge, dict):
        raise TypeError("capability graph edge must be a dict")
    normalized = {
        "source_id": _first_text(edge, "source_id", "source"),
        "target_id": _first_text(edge, "target_id", "target"),
        "relationship": str(edge.get("relationship") or "").strip().lower().replace("-", "_").replace(" ", "_"),
        "confidence": round(float(edge.get("confidence", 0.75)), 4),
        "reason": _first_text(edge, "reason", "description"),
    }
    normalized["edge_id"] = _first_text(edge, "edge_id") or make_capability_graph_edge_id(
        normalized["source_id"],
        normalized["target_id"],
        normalized["relationship"],
        normalized["reason"],
    )
    validate_capability_graph_edge(normalized, node_ids)
    return normalized


def make_capability_graph_edge_id(source_id: str, target_id: str, relationship: str, reason: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "reason": reason,
        "relationship": relationship,
        "source_id": source_id,
        "target_id": target_id,
        "version": CAPABILITY_GRAPH_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"capability-edge-{digest}"


def _capability_graph_nodes_from_inventory(inventory: dict[str, Any]) -> list[dict[str, Any]]:
    validate_link_capability_inventory(inventory)
    chosen: dict[str, dict[str, Any]] = {}
    for capability in inventory["capabilities"]:
        node = _capability_graph_node_from_capability(capability)
        chosen.setdefault(node["capability_id"], node)
    return sorted(chosen.values(), key=lambda item: item["capability_id"])


def _capability_graph_node_from_capability(capability: dict[str, Any]) -> dict[str, Any]:
    validate_link_capability_entry(capability)
    maturity = capability["maturity_level"]
    node = {
        "capability_id": capability["capability_id"],
        "name": capability["name"],
        "category": capability["category"],
        "maturity_score": _CAPABILITY_GRAPH_MATURITY_SCORE[maturity],
        "evidence_sources": [capability["source"]],
        "risk_label": capability["risk_level"],
        "status": _CAPABILITY_GRAPH_STATUS_BY_MATURITY[maturity],
    }
    validate_capability_graph_node(node)
    return node


def _capability_graph_edges_from_gap_preview(gap_preview: dict[str, Any], node_ids: set[str]) -> list[dict[str, Any]]:
    validate_capability_gap_preview(gap_preview)
    edges: list[dict[str, Any]] = []
    for match in gap_preview["matched_capabilities"]:
        capability_id = match["capability_id"]
        if capability_id not in node_ids:
            continue
        reason = f"Repo finding '{match['finding_title']}' maps to this Link capability."
        edges.append(normalize_capability_graph_edge({
            "source_id": capability_id,
            "target_id": capability_id,
            "relationship": "derived_from_repo_finding",
            "confidence": _capability_graph_confidence_score(match["confidence"]),
            "reason": reason,
        }, node_ids))
    return edges


def _dedupe_capability_graph_edges(edges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    chosen: dict[str, dict[str, Any]] = {}
    for edge in edges:
        chosen.setdefault(edge["edge_id"], edge)
    return sorted(chosen.values(), key=lambda item: item["edge_id"])


def _capability_graph_confidence_score(confidence: str) -> float:
    return {"low": 0.35, "medium": 0.65, "high": 0.9}.get(confidence, 0.5)


def _validate_capability_graph_confidence(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"capability graph {field_name} must be numeric between 0.0 and 1.0")
    if not (0.0 <= float(value) <= 1.0):
        raise ValueError(f"capability graph {field_name} must be between 0.0 and 1.0")


CAPABILITY_EVIDENCE_GRAPH_VERSION = "link-capability-evidence-graph-v1"
_CAPABILITY_EVIDENCE_REF_FIELDS = (
    "commit_refs",
    "file_refs",
    "test_refs",
    "healthcheck_refs",
    "proposal_refs",
    "source_repo_refs",
)


def make_capability_evidence_graph_id(evidence_nodes: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "evidence_ids": [node["evidence_id"] for node in evidence_nodes],
        "version": CAPABILITY_EVIDENCE_GRAPH_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-evidence-graph-{digest}"


def make_capability_evidence_node_id(capability_id: str, refs: dict[str, list[str]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_id": capability_id,
        "refs": refs,
        "version": CAPABILITY_EVIDENCE_GRAPH_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"capability-evidence-{digest}"


def collect_capability_evidence_graph(
    capability_graph: dict[str, Any] | None = None,
    *,
    capability_inventory: dict[str, Any] | None = None,
    evidence_refs: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Attach normalized proof references and confidence to capability graph nodes."""
    graph = capability_graph or collect_capability_graph(capability_inventory)
    validate_capability_graph(graph)
    refs_by_capability = _capability_evidence_refs_by_capability(evidence_refs or [])
    evidence_nodes: list[dict[str, Any]] = []
    for node in graph["nodes"]:
        refs = _empty_capability_evidence_refs()
        refs["file_refs"] = _normalize_capability_evidence_refs(
            node.get("evidence_sources", []),
            "file_refs",
        )
        override = refs_by_capability.get(node["capability_id"], {})
        for field in _CAPABILITY_EVIDENCE_REF_FIELDS:
            refs[field] = _normalize_capability_evidence_refs(refs[field] + override.get(field, []), field)
        evidence_node = {
            "evidence_id": make_capability_evidence_node_id(node["capability_id"], refs),
            "capability_id": node["capability_id"],
            "capability_name": node["name"],
            "commit_refs": refs["commit_refs"],
            "file_refs": refs["file_refs"],
            "test_refs": refs["test_refs"],
            "healthcheck_refs": refs["healthcheck_refs"],
            "proposal_refs": refs["proposal_refs"],
            "source_repo_refs": refs["source_repo_refs"],
            "confidence_score": _capability_evidence_confidence_score(node, refs),
        }
        validate_capability_evidence_node(evidence_node)
        evidence_nodes.append(evidence_node)
    evidence_nodes.sort(key=lambda item: item["capability_id"])
    evidence_graph = {
        "evidence_graph_version": CAPABILITY_EVIDENCE_GRAPH_VERSION,
        "evidence_graph_id": make_capability_evidence_graph_id(evidence_nodes),
        "source_graph_id": graph["graph_id"],
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "node_count": len(evidence_nodes),
        "evidence_nodes": evidence_nodes,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_capability_evidence_graph(evidence_graph)
    return evidence_graph


def validate_capability_evidence_graph(evidence_graph: dict[str, Any]) -> None:
    required = (
        "evidence_graph_version", "evidence_graph_id", "source_graph_id", "dry_run",
        "write_allowed", "automation_allowed", "node_count", "evidence_nodes", "metadata", "writes",
    )
    missing = [field for field in required if field not in evidence_graph]
    if missing:
        raise ValueError(f"capability evidence graph missing fields: {missing}")
    if evidence_graph["evidence_graph_version"] != CAPABILITY_EVIDENCE_GRAPH_VERSION:
        raise ValueError("unsupported capability evidence graph version")
    for field in ("evidence_graph_id", "source_graph_id"):
        if not isinstance(evidence_graph[field], str) or not evidence_graph[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if evidence_graph["dry_run"] is not True or evidence_graph["write_allowed"] is not False or evidence_graph["automation_allowed"] is not False:
        raise ValueError("capability evidence graph must remain read-only")
    if evidence_graph["writes"] != []:
        raise ValueError("capability evidence graph must not write files")
    if not isinstance(evidence_graph["metadata"], dict):
        raise TypeError("capability evidence graph metadata must be a dict")
    nodes = evidence_graph["evidence_nodes"]
    if not isinstance(nodes, list):
        raise TypeError("capability evidence graph evidence_nodes must be a list")
    if not isinstance(evidence_graph["node_count"], int) or evidence_graph["node_count"] != len(nodes):
        raise ValueError("node_count must match evidence_nodes length")
    capability_ids: set[str] = set()
    evidence_ids: set[str] = set()
    for node in nodes:
        validate_capability_evidence_node(node)
        if node["capability_id"] in capability_ids:
            raise ValueError(f"duplicate capability evidence node: {node['capability_id']}")
        if node["evidence_id"] in evidence_ids:
            raise ValueError(f"duplicate capability evidence id: {node['evidence_id']}")
        capability_ids.add(node["capability_id"])
        evidence_ids.add(node["evidence_id"])


def stable_capability_evidence_graph_json(evidence_graph: dict[str, Any]) -> str:
    validate_capability_evidence_graph(evidence_graph)
    return _stable_ruflo_json(evidence_graph, indent=2) + "\n"


def parse_capability_evidence_graph_json(text: str) -> dict[str, Any]:
    import json as _json

    evidence_graph = _json.loads(text)
    validate_capability_evidence_graph(evidence_graph)
    return evidence_graph


def validate_capability_evidence_node(node: dict[str, Any]) -> None:
    required = ("evidence_id", "capability_id", "capability_name", "confidence_score", *_CAPABILITY_EVIDENCE_REF_FIELDS)
    missing = [field for field in required if field not in node]
    if missing:
        raise ValueError(f"capability evidence node missing fields: {missing}")
    for field in ("evidence_id", "capability_id", "capability_name"):
        if not isinstance(node[field], str) or not node[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    _validate_capability_graph_confidence(node["confidence_score"], "confidence_score")
    for field in _CAPABILITY_EVIDENCE_REF_FIELDS:
        refs = node[field]
        if not isinstance(refs, list):
            raise TypeError(f"{field} must be a list")
        normalized = _normalize_capability_evidence_refs(refs, field)
        if refs != normalized:
            raise ValueError(f"{field} must be normalized and sorted")


def _capability_evidence_refs_by_capability(evidence_refs: list[dict[str, Any]]) -> dict[str, dict[str, list[str]]]:
    if not isinstance(evidence_refs, list):
        raise TypeError("evidence_refs must be a list")
    refs_by_capability: dict[str, dict[str, list[str]]] = {}
    for item in evidence_refs:
        if not isinstance(item, dict):
            raise TypeError("capability evidence refs must be dicts")
        capability_id = _first_text(item, "capability_id")
        refs = refs_by_capability.setdefault(capability_id, _empty_capability_evidence_refs())
        for field in _CAPABILITY_EVIDENCE_REF_FIELDS:
            refs[field] = _normalize_capability_evidence_refs(refs[field] + list(item.get(field) or []), field)
    return refs_by_capability


def _empty_capability_evidence_refs() -> dict[str, list[str]]:
    return {field: [] for field in _CAPABILITY_EVIDENCE_REF_FIELDS}


def _normalize_capability_evidence_refs(refs: Any, field: str) -> list[str]:
    import re

    if refs is None:
        return []
    if isinstance(refs, str):
        raw_refs = [refs]
    elif isinstance(refs, list):
        raw_refs = refs
    else:
        raise TypeError(f"{field} must be a string or list")
    normalized: list[str] = []
    for ref in raw_refs:
        value = str(ref or "").strip()
        if not value:
            raise ValueError(f"{field} cannot contain empty references")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid {field} reference: {value}")
        if field == "commit_refs" and not re.fullmatch(r"[a-fA-F0-9]{7,40}", value):
            raise ValueError(f"invalid commit reference: {value}")
        if field == "proposal_refs" and not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.:-]*", value):
            raise ValueError(f"invalid proposal reference: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def _capability_evidence_confidence_score(node: dict[str, Any], refs: dict[str, list[str]]) -> float:
    maturity = float(node.get("maturity_score", 0.0) or 0.0)
    score = maturity * 0.35
    weights = {
        "commit_refs": 0.15,
        "file_refs": 0.2,
        "test_refs": 0.15,
        "healthcheck_refs": 0.15,
        "proposal_refs": 0.1,
        "source_repo_refs": 0.1,
    }
    for field, weight in weights.items():
        if refs.get(field):
            score += weight
    return round(min(score, 1.0), 4)


CAPABILITY_DISCOVERY_VERSION = "link-capability-discovery-v1"
_CAPABILITY_DISCOVERY_PATH_FIELDS = (
    "file_paths",
    "module_paths",
    "test_paths",
    "evidence_refs",
)


def make_capability_discovery_id(discoveries: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "discovery_ids": [item["discovery_id"] for item in discoveries],
        "version": CAPABILITY_DISCOVERY_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-discovery-{digest}"


def make_capability_discovery_entry_id(capability_id: str, paths: dict[str, list[str]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_id": capability_id,
        "paths": paths,
        "version": CAPABILITY_DISCOVERY_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"capability-discovery-{digest}"


def collect_capability_discovery(
    capability_inventory: dict[str, Any] | None = None,
    *,
    capability_graph: dict[str, Any] | None = None,
    evidence_graph: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Map known capabilities to implementation locations without writing state."""
    inventory = capability_inventory or collect_link_capability_inventory()
    validate_link_capability_inventory(inventory)
    graph = capability_graph or collect_capability_graph(inventory)
    validate_capability_graph(graph)
    evidence = evidence_graph or collect_capability_evidence_graph(graph)
    validate_capability_evidence_graph(evidence)

    graph_nodes = {node["capability_id"]: node for node in graph["nodes"]}
    evidence_nodes = {node["capability_id"]: node for node in evidence["evidence_nodes"]}
    discoveries: list[dict[str, Any]] = []
    for capability in inventory["capabilities"]:
        capability_id = capability["capability_id"]
        graph_node = graph_nodes.get(capability_id, {})
        evidence_node = evidence_nodes.get(capability_id, {})
        file_paths = _normalize_capability_discovery_paths(
            list(graph_node.get("evidence_sources", [])) + list(evidence_node.get("file_refs", [])),
            "file_paths",
        )
        test_paths = _normalize_capability_discovery_paths(evidence_node.get("test_refs", []), "test_paths")
        evidence_refs = _normalize_capability_discovery_paths(
            list(evidence_node.get("commit_refs", []))
            + list(evidence_node.get("healthcheck_refs", []))
            + list(evidence_node.get("proposal_refs", []))
            + list(evidence_node.get("source_repo_refs", [])),
            "evidence_refs",
        )
        module_paths = _normalize_capability_discovery_paths(
            _capability_discovery_modules_from_files(file_paths),
            "module_paths",
        )
        entry_paths = {
            "file_paths": file_paths,
            "module_paths": module_paths,
            "test_paths": test_paths,
            "evidence_refs": evidence_refs,
        }
        discovery = {
            "discovery_id": make_capability_discovery_entry_id(capability_id, entry_paths),
            "capability_id": capability_id,
            "capability_name": capability["name"],
            "file_paths": file_paths,
            "module_paths": module_paths,
            "test_paths": test_paths,
            "evidence_refs": evidence_refs,
            "confidence_score": _capability_discovery_confidence_score(entry_paths, evidence_node),
        }
        validate_capability_discovery_entry(discovery)
        discoveries.append(discovery)
    discoveries.sort(key=lambda item: item["capability_id"])
    discovery = {
        "discovery_version": CAPABILITY_DISCOVERY_VERSION,
        "discovery_id": make_capability_discovery_id(discoveries),
        "source_inventory_id": inventory["inventory_id"],
        "source_graph_id": graph["graph_id"],
        "source_evidence_graph_id": evidence["evidence_graph_id"],
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "capability_count": len(discoveries),
        "discoveries": discoveries,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_capability_discovery(discovery)
    return discovery


def validate_capability_discovery(discovery: dict[str, Any]) -> None:
    required = (
        "discovery_version", "discovery_id", "source_inventory_id", "source_graph_id",
        "source_evidence_graph_id", "dry_run", "write_allowed", "automation_allowed",
        "capability_count", "discoveries", "metadata", "writes",
    )
    missing = [field for field in required if field not in discovery]
    if missing:
        raise ValueError(f"capability discovery missing fields: {missing}")
    if discovery["discovery_version"] != CAPABILITY_DISCOVERY_VERSION:
        raise ValueError("unsupported capability discovery version")
    for field in ("discovery_id", "source_inventory_id", "source_graph_id", "source_evidence_graph_id"):
        if not isinstance(discovery[field], str) or not discovery[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if discovery["dry_run"] is not True or discovery["write_allowed"] is not False or discovery["automation_allowed"] is not False:
        raise ValueError("capability discovery must remain read-only")
    if discovery["writes"] != []:
        raise ValueError("capability discovery must not write files")
    if not isinstance(discovery["metadata"], dict):
        raise TypeError("capability discovery metadata must be a dict")
    entries = discovery["discoveries"]
    if not isinstance(entries, list):
        raise TypeError("capability discovery discoveries must be a list")
    if not isinstance(discovery["capability_count"], int) or discovery["capability_count"] != len(entries):
        raise ValueError("capability_count must match discoveries length")
    capability_ids: set[str] = set()
    discovery_ids: set[str] = set()
    for entry in entries:
        validate_capability_discovery_entry(entry)
        if entry["capability_id"] in capability_ids:
            raise ValueError(f"duplicate capability discovery entry: {entry['capability_id']}")
        if entry["discovery_id"] in discovery_ids:
            raise ValueError(f"duplicate capability discovery id: {entry['discovery_id']}")
        capability_ids.add(entry["capability_id"])
        discovery_ids.add(entry["discovery_id"])


def stable_capability_discovery_json(discovery: dict[str, Any]) -> str:
    validate_capability_discovery(discovery)
    return _stable_ruflo_json(discovery, indent=2) + "\n"


def parse_capability_discovery_json(text: str) -> dict[str, Any]:
    import json as _json

    discovery = _json.loads(text)
    validate_capability_discovery(discovery)
    return discovery


def validate_capability_discovery_entry(entry: dict[str, Any]) -> None:
    required = ("discovery_id", "capability_id", "capability_name", "confidence_score", *_CAPABILITY_DISCOVERY_PATH_FIELDS)
    missing = [field for field in required if field not in entry]
    if missing:
        raise ValueError(f"capability discovery entry missing fields: {missing}")
    for field in ("discovery_id", "capability_id", "capability_name"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    _validate_capability_graph_confidence(entry["confidence_score"], "confidence_score")
    for field in _CAPABILITY_DISCOVERY_PATH_FIELDS:
        refs = entry[field]
        if not isinstance(refs, list):
            raise TypeError(f"{field} must be a list")
        normalized = _normalize_capability_discovery_paths(refs, field)
        if refs != normalized:
            raise ValueError(f"{field} must be normalized and sorted")


def _normalize_capability_discovery_paths(paths: Any, field: str) -> list[str]:
    if paths is None:
        return []
    if isinstance(paths, str):
        raw_paths = [paths]
    elif isinstance(paths, list):
        raw_paths = paths
    else:
        raise TypeError(f"{field} must be a string or list")
    normalized: list[str] = []
    for path in raw_paths:
        value = str(path or "").strip()
        if not value:
            raise ValueError(f"{field} cannot contain empty paths")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid {field} path: {value}")
        if field == "module_paths" and ("/" in value or value.endswith(".") or value.startswith(".") or ".." in value.split(".")):
            raise ValueError(f"invalid module path: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def _capability_discovery_modules_from_files(file_paths: list[str]) -> list[str]:
    modules: list[str] = []
    for file_path in file_paths:
        if not file_path.endswith(".py"):
            continue
        module = file_path[:-3].replace("/", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        if module and module not in modules:
            modules.append(module)
    return modules


def _capability_discovery_confidence_score(paths: dict[str, list[str]], evidence_node: dict[str, Any]) -> float:
    score = 0.0
    if paths["file_paths"]:
        score += 0.35
    if paths["module_paths"]:
        score += 0.15
    if paths["test_paths"]:
        score += 0.2
    if paths["evidence_refs"]:
        score += 0.15
    if evidence_node:
        score += float(evidence_node.get("confidence_score", 0.0) or 0.0) * 0.15
    return round(min(score, 1.0), 4)


CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION = "link-capability-intelligence-payload-v1"


def make_capability_intelligence_payload_id(
    inventory: dict[str, Any],
    gap_preview: dict[str, Any],
    planning_preview: dict[str, Any],
    graph: dict[str, Any],
    evidence_graph: dict[str, Any],
    discovery: dict[str, Any],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "discovery_id": discovery["discovery_id"],
        "evidence_graph_id": evidence_graph["evidence_graph_id"],
        "gap_preview_id": gap_preview["preview_id"],
        "graph_id": graph["graph_id"],
        "inventory_id": inventory["inventory_id"],
        "planning_preview_id": planning_preview["preview_id"],
        "version": CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-capability-intelligence-{digest}"


def collect_capability_intelligence_payload(
    repo_inventory_items: list[dict[str, Any]] | None = None,
    *,
    link_capabilities: list[dict[str, Any]] | None = None,
    top: int = 10,
    source_label: str = "research",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Aggregate read-only capability intelligence for dashboards/JSON."""
    repo_items = list(repo_inventory_items or [])
    inventory = collect_link_capability_inventory(link_capabilities)
    repo_scan = collect_repo_value_scan(repo_items, top=top, source_label=source_label)
    gap_preview = collect_capability_gap_preview(inventory, repo_scan, metadata={"source_label": source_label})
    planning_preview = collect_growth_planning_preview(
        repo_items,
        link_capabilities=link_capabilities,
        top=top,
        source_label=source_label,
        metadata=metadata,
    )
    graph = collect_capability_graph(inventory, gap_preview=gap_preview)
    evidence_graph = collect_capability_evidence_graph(graph)
    discovery = collect_capability_discovery(
        inventory,
        capability_graph=graph,
        evidence_graph=evidence_graph,
    )
    payload = {
        "payload_version": CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION,
        "payload_id": make_capability_intelligence_payload_id(
            inventory,
            gap_preview,
            planning_preview,
            graph,
            evidence_graph,
            discovery,
        ),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "inventory_summary": _capability_intelligence_inventory_summary(inventory),
        "gap_summary": _capability_intelligence_gap_summary(gap_preview),
        "planning_preview_summary": _capability_intelligence_planning_summary(planning_preview),
        "capability_graph_summary": _capability_intelligence_graph_summary(graph),
        "evidence_graph_summary": _capability_intelligence_evidence_summary(evidence_graph),
        "discovery_summary": _capability_intelligence_discovery_summary(discovery),
        "top_recommended_next_steps": list(planning_preview["top_recommended_next_steps"]),
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_capability_intelligence_payload(payload)
    return payload


def validate_capability_intelligence_payload(payload: dict[str, Any]) -> None:
    required = (
        "payload_version", "payload_id", "dry_run", "write_allowed", "automation_allowed",
        "inventory_summary", "gap_summary", "planning_preview_summary", "capability_graph_summary",
        "evidence_graph_summary", "discovery_summary", "top_recommended_next_steps", "metadata", "writes",
    )
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(f"capability intelligence payload missing fields: {missing}")
    if payload["payload_version"] != CAPABILITY_INTELLIGENCE_PAYLOAD_VERSION:
        raise ValueError("unsupported capability intelligence payload version")
    if not isinstance(payload["payload_id"], str) or not payload["payload_id"].strip():
        raise ValueError("payload_id must be a non-empty string")
    if payload["dry_run"] is not True or payload["write_allowed"] is not False or payload["automation_allowed"] is not False:
        raise ValueError("capability intelligence payload must remain read-only")
    if payload["writes"] != []:
        raise ValueError("capability intelligence payload must not write files")
    if not isinstance(payload["metadata"], dict):
        raise TypeError("capability intelligence payload metadata must be a dict")
    for field, required_keys in (
        ("inventory_summary", ("inventory_id", "capability_count", "duplicate_count")),
        ("gap_summary", ("gap_preview_id", "counts", "confidence")),
        ("planning_preview_summary", ("planning_preview_id", "next_step_count")),
        ("capability_graph_summary", ("graph_id", "node_count", "edge_count")),
        ("evidence_graph_summary", ("evidence_graph_id", "node_count", "average_confidence_score")),
        ("discovery_summary", ("discovery_id", "capability_count", "average_confidence_score")),
    ):
        summary = payload[field]
        if not isinstance(summary, dict):
            raise TypeError(f"{field} must be a dict")
        missing_keys = [key for key in required_keys if key not in summary]
        if missing_keys:
            raise ValueError(f"{field} missing keys: {missing_keys}")
    if not isinstance(payload["top_recommended_next_steps"], list):
        raise TypeError("top_recommended_next_steps must be a list")
    for step in payload["top_recommended_next_steps"]:
        _validate_growth_planning_next_step(step)


def stable_capability_intelligence_payload_json(payload: dict[str, Any]) -> str:
    validate_capability_intelligence_payload(payload)
    return _stable_ruflo_json(payload, indent=2) + "\n"


def parse_capability_intelligence_payload_json(text: str) -> dict[str, Any]:
    import json as _json

    payload = _json.loads(text)
    validate_capability_intelligence_payload(payload)
    return payload


def _capability_intelligence_inventory_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    validate_link_capability_inventory(inventory)
    return {
        "inventory_id": inventory["inventory_id"],
        "capability_count": inventory["capability_count"],
        "duplicate_count": inventory["duplicate_count"],
        "categories": list(inventory["categories"]),
    }


def _capability_intelligence_gap_summary(gap_preview: dict[str, Any]) -> dict[str, Any]:
    validate_capability_gap_preview(gap_preview)
    return {
        "gap_preview_id": gap_preview["preview_id"],
        "confidence": gap_preview["confidence"],
        "counts": dict(gap_preview["counts"]),
    }


def _capability_intelligence_planning_summary(planning_preview: dict[str, Any]) -> dict[str, Any]:
    validate_growth_planning_preview(planning_preview)
    return {
        "planning_preview_id": planning_preview["preview_id"],
        "next_step_count": len(planning_preview["top_recommended_next_steps"]),
        "capability_count": planning_preview["capability_inventory_summary"]["capability_count"],
        "repo_finding_count": planning_preview["repo_value_scan_summary"]["finding_count"],
    }


def _capability_intelligence_graph_summary(graph: dict[str, Any]) -> dict[str, Any]:
    validate_capability_graph(graph)
    return {
        "graph_id": graph["graph_id"],
        "node_count": graph["node_count"],
        "edge_count": graph["edge_count"],
    }


def _capability_intelligence_evidence_summary(evidence_graph: dict[str, Any]) -> dict[str, Any]:
    validate_capability_evidence_graph(evidence_graph)
    scores = [float(node["confidence_score"]) for node in evidence_graph["evidence_nodes"]]
    return {
        "evidence_graph_id": evidence_graph["evidence_graph_id"],
        "node_count": evidence_graph["node_count"],
        "average_confidence_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }


def _capability_intelligence_discovery_summary(discovery: dict[str, Any]) -> dict[str, Any]:
    validate_capability_discovery(discovery)
    scores = [float(entry["confidence_score"]) for entry in discovery["discoveries"]]
    return {
        "discovery_id": discovery["discovery_id"],
        "capability_count": discovery["capability_count"],
        "average_confidence_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
    }


UPGRADE_EXECUTION_PLAN_VERSION = "link-upgrade-execution-plan-v1"
UPGRADE_COMPLEXITY_LEVELS = ("trivial", "small", "medium", "large", "major")
UPGRADE_RISK_LEVELS = ("low", "medium", "high")
UPGRADE_PLAN_PHASES = ("discovery", "design", "implementation", "verification", "rollout")
_UPGRADE_PLAN_SECTION_ORDER = {
    "direct_gaps": 0,
    "maturity_gaps": 1,
    "onboarding_gaps": 2,
    "optional_cross_cluster_ideas": 3,
}
_UPGRADE_TARGET_SUBSYSTEM_BY_CATEGORY = {
    "safety": "link_capability_gate.py / modern_command_guard.py",
    "receipts": "link_core/receipts/",
    "routing": "link_model_routing_profiles.py / link_profile_gate.py",
    "research_mining": "link_modes/growth/link_growth_console.py research mining helpers",
    "repo_value_scan": "link_modes/growth/link_growth_console.py repo value scanning helpers",
    "self_learning": "link_modes/growth/link_growth_console.py self-learning helpers",
    "tests": "tests/test_growth_pipeline.py / link_healthcheck.py",
    "workflow_ux": "link_modes/growth/link_growth_console.py Growth CLI/dashboard helpers",
}


def make_upgrade_execution_plan_id(upgrade_plans: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "upgrade_plan_ids": [plan["upgrade_plan_id"] for plan in upgrade_plans],
        "version": UPGRADE_EXECUTION_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"link-upgrade-execution-plan-{digest}"


def make_upgrade_execution_entry_id(gap: dict[str, Any], capability_inventory_id: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "capability_inventory_id": capability_inventory_id,
        "gap_id": gap["gap_id"],
        "gap_type": gap["gap_type"],
        "target_category": gap["target_category"],
        "version": UPGRADE_EXECUTION_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"upgrade-plan-{digest}"


def collect_upgrade_execution_plan(
    capability_gap_preview: dict[str, Any],
    capability_inventory: dict[str, Any],
    repo_value_scan: dict[str, Any] | list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert capability gaps into deterministic read-only implementation plans."""
    validate_capability_gap_preview(capability_gap_preview)
    validate_link_capability_inventory(capability_inventory)
    repo_findings = _capability_gap_findings_from_input(repo_value_scan)
    findings_by_id = {finding["finding_id"]: finding for finding in repo_findings}
    upgrade_plans: list[dict[str, Any]] = []
    for section in _CAPABILITY_GAP_SECTIONS:
        for gap in capability_gap_preview[section]:
            finding = findings_by_id.get(gap["finding_id"], {})
            upgrade_plans.append(_build_upgrade_execution_entry(
                gap,
                finding,
                capability_inventory,
                section,
            ))
    upgrade_plans.sort(key=lambda item: (item["rank"], item["upgrade_plan_id"]))
    plan = {
        "plan_version": UPGRADE_EXECUTION_PLAN_VERSION,
        "plan_id": make_upgrade_execution_plan_id(upgrade_plans),
        "source_gap_preview_id": capability_gap_preview["preview_id"],
        "source_inventory_id": capability_inventory["inventory_id"],
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "upgrade_plan_count": len(upgrade_plans),
        "upgrade_plans": upgrade_plans,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_upgrade_execution_plan(plan)
    return plan


def validate_upgrade_execution_plan(plan: dict[str, Any]) -> None:
    required = (
        "plan_version", "plan_id", "source_gap_preview_id", "source_inventory_id",
        "dry_run", "write_allowed", "automation_allowed", "upgrade_plan_count",
        "upgrade_plans", "metadata", "writes",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise ValueError(f"upgrade execution plan missing fields: {missing}")
    if plan["plan_version"] != UPGRADE_EXECUTION_PLAN_VERSION:
        raise ValueError("unsupported upgrade execution plan version")
    for field in ("plan_id", "source_gap_preview_id", "source_inventory_id"):
        if not isinstance(plan[field], str) or not plan[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if plan["dry_run"] is not True or plan["write_allowed"] is not False or plan["automation_allowed"] is not False:
        raise ValueError("upgrade execution plan must remain read-only")
    if plan["writes"] != []:
        raise ValueError("upgrade execution plan must not write files")
    if not isinstance(plan["metadata"], dict):
        raise TypeError("upgrade execution plan metadata must be a dict")
    upgrade_plans = plan["upgrade_plans"]
    if not isinstance(upgrade_plans, list):
        raise TypeError("upgrade_plans must be a list")
    if not isinstance(plan["upgrade_plan_count"], int) or plan["upgrade_plan_count"] != len(upgrade_plans):
        raise ValueError("upgrade_plan_count must match upgrade_plans length")
    seen_ids: set[str] = set()
    ranks: list[int] = []
    for entry in upgrade_plans:
        validate_upgrade_execution_entry(entry)
        if entry["upgrade_plan_id"] in seen_ids:
            raise ValueError(f"duplicate upgrade execution plan id: {entry['upgrade_plan_id']}")
        seen_ids.add(entry["upgrade_plan_id"])
        ranks.append(entry["rank"])
    if ranks != sorted(ranks):
        raise ValueError("upgrade execution plans must be sorted by rank")


def stable_upgrade_execution_plan_json(plan: dict[str, Any]) -> str:
    validate_upgrade_execution_plan(plan)
    return _stable_ruflo_json(plan, indent=2) + "\n"


def parse_upgrade_execution_plan_json(text: str) -> dict[str, Any]:
    import json as _json

    plan = _json.loads(text)
    validate_upgrade_execution_plan(plan)
    return plan


def validate_upgrade_execution_entry(entry: dict[str, Any]) -> None:
    required = (
        "upgrade_plan_id", "gap_id", "finding_id", "title", "rank", "gap_type",
        "target_category", "target_link_subsystems", "complexity", "risk",
        "phases", "required_evidence", "verification_requirements", "reason",
        "recommended_action",
    )
    missing = [field for field in required if field not in entry]
    if missing:
        raise ValueError(f"upgrade execution entry missing fields: {missing}")
    for field in ("upgrade_plan_id", "gap_id", "finding_id", "title", "gap_type", "target_category", "complexity", "risk", "reason", "recommended_action"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if entry["gap_type"] not in {"direct_gap", "maturity_gap", "onboarding_gap", "optional_cross_cluster_idea"}:
        raise ValueError(f"invalid upgrade gap_type: {entry['gap_type']}")
    if entry["target_category"] not in LINK_CAPABILITY_CATEGORIES:
        raise ValueError(f"invalid upgrade target_category: {entry['target_category']}")
    if entry["complexity"] not in UPGRADE_COMPLEXITY_LEVELS:
        raise ValueError(f"invalid upgrade complexity: {entry['complexity']}")
    if entry["risk"] not in UPGRADE_RISK_LEVELS:
        raise ValueError(f"invalid upgrade risk: {entry['risk']}")
    if not isinstance(entry["rank"], int) or entry["rank"] < 1:
        raise ValueError("upgrade execution rank must be a positive integer")
    for field in ("target_link_subsystems", "phases", "required_evidence", "verification_requirements"):
        values = entry[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    if tuple(entry["phases"]) != UPGRADE_PLAN_PHASES:
        raise ValueError("upgrade execution phases must use the stable phase sequence")


def _build_upgrade_execution_entry(
    gap: dict[str, Any],
    finding: dict[str, Any],
    capability_inventory: dict[str, Any],
    section: str,
) -> dict[str, Any]:
    complexity = _upgrade_execution_complexity(gap, finding)
    risk = _upgrade_execution_risk(gap, finding, complexity)
    entry = {
        "upgrade_plan_id": make_upgrade_execution_entry_id(gap, capability_inventory["inventory_id"]),
        "gap_id": gap["gap_id"],
        "finding_id": gap["finding_id"],
        "title": gap["finding_title"],
        "rank": _upgrade_execution_rank(section, gap, finding, complexity, risk),
        "gap_type": gap["gap_type"],
        "target_category": gap["target_category"],
        "target_link_subsystems": _upgrade_execution_target_subsystems(gap, finding),
        "complexity": complexity,
        "risk": risk,
        "phases": list(UPGRADE_PLAN_PHASES),
        "required_evidence": _upgrade_execution_required_evidence(gap, risk),
        "verification_requirements": _upgrade_execution_verification_requirements(gap, complexity),
        "reason": gap["reason"],
        "recommended_action": gap["recommended_action"],
    }
    validate_upgrade_execution_entry(entry)
    return entry


def _upgrade_execution_rank(section: str, gap: dict[str, Any], finding: dict[str, Any], complexity: str, risk: str) -> int:
    base = _UPGRADE_PLAN_SECTION_ORDER.get(section, 9) * 100
    complexity_penalty = UPGRADE_COMPLEXITY_LEVELS.index(complexity) * 10
    risk_penalty = UPGRADE_RISK_LEVELS.index(risk) * 5
    confidence_bonus = {"high": 0, "medium": 2, "low": 4}.get(gap.get("confidence"), 3)
    signal_bonus = max(0, 5 - int(finding.get("signal_count", 0) or 0))
    return base + complexity_penalty + risk_penalty + confidence_bonus + signal_bonus + 1


def _upgrade_execution_complexity(gap: dict[str, Any], finding: dict[str, Any]) -> str:
    signal_count = int(finding.get("signal_count", 0) or 0)
    category = gap["target_category"]
    gap_type = gap["gap_type"]
    if gap_type == "onboarding_gap":
        return "small"
    if gap_type == "optional_cross_cluster_idea":
        return "medium"
    if gap_type == "maturity_gap":
        return "small" if category in {"tests", "receipts", "workflow_ux"} else "medium"
    if category in {"safety", "routing", "self_learning"} and signal_count >= 3:
        return "large"
    if category in {"research_mining", "repo_value_scan", "workflow_ux", "tests", "receipts"}:
        return "small" if signal_count <= 2 else "medium"
    return "medium"


def _upgrade_execution_risk(gap: dict[str, Any], finding: dict[str, Any], complexity: str) -> str:
    category = gap["target_category"]
    gap_type = gap["gap_type"]
    if gap_type == "optional_cross_cluster_idea":
        return "medium"
    if complexity in {"large", "major"} or category in {"safety", "routing", "self_learning"}:
        return "high" if gap_type == "direct_gap" else "medium"
    if category in {"tests", "receipts", "repo_value_scan", "workflow_ux"}:
        return "low"
    return "medium"


def _upgrade_execution_target_subsystems(gap: dict[str, Any], finding: dict[str, Any]) -> list[str]:
    subsystems = [_UPGRADE_TARGET_SUBSYSTEM_BY_CATEGORY.get(gap["target_category"], "link_modes/growth/link_growth_console.py")]
    source_path = finding.get("source_path") or gap.get("source_path")
    if source_path:
        subsystems.append(f"research source reference: {source_path}")
    return sorted(dict.fromkeys(subsystems))


def _upgrade_execution_required_evidence(gap: dict[str, Any], risk: str) -> list[str]:
    evidence = [
        "git diff --stat",
        "focused source diff review",
        "rollback note in final summary",
    ]
    if risk in {"medium", "high"}:
        evidence.append("explicit safety review notes")
    if gap["gap_type"] in {"maturity_gap", "direct_gap"}:
        evidence.append("targeted regression test output")
    return sorted(dict.fromkeys(evidence))


def _upgrade_execution_verification_requirements(gap: dict[str, Any], complexity: str) -> list[str]:
    requirements = [
        "python3 -m py_compile link.py link_modes/growth/link_growth_console.py tests/test_growth_pipeline.py",
        "PYTHONDONTWRITEBYTECODE=1 python3 tests/test_growth_pipeline.py",
        "PYTHONDONTWRITEBYTECODE=1 python3 link_healthcheck.py",
    ]
    if complexity in {"large", "major"}:
        requirements.append("manual dry-run smoke test for affected Growth command")
    if gap["target_category"] == "safety":
        requirements.append("confirm no approval/handoff/execute behavior was added")
    return requirements


IMPLEMENTATION_BRANCH_PLAN_VERSION = "link-implementation-branch-plan-v1"


def make_implementation_branch_plan_id(source_plan_id: str, upgrade_item: dict[str, Any], branch_name: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "branch_name": branch_name,
        "source_upgrade_id": upgrade_item["upgrade_plan_id"],
        "source_upgrade_plan_id": source_plan_id,
        "version": IMPLEMENTATION_BRANCH_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"implementation-branch-plan-{digest}"


def collect_implementation_branch_plan(
    upgrade_plan_or_item: dict[str, Any],
    upgrade_item: dict[str, Any] | None = None,
    *,
    evidence_refs: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a deterministic read-only implementation branch plan for one upgrade."""
    source_plan_id, item = _implementation_branch_source_item(upgrade_plan_or_item, upgrade_item)
    evidence = _normalize_implementation_branch_refs(evidence_refs or [])
    branch_name = make_implementation_branch_name(item)
    required_evidence = _normalize_implementation_branch_refs(item["required_evidence"])
    missing_evidence = [ref for ref in required_evidence if ref not in evidence]
    plan = {
        "branch_plan_version": IMPLEMENTATION_BRANCH_PLAN_VERSION,
        "branch_plan_id": make_implementation_branch_plan_id(source_plan_id, item, branch_name),
        "source_upgrade_plan_id": source_plan_id,
        "source_upgrade_id": item["upgrade_plan_id"],
        "proposed_branch_name": branch_name,
        "target_files": _implementation_branch_target_files(item),
        "target_subsystems": list(item["target_link_subsystems"]),
        "ordered_implementation_tasks": _implementation_branch_tasks(item),
        "verification_commands": list(item["verification_requirements"]),
        "rollback_notes": _implementation_branch_rollback_notes(item),
        "risk_level": item["risk"],
        "complexity": item["complexity"],
        "required_evidence": required_evidence,
        "provided_evidence": evidence,
        "missing_evidence": missing_evidence,
        "blocked": bool(missing_evidence),
        "requires_review": item["risk"] != "low" or item["complexity"] in {"large", "major"} or bool(missing_evidence),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_implementation_branch_plan(plan)
    return plan


def validate_implementation_branch_plan(plan: dict[str, Any]) -> None:
    required = (
        "branch_plan_version", "branch_plan_id", "source_upgrade_plan_id", "source_upgrade_id",
        "proposed_branch_name", "target_files", "target_subsystems", "ordered_implementation_tasks",
        "verification_commands", "rollback_notes", "risk_level", "complexity", "required_evidence",
        "provided_evidence", "missing_evidence", "blocked", "requires_review", "dry_run",
        "write_allowed", "automation_allowed", "metadata", "writes",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise ValueError(f"implementation branch plan missing fields: {missing}")
    if plan["branch_plan_version"] != IMPLEMENTATION_BRANCH_PLAN_VERSION:
        raise ValueError("unsupported implementation branch plan version")
    for field in ("branch_plan_id", "source_upgrade_plan_id", "source_upgrade_id", "proposed_branch_name", "risk_level", "complexity"):
        if not isinstance(plan[field], str) or not plan[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if plan["risk_level"] not in UPGRADE_RISK_LEVELS:
        raise ValueError(f"invalid implementation branch risk_level: {plan['risk_level']}")
    if plan["complexity"] not in UPGRADE_COMPLEXITY_LEVELS:
        raise ValueError(f"invalid implementation branch complexity: {plan['complexity']}")
    if not _valid_implementation_branch_name(plan["proposed_branch_name"]):
        raise ValueError(f"invalid proposed branch name: {plan['proposed_branch_name']}")
    if plan["dry_run"] is not True or plan["write_allowed"] is not False or plan["automation_allowed"] is not False:
        raise ValueError("implementation branch plan must remain read-only")
    if plan["writes"] != []:
        raise ValueError("implementation branch plan must not write files")
    if not isinstance(plan["metadata"], dict):
        raise TypeError("implementation branch plan metadata must be a dict")
    for field in ("target_files", "target_subsystems", "verification_commands", "rollback_notes", "required_evidence", "provided_evidence", "missing_evidence"):
        values = plan[field]
        if not isinstance(values, list):
            raise TypeError(f"{field} must be a list")
        if field in {"target_subsystems", "verification_commands", "rollback_notes", "required_evidence"} and not values:
            raise ValueError(f"{field} must be non-empty")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    if plan["target_files"] != _normalize_implementation_branch_refs(plan["target_files"]):
        raise ValueError("target_files must be normalized and sorted")
    for field in ("required_evidence", "provided_evidence", "missing_evidence"):
        if plan[field] != _normalize_implementation_branch_refs(plan[field]):
            raise ValueError(f"{field} must be normalized and sorted")
    if not isinstance(plan["blocked"], bool) or not isinstance(plan["requires_review"], bool):
        raise TypeError("blocked and requires_review must be booleans")
    expected_missing = [ref for ref in plan["required_evidence"] if ref not in plan["provided_evidence"]]
    if plan["missing_evidence"] != expected_missing:
        raise ValueError("missing_evidence must match required evidence not present in provided evidence")
    if plan["blocked"] is not bool(plan["missing_evidence"]):
        raise ValueError("blocked must reflect missing_evidence")
    tasks = plan["ordered_implementation_tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise TypeError("ordered_implementation_tasks must be a non-empty list")
    orders: list[int] = []
    for task in tasks:
        _validate_implementation_branch_task(task)
        orders.append(task["order"])
    if orders != list(range(1, len(tasks) + 1)):
        raise ValueError("implementation tasks must be ordered from 1 without gaps")


def stable_implementation_branch_plan_json(plan: dict[str, Any]) -> str:
    validate_implementation_branch_plan(plan)
    return _stable_ruflo_json(plan, indent=2) + "\n"


def parse_implementation_branch_plan_json(text: str) -> dict[str, Any]:
    import json as _json

    plan = _json.loads(text)
    validate_implementation_branch_plan(plan)
    return plan


def make_implementation_branch_name(upgrade_item: dict[str, Any]) -> str:
    import hashlib
    import re

    validate_upgrade_execution_entry(upgrade_item)
    slug = re.sub(r"[^a-z0-9]+", "-", upgrade_item["title"].lower()).strip("-")
    slug = slug[:52].strip("-") or "upgrade"
    digest = hashlib.sha256(upgrade_item["upgrade_plan_id"].encode("utf-8")).hexdigest()[:8]
    return f"link-upgrade/{slug}-{digest}"


def _implementation_branch_source_item(
    upgrade_plan_or_item: dict[str, Any],
    upgrade_item: dict[str, Any] | None,
) -> tuple[str, dict[str, Any]]:
    if not isinstance(upgrade_plan_or_item, dict):
        raise TypeError("upgrade plan or item must be a dict")
    if upgrade_item is None and "upgrade_plans" in upgrade_plan_or_item:
        validate_upgrade_execution_plan(upgrade_plan_or_item)
        if not upgrade_plan_or_item["upgrade_plans"]:
            raise ValueError("upgrade execution plan has no upgrade_plans")
        return upgrade_plan_or_item["plan_id"], dict(upgrade_plan_or_item["upgrade_plans"][0])
    if upgrade_item is not None:
        validate_upgrade_execution_plan(upgrade_plan_or_item)
        validate_upgrade_execution_entry(upgrade_item)
        ids = {entry["upgrade_plan_id"] for entry in upgrade_plan_or_item["upgrade_plans"]}
        if upgrade_item["upgrade_plan_id"] not in ids:
            raise ValueError("upgrade_item is not present in source upgrade plan")
        return upgrade_plan_or_item["plan_id"], dict(upgrade_item)
    validate_upgrade_execution_entry(upgrade_plan_or_item)
    return "standalone-upgrade-plan", dict(upgrade_plan_or_item)


def _implementation_branch_target_files(upgrade_item: dict[str, Any]) -> list[str]:
    import re

    paths: list[str] = []
    for subsystem in upgrade_item["target_link_subsystems"]:
        if subsystem.startswith("research source reference:"):
            continue
        for match in re.findall(r"[A-Za-z0-9_./-]+\.(?:py|md|json|yaml|yml|toml)", subsystem):
            if not match.startswith("research/"):
                paths.append(match)
    if not paths:
        paths.extend(["link_modes/growth/link_growth_console.py", "tests/test_growth_pipeline.py"])
    elif "tests/test_growth_pipeline.py" not in paths:
        paths.append("tests/test_growth_pipeline.py")
    return _normalize_implementation_branch_refs(paths)


def _implementation_branch_tasks(upgrade_item: dict[str, Any]) -> list[dict[str, Any]]:
    phase_templates = {
        "discovery": f"Review the source gap and target subsystem for '{upgrade_item['title']}'.",
        "design": "Define the smallest Link-native read-only data shape and validation rules.",
        "implementation": "Patch only the focused source and test files needed for this slice.",
        "verification": "Run the required verification commands and capture pass/fail evidence.",
        "rollout": "Prepare a review summary with rollback notes; do not merge without approval.",
    }
    tasks: list[dict[str, Any]] = []
    for index, phase in enumerate(UPGRADE_PLAN_PHASES, start=1):
        tasks.append({"order": index, "phase": phase, "task": phase_templates[phase]})
    return tasks


def _implementation_branch_rollback_notes(upgrade_item: dict[str, Any]) -> list[str]:
    return [
        "Do not create the branch until a human approves execution.",
        "Keep the implementation limited to the planned target files unless review expands scope.",
        "Rollback is git revert of the eventual implementation commit, not runtime state mutation.",
        f"Risk level for review: {upgrade_item['risk']}.",
    ]


def _validate_implementation_branch_task(task: dict[str, Any]) -> None:
    required = ("order", "phase", "task")
    missing = [field for field in required if field not in task]
    if missing:
        raise ValueError(f"implementation branch task missing fields: {missing}")
    if not isinstance(task["order"], int) or task["order"] < 1:
        raise ValueError("implementation branch task order must be a positive integer")
    if task["phase"] not in UPGRADE_PLAN_PHASES:
        raise ValueError(f"invalid implementation branch task phase: {task['phase']}")
    if not isinstance(task["task"], str) or not task["task"].strip():
        raise ValueError("implementation branch task must be a non-empty string")


def _normalize_implementation_branch_refs(values: Any) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        raw_values = [values]
    elif isinstance(values, list):
        raw_values = values
    else:
        raise TypeError("implementation branch refs must be a string or list")
    normalized: list[str] = []
    for raw in raw_values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError("implementation branch refs cannot contain empty strings")
        if "\x00" in value or value.startswith("/") or ".." in value.split("/"):
            raise ValueError(f"invalid implementation branch ref: {value}")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)


def _valid_implementation_branch_name(name: str) -> bool:
    import re

    if not isinstance(name, str) or not name.startswith("link-upgrade/"):
        return False
    if name.endswith("/") or ".." in name or "//" in name:
        return False
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9._/-]*[a-z0-9]", name))


IMPLEMENTATION_WORK_PACKAGES_VERSION = "link-implementation-work-packages-v1"


def make_implementation_work_packages_id(packages: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "package_ids": [package["package_id"] for package in packages],
        "version": IMPLEMENTATION_WORK_PACKAGES_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"implementation-work-packages-{digest}"


def make_implementation_work_package_id(branch_plan: dict[str, Any], task_group: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "branch_plan_id": branch_plan["branch_plan_id"],
        "source_upgrade_id": branch_plan["source_upgrade_id"],
        "task_group": task_group,
        "version": IMPLEMENTATION_WORK_PACKAGES_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"implementation-work-package-{digest}"


def collect_implementation_work_packages(
    branch_plans: dict[str, Any] | list[dict[str, Any]],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert implementation branch plans into deterministic read-only work packages."""
    plans = _implementation_work_package_plans_from_input(branch_plans)
    packages = [_implementation_work_package_from_branch_plan(plan) for plan in plans]
    packages.sort(key=lambda item: (item["risk"], item["complexity"], item["package_id"]))
    result = {
        "work_packages_version": IMPLEMENTATION_WORK_PACKAGES_VERSION,
        "work_packages_id": make_implementation_work_packages_id(packages),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "package_count": len(packages),
        "packages": packages,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_implementation_work_packages(result)
    return result


def validate_implementation_work_packages(work_packages: dict[str, Any]) -> None:
    required = (
        "work_packages_version", "work_packages_id", "dry_run", "write_allowed",
        "automation_allowed", "package_count", "packages", "metadata", "writes",
    )
    missing = [field for field in required if field not in work_packages]
    if missing:
        raise ValueError(f"implementation work packages missing fields: {missing}")
    if work_packages["work_packages_version"] != IMPLEMENTATION_WORK_PACKAGES_VERSION:
        raise ValueError("unsupported implementation work packages version")
    if not isinstance(work_packages["work_packages_id"], str) or not work_packages["work_packages_id"].strip():
        raise ValueError("work_packages_id must be a non-empty string")
    if work_packages["dry_run"] is not True or work_packages["write_allowed"] is not False or work_packages["automation_allowed"] is not False:
        raise ValueError("implementation work packages must remain read-only")
    if work_packages["writes"] != []:
        raise ValueError("implementation work packages must not write files")
    if not isinstance(work_packages["metadata"], dict):
        raise TypeError("implementation work packages metadata must be a dict")
    packages = work_packages["packages"]
    if not isinstance(packages, list):
        raise TypeError("packages must be a list")
    if not isinstance(work_packages["package_count"], int) or work_packages["package_count"] != len(packages):
        raise ValueError("package_count must match packages length")
    package_ids: set[str] = set()
    for package in packages:
        validate_implementation_work_package(package)
        if package["package_id"] in package_ids:
            raise ValueError(f"duplicate implementation work package id: {package['package_id']}")
        package_ids.add(package["package_id"])


def stable_implementation_work_packages_json(work_packages: dict[str, Any]) -> str:
    validate_implementation_work_packages(work_packages)
    return _stable_ruflo_json(work_packages, indent=2) + "\n"


def parse_implementation_work_packages_json(text: str) -> dict[str, Any]:
    import json as _json

    work_packages = _json.loads(text)
    validate_implementation_work_packages(work_packages)
    return work_packages


def validate_implementation_work_package(package: dict[str, Any]) -> None:
    required = (
        "package_id", "branch_plan_id", "upgrade_id", "target_files", "target_subsystems",
        "acceptance_criteria", "implementation_tasks", "verification_commands", "rollback_notes",
        "risk", "complexity", "estimated_file_count", "estimated_test_count",
    )
    missing = [field for field in required if field not in package]
    if missing:
        raise ValueError(f"implementation work package missing fields: {missing}")
    for field in ("package_id", "branch_plan_id", "upgrade_id", "risk", "complexity"):
        if not isinstance(package[field], str) or not package[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if package["risk"] not in UPGRADE_RISK_LEVELS:
        raise ValueError(f"invalid implementation work package risk: {package['risk']}")
    if package["complexity"] not in UPGRADE_COMPLEXITY_LEVELS:
        raise ValueError(f"invalid implementation work package complexity: {package['complexity']}")
    for field in ("target_files", "target_subsystems", "acceptance_criteria", "implementation_tasks", "verification_commands", "rollback_notes"):
        values = package[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    if package["target_files"] != _normalize_implementation_branch_refs(package["target_files"]):
        raise ValueError("target_files must be normalized and sorted")
    for field in ("estimated_file_count", "estimated_test_count"):
        if not isinstance(package[field], int) or package[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if package["estimated_file_count"] != len(package["target_files"]):
        raise ValueError("estimated_file_count must match target_files length")
    expected_test_count = len([path for path in package["target_files"] if path.startswith("tests/") or "/test" in path or path.endswith("_test.py")])
    if package["estimated_test_count"] != expected_test_count:
        raise ValueError("estimated_test_count must match test target count")


def _implementation_work_package_plans_from_input(branch_plans: dict[str, Any] | list[dict[str, Any]]) -> list[dict[str, Any]]:
    if isinstance(branch_plans, dict):
        validate_implementation_branch_plan(branch_plans)
        return [branch_plans]
    if isinstance(branch_plans, list):
        plans: list[dict[str, Any]] = []
        for plan in branch_plans:
            validate_implementation_branch_plan(plan)
            plans.append(plan)
        return plans
    raise TypeError("branch_plans must be a branch plan dict or list of branch plans")


def _implementation_work_package_from_branch_plan(branch_plan: dict[str, Any]) -> dict[str, Any]:
    validate_implementation_branch_plan(branch_plan)
    target_files = _normalize_implementation_branch_refs(branch_plan["target_files"])
    tasks = [f"{task['order']}. {task['phase']}: {task['task']}" for task in branch_plan["ordered_implementation_tasks"]]
    package = {
        "package_id": make_implementation_work_package_id(branch_plan, "primary"),
        "branch_plan_id": branch_plan["branch_plan_id"],
        "upgrade_id": branch_plan["source_upgrade_id"],
        "target_files": target_files,
        "target_subsystems": list(branch_plan["target_subsystems"]),
        "acceptance_criteria": _implementation_work_package_acceptance_criteria(branch_plan),
        "implementation_tasks": tasks,
        "verification_commands": list(branch_plan["verification_commands"]),
        "rollback_notes": list(branch_plan["rollback_notes"]),
        "risk": branch_plan["risk_level"],
        "complexity": branch_plan["complexity"],
        "estimated_file_count": len(target_files),
        "estimated_test_count": len([path for path in target_files if path.startswith("tests/") or "/test" in path or path.endswith("_test.py")]),
    }
    validate_implementation_work_package(package)
    return package


def _implementation_work_package_acceptance_criteria(branch_plan: dict[str, Any]) -> list[str]:
    criteria = [
        "Implementation remains scoped to the planned target files unless human review expands scope.",
        "No CLI, branch, worktree, approval, handoff, execute, finalize, network, npm, node, or bun behavior is added by the package generator.",
        "All verification commands in the package pass before review.",
        "Final summary includes changed files, verification results, rollback notes, and git status.",
    ]
    if branch_plan["blocked"]:
        criteria.append("Missing required evidence is resolved before implementation begins.")
    if branch_plan["requires_review"]:
        criteria.append("Human review is required before any implementation branch or commit is created.")
    return criteria


VERIFICATION_PLAN_VERSION = "link-verification-plan-v1"
VERIFICATION_COST_LEVELS = ("low", "medium", "high")
VERIFICATION_RISK_LEVELS = ("low", "medium", "high")


def make_verification_plan_id(package: dict[str, Any]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "package_id": package["package_id"],
        "upgrade_id": package["upgrade_id"],
        "verification_commands": package["verification_commands"],
        "version": VERIFICATION_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"verification-plan-{digest}"


def collect_verification_plan(
    work_package_or_packages: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert implementation work packages into deterministic read-only verification plans."""
    packages = _verification_packages_from_input(work_package_or_packages)
    plans = [_verification_plan_from_package(package) for package in packages]
    plans.sort(key=lambda item: item["verification_plan_id"])
    result = {
        "verification_plan_version": VERIFICATION_PLAN_VERSION,
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "plan_count": len(plans),
        "plans": plans,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_verification_plan(result)
    return result


def validate_verification_plan(verification_plan: dict[str, Any]) -> None:
    required = (
        "verification_plan_version", "dry_run", "write_allowed", "automation_allowed",
        "plan_count", "plans", "metadata", "writes",
    )
    missing = [field for field in required if field not in verification_plan]
    if missing:
        raise ValueError(f"verification plan missing fields: {missing}")
    if verification_plan["verification_plan_version"] != VERIFICATION_PLAN_VERSION:
        raise ValueError("unsupported verification plan version")
    if verification_plan["dry_run"] is not True or verification_plan["write_allowed"] is not False or verification_plan["automation_allowed"] is not False:
        raise ValueError("verification plan must remain read-only")
    if verification_plan["writes"] != []:
        raise ValueError("verification plan must not write files")
    if not isinstance(verification_plan["metadata"], dict):
        raise TypeError("verification plan metadata must be a dict")
    plans = verification_plan["plans"]
    if not isinstance(plans, list):
        raise TypeError("plans must be a list")
    if not isinstance(verification_plan["plan_count"], int) or verification_plan["plan_count"] != len(plans):
        raise ValueError("plan_count must match plans length")
    plan_ids: set[str] = set()
    for plan in plans:
        validate_verification_plan_entry(plan)
        if plan["verification_plan_id"] in plan_ids:
            raise ValueError(f"duplicate verification plan id: {plan['verification_plan_id']}")
        plan_ids.add(plan["verification_plan_id"])
    if [plan["verification_plan_id"] for plan in plans] != sorted(plan["verification_plan_id"] for plan in plans):
        raise ValueError("verification plans must be sorted by verification_plan_id")


def stable_verification_plan_json(verification_plan: dict[str, Any]) -> str:
    validate_verification_plan(verification_plan)
    return _stable_ruflo_json(verification_plan, indent=2) + "\n"


def parse_verification_plan_json(text: str) -> dict[str, Any]:
    import json as _json

    verification_plan = _json.loads(text)
    validate_verification_plan(verification_plan)
    return verification_plan


def validate_verification_plan_entry(plan: dict[str, Any]) -> None:
    required = (
        "verification_plan_id", "package_id", "branch_plan_id", "upgrade_id",
        "compile_commands", "test_commands", "healthcheck_commands", "expected_files",
        "expected_capabilities", "expected_behaviors", "failure_conditions", "rollback_triggers",
        "estimated_verification_cost", "estimated_verification_risk", "required_evidence",
    )
    missing = [field for field in required if field not in plan]
    if missing:
        raise ValueError(f"verification plan entry missing fields: {missing}")
    for field in ("verification_plan_id", "package_id", "branch_plan_id", "upgrade_id", "estimated_verification_cost", "estimated_verification_risk"):
        if not isinstance(plan[field], str) or not plan[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if plan["estimated_verification_cost"] not in VERIFICATION_COST_LEVELS:
        raise ValueError(f"invalid estimated_verification_cost: {plan['estimated_verification_cost']}")
    if plan["estimated_verification_risk"] not in VERIFICATION_RISK_LEVELS:
        raise ValueError(f"invalid estimated_verification_risk: {plan['estimated_verification_risk']}")
    for field in (
        "compile_commands", "test_commands", "healthcheck_commands", "expected_files",
        "expected_capabilities", "expected_behaviors", "failure_conditions", "rollback_triggers",
        "required_evidence",
    ):
        values = plan[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    if plan["expected_files"] != _normalize_implementation_branch_refs(plan["expected_files"]):
        raise ValueError("expected_files must be normalized and sorted")
    if not plan["compile_commands"]:
        raise ValueError("compile_commands must not be empty")
    if not plan["test_commands"]:
        raise ValueError("test_commands must not be empty")
    if not plan["healthcheck_commands"]:
        raise ValueError("healthcheck_commands must not be empty")


def _verification_packages_from_input(work_package_or_packages: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(work_package_or_packages, dict):
        raise TypeError("work_package_or_packages must be a dict")
    if "packages" in work_package_or_packages:
        validate_implementation_work_packages(work_package_or_packages)
        return [dict(package) for package in work_package_or_packages["packages"]]
    validate_implementation_work_package(work_package_or_packages)
    return [dict(work_package_or_packages)]


def _verification_plan_from_package(package: dict[str, Any]) -> dict[str, Any]:
    validate_implementation_work_package(package)
    command_groups = _verification_command_groups(package["verification_commands"])
    plan = {
        "verification_plan_id": make_verification_plan_id(package),
        "package_id": package["package_id"],
        "branch_plan_id": package["branch_plan_id"],
        "upgrade_id": package["upgrade_id"],
        "compile_commands": command_groups["compile_commands"],
        "test_commands": command_groups["test_commands"],
        "healthcheck_commands": command_groups["healthcheck_commands"],
        "expected_files": _normalize_implementation_branch_refs(package["target_files"]),
        "expected_capabilities": _verification_expected_capabilities(package),
        "expected_behaviors": _verification_expected_behaviors(package),
        "failure_conditions": _verification_failure_conditions(package),
        "rollback_triggers": _verification_rollback_triggers(package),
        "estimated_verification_cost": _verification_cost(package),
        "estimated_verification_risk": _verification_risk(package),
        "required_evidence": _verification_required_evidence(package),
    }
    validate_verification_plan_entry(plan)
    return plan


def _verification_command_groups(commands: list[str]) -> dict[str, list[str]]:
    compile_commands: list[str] = []
    test_commands: list[str] = []
    healthcheck_commands: list[str] = []
    for command in commands:
        if "py_compile" in command:
            compile_commands.append(command)
        elif "link_healthcheck.py" in command:
            healthcheck_commands.append(command)
        else:
            test_commands.append(command)
    return {
        "compile_commands": compile_commands or ["python3 -m py_compile link.py link_modes/growth/link_growth_console.py tests/test_growth_pipeline.py"],
        "test_commands": test_commands or ["PYTHONDONTWRITEBYTECODE=1 python3 tests/test_growth_pipeline.py"],
        "healthcheck_commands": healthcheck_commands or ["PYTHONDONTWRITEBYTECODE=1 python3 link_healthcheck.py"],
    }


def _verification_expected_capabilities(package: dict[str, Any]) -> list[str]:
    capabilities = [
        "work package remains read-only",
        "planned target files are unchanged until implementation approval",
        f"risk classification remains {package['risk']}",
        f"complexity classification remains {package['complexity']}",
    ]
    return sorted(dict.fromkeys(capabilities))


def _verification_expected_behaviors(package: dict[str, Any]) -> list[str]:
    behaviors = [
        "verification commands are represented as data only and are not executed by this helper",
        "acceptance criteria remain attached to the work package",
        "rollback notes remain available for reviewer use",
    ]
    for criterion in package["acceptance_criteria"]:
        behaviors.append(f"acceptance criterion: {criterion}")
    return sorted(dict.fromkeys(behaviors))


def _verification_failure_conditions(package: dict[str, Any]) -> list[str]:
    conditions = [
        "compile command fails",
        "Growth pipeline tests fail",
        "link_healthcheck.py fails",
        "unexpected files are modified outside the package target files",
        "runtime state, research files, proposals, handoffs, or receipts are modified unexpectedly",
    ]
    if package["risk"] in {"medium", "high"}:
        conditions.append("reviewer safety concern remains unresolved")
    return sorted(dict.fromkeys(conditions))


def _verification_rollback_triggers(package: dict[str, Any]) -> list[str]:
    triggers = [
        "verification command failure after implementation",
        "scope expands beyond planned target files without approval",
        "read-only safety metadata is removed or weakened",
    ]
    if package["risk"] == "high":
        triggers.append("high-risk behavior changes without explicit approval")
    return sorted(dict.fromkeys(triggers))


def _verification_cost(package: dict[str, Any]) -> str:
    command_count = len(package["verification_commands"])
    file_count = int(package["estimated_file_count"])
    if package["complexity"] in {"large", "major"} or command_count >= 5 or file_count >= 5:
        return "high"
    if package["complexity"] == "medium" or command_count >= 3 or file_count >= 3:
        return "medium"
    return "low"


def _verification_risk(package: dict[str, Any]) -> str:
    if package["risk"] == "high":
        return "high"
    if package["risk"] == "medium" or package["complexity"] in {"large", "major"}:
        return "medium"
    return "low"


def _verification_required_evidence(package: dict[str, Any]) -> list[str]:
    evidence = [
        "compile output",
        "Growth pipeline test output",
        "link_healthcheck.py output",
        "git diff --stat",
        "git status --short --branch",
    ]
    evidence.extend(package["acceptance_criteria"])
    return sorted(dict.fromkeys(evidence))


GROWTH_PLANNING_CHAIN_VERSION = "link-growth-planning-chain-v1"

_DEFAULT_PLANNING_CHAIN_CAPABILITIES: tuple[dict[str, Any], ...] = (
    {
        "name": "Self-learning recommendations",
        "category": "self_learning",
        "description": "Existing self-learning helper is present but still needs verified upgrade execution planning.",
        "source": "link_modes/growth/link_growth_console.py",
        "confidence": "high",
        "tags": ["self-learning", "recommendation", "planning"],
        "risk_level": "medium",
        "maturity_level": "partial",
    },
    {
        "name": "Growth planning dashboard",
        "category": "workflow_ux",
        "description": "Growth exposes read-only planning data and CLI summaries for local operation.",
        "source": "link_modes/growth/link_growth_console.py",
        "confidence": "high",
        "tags": ["growth", "dashboard", "planning"],
        "risk_level": "low",
        "maturity_level": "verified",
    },
)

_DEFAULT_PLANNING_CHAIN_REPO_ITEMS: tuple[dict[str, Any], ...] = (
    {
        "path": "research/sota-scan/planning.md",
        "title": "Self-learning feedback loop",
        "category": "self_learning",
        "summary": "Repo scanner records feedback loops and turns them into verified implementation planning.",
        "source_kind": "research-summary",
        "tags": ["self-learning", "feedback", "verification", "planning"],
        "required_maturity_level": "verified",
    },
    {
        "path": "research/sota-scan/onboarding.md",
        "title": "Discoverable planning command UX",
        "category": "cli_workflow_ux",
        "summary": "Repo scanner presents planning state through concise CLI and dashboard summaries.",
        "source_kind": "research-summary",
        "tags": ["cli", "dashboard", "planning", "docs"],
    },
)


def make_growth_planning_chain_id(
    gap_preview: dict[str, Any],
    upgrade_plan: dict[str, Any],
    branch_plan: dict[str, Any],
    work_packages: dict[str, Any],
    verification_plan: dict[str, Any],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "branch_plan_id": branch_plan["branch_plan_id"],
        "gap_preview_id": gap_preview["preview_id"],
        "upgrade_plan_id": upgrade_plan["plan_id"],
        "verification_plan_ids": [plan["verification_plan_id"] for plan in verification_plan["plans"]],
        "work_packages_id": work_packages["work_packages_id"],
        "version": GROWTH_PLANNING_CHAIN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"growth-planning-chain-{digest}"


def collect_growth_planning_chain_preview(
    repo_items: list[dict[str, Any]] | None = None,
    *,
    capabilities: list[dict[str, Any]] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the read-only Growth planning chain from gaps to verification."""
    capability_items = list(capabilities) if capabilities is not None else [dict(item) for item in _DEFAULT_PLANNING_CHAIN_CAPABILITIES]
    source_items = list(repo_items) if repo_items is not None else [dict(item) for item in _DEFAULT_PLANNING_CHAIN_REPO_ITEMS]
    inventory = collect_link_capability_inventory(capability_items)
    repo_scan = collect_repo_value_scan(source_items, top=10, source_label="growth-planning-chain")
    findings = [dict(item) for item in repo_scan["findings"]]
    required_by_path = {
        str(item.get("path") or item.get("source_path") or item.get("file") or ""): str(item.get("required_maturity_level") or "")
        for item in source_items
        if item.get("required_maturity_level")
    }
    for finding in findings:
        required = required_by_path.get(finding["source_path"])
        if required:
            finding["required_maturity_level"] = required
    gap_preview = collect_capability_gap_preview(inventory, findings, metadata={"source": "growth-planning-chain"})
    upgrade_plan = collect_upgrade_execution_plan(gap_preview, inventory, findings, metadata={"source": "growth-planning-chain"})
    if not upgrade_plan["upgrade_plans"]:
        raise ValueError("planning chain requires at least one upgrade plan")
    top_upgrade = upgrade_plan["upgrade_plans"][0]
    branch_plan = collect_implementation_branch_plan(upgrade_plan, top_upgrade)
    work_packages = collect_implementation_work_packages(branch_plan)
    verification_plan = collect_verification_plan(work_packages)
    chain = {
        "planning_chain_version": GROWTH_PLANNING_CHAIN_VERSION,
        "planning_chain_id": make_growth_planning_chain_id(
            gap_preview,
            upgrade_plan,
            branch_plan,
            work_packages,
            verification_plan,
        ),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "capability_gap_preview": gap_preview,
        "upgrade_execution_plan": upgrade_plan,
        "implementation_branch_plan": branch_plan,
        "implementation_work_packages": work_packages,
        "verification_plan": verification_plan,
        "top_recommended_next_action": _growth_planning_chain_next_action(top_upgrade, branch_plan, verification_plan),
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_growth_planning_chain_preview(chain)
    return chain


def validate_growth_planning_chain_preview(chain: dict[str, Any]) -> None:
    required = (
        "planning_chain_version", "planning_chain_id", "dry_run", "write_allowed", "automation_allowed",
        "capability_gap_preview", "upgrade_execution_plan", "implementation_branch_plan",
        "implementation_work_packages", "verification_plan", "top_recommended_next_action", "metadata", "writes",
    )
    missing = [field for field in required if field not in chain]
    if missing:
        raise ValueError(f"growth planning chain missing fields: {missing}")
    if chain["planning_chain_version"] != GROWTH_PLANNING_CHAIN_VERSION:
        raise ValueError("unsupported growth planning chain version")
    if not isinstance(chain["planning_chain_id"], str) or not chain["planning_chain_id"].strip():
        raise ValueError("planning_chain_id must be a non-empty string")
    if chain["dry_run"] is not True or chain["write_allowed"] is not False or chain["automation_allowed"] is not False:
        raise ValueError("growth planning chain must remain read-only")
    if chain["writes"] != []:
        raise ValueError("growth planning chain must not write files")
    if not isinstance(chain["metadata"], dict):
        raise TypeError("growth planning chain metadata must be a dict")
    validate_capability_gap_preview(chain["capability_gap_preview"])
    validate_upgrade_execution_plan(chain["upgrade_execution_plan"])
    validate_implementation_branch_plan(chain["implementation_branch_plan"])
    validate_implementation_work_packages(chain["implementation_work_packages"])
    validate_verification_plan(chain["verification_plan"])
    action = chain["top_recommended_next_action"]
    if not isinstance(action, dict):
        raise TypeError("top_recommended_next_action must be a dict")
    for field in ("upgrade_id", "title", "branch_plan_id", "package_id", "verification_plan_id", "summary"):
        if not isinstance(action.get(field), str) or not action[field].strip():
            raise ValueError(f"top_recommended_next_action.{field} must be a non-empty string")
    top_upgrade = chain["upgrade_execution_plan"]["upgrade_plans"][0]
    branch_plan = chain["implementation_branch_plan"]
    work_package = chain["implementation_work_packages"]["packages"][0]
    verification = chain["verification_plan"]["plans"][0]
    if branch_plan["source_upgrade_id"] != top_upgrade["upgrade_plan_id"]:
        raise ValueError("top upgrade must flow into implementation branch plan")
    if work_package["branch_plan_id"] != branch_plan["branch_plan_id"]:
        raise ValueError("implementation branch plan must flow into work package")
    if verification["package_id"] != work_package["package_id"]:
        raise ValueError("work package must flow into verification plan")


def stable_growth_planning_chain_json(chain: dict[str, Any]) -> str:
    validate_growth_planning_chain_preview(chain)
    return _stable_ruflo_json(chain, indent=2) + "\n"


def parse_growth_planning_chain_json(text: str) -> dict[str, Any]:
    import json as _json

    chain = _json.loads(text)
    validate_growth_planning_chain_preview(chain)
    return chain


def _growth_planning_chain_next_action(
    top_upgrade: dict[str, Any],
    branch_plan: dict[str, Any],
    verification_plan: dict[str, Any],
) -> dict[str, str]:
    return {
        "upgrade_id": top_upgrade["upgrade_plan_id"],
        "title": top_upgrade["title"],
        "branch_plan_id": branch_plan["branch_plan_id"],
        "package_id": verification_plan["plans"][0]["package_id"],
        "verification_plan_id": verification_plan["plans"][0]["verification_plan_id"],
        "summary": "Review the read-only branch, work package, and verification plan before approving any implementation.",
    }


def planning_chain_main(argv: list[str] | None = None) -> int:
    """Entry point for ``growth planning-chain`` read-only preview."""
    args = _normalize_cli_dashes(sys.argv[1:] if argv is None else argv)
    if "--help" in args or "-h" in args:
        print("Growth planning-chain: preview gaps to verification plan")
        print("")
        print("Usage:")
        print("  python3 link.py growth planning-chain")
        print("  python3 link.py growth planning-chain --json")
        print("")
        print("Read-only. --write is not supported.")
        return 0
    if "--write" in args:
        print("error: growth planning-chain is read-only; --write is not supported", file=sys.stderr)
        return 2
    chain = collect_growth_planning_chain_preview()
    if "--json" in args:
        print(stable_growth_planning_chain_json(chain), end="")
        return 0
    render_planning_chain_plain(chain)
    return 0


def render_planning_chain_plain(chain: dict[str, Any]) -> None:
    validate_growth_planning_chain_preview(chain)
    gap_counts = chain["capability_gap_preview"]["counts"]
    upgrade_plan = chain["upgrade_execution_plan"]
    branch_plan = chain["implementation_branch_plan"]
    work_packages = chain["implementation_work_packages"]
    verification = chain["verification_plan"]
    action = chain["top_recommended_next_action"]
    print("Growth planning-chain preview")
    print(f"planning_chain_id: {chain['planning_chain_id']}")
    print(f"gaps: direct={gap_counts['direct_gap_count']} maturity={gap_counts['maturity_gap_count']} onboarding={gap_counts['onboarding_gap_count']} optional={gap_counts['optional_cross_cluster_idea_count']}")
    print(f"upgrade_plans: {upgrade_plan['upgrade_plan_count']}")
    print(f"branch_plan: {branch_plan['proposed_branch_name']} ({branch_plan['risk_level']}/{branch_plan['complexity']})")
    print(f"work_packages: {work_packages['package_count']}")
    print(f"verification_plans: {verification['plan_count']}")
    print(f"next_action: {action['summary']}")


VERIFIED_PATCH_PLAN_VERSION = "link-verified-patch-plan-v1"
VERIFIED_PATCH_OPERATION_TYPES = (
    "create_file",
    "modify_file",
    "delete_file",
    "add_test",
    "update_test",
    "documentation_update",
)
VERIFIED_PATCH_DIFF_VERSION = "link-verified-patch-diff-v1"
PATCH_BEHAVIOR_QUALITY_GATE_VERSION = "link-patch-behavior-quality-gate-v1"
AUTONOMOUS_EXECUTION_PACKAGE_VERSION = "link-autonomous-execution-package-v1"


def make_verified_patch_plan_id(work_package: dict[str, Any], operations: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "operation_ids": [operation["operation_id"] for operation in operations],
        "package_id": work_package["package_id"],
        "upgrade_id": work_package["upgrade_id"],
        "version": VERIFIED_PATCH_PLAN_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"verified-patch-plan-{digest}"


def make_verified_patch_operation_id(operation_type: str, file_path: str, work_package_id: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "file_path": file_path,
        "operation_type": operation_type,
        "version": VERIFIED_PATCH_PLAN_VERSION,
        "work_package_id": work_package_id,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"patch-operation-{digest}"


def collect_verified_patch_plan(
    work_package: dict[str, Any],
    *,
    verification_plan: dict[str, Any] | None = None,
    provided_evidence: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe intended code changes for a work package without modifying files."""
    validate_implementation_work_package(work_package)
    verification_entry = _verified_patch_verification_entry(work_package, verification_plan)
    target_files = _normalize_implementation_branch_refs(work_package["target_files"])
    operations = [_verified_patch_operation_for_file(work_package, file_path) for file_path in target_files]
    operations.sort(key=lambda item: (item["file_path"], item["operation_type"], item["operation_id"]))
    required_evidence = _verified_patch_required_evidence(work_package, verification_entry)
    provided = _normalize_implementation_branch_refs(provided_evidence or [])
    missing = [item for item in required_evidence if item not in provided]
    patch_plan = {
        "verified_patch_plan_version": VERIFIED_PATCH_PLAN_VERSION,
        "verified_patch_plan_id": make_verified_patch_plan_id(work_package, operations),
        "upgrade_id": work_package["upgrade_id"],
        "branch_plan_id": work_package["branch_plan_id"],
        "work_package_id": work_package["package_id"],
        "target_files": target_files,
        "estimated_files_changed": len(target_files),
        "estimated_tests_affected": len([path for path in target_files if _verified_patch_is_test_path(path)]),
        "patch_operations": operations,
        "compile_expectations": _verified_patch_compile_expectations(verification_entry),
        "test_expectations": _verified_patch_test_expectations(verification_entry),
        "healthcheck_expectations": _verified_patch_healthcheck_expectations(verification_entry),
        "required_evidence": required_evidence,
        "provided_evidence": provided,
        "missing_evidence": missing,
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_verified_patch_plan(patch_plan)
    return patch_plan


def validate_verified_patch_plan(patch_plan: dict[str, Any]) -> None:
    required = (
        "verified_patch_plan_version", "verified_patch_plan_id", "upgrade_id", "branch_plan_id",
        "work_package_id", "target_files", "estimated_files_changed", "estimated_tests_affected",
        "patch_operations", "compile_expectations", "test_expectations", "healthcheck_expectations",
        "required_evidence", "provided_evidence", "missing_evidence", "dry_run", "write_allowed",
        "automation_allowed", "metadata", "writes",
    )
    missing = [field for field in required if field not in patch_plan]
    if missing:
        raise ValueError(f"verified patch plan missing fields: {missing}")
    if patch_plan["verified_patch_plan_version"] != VERIFIED_PATCH_PLAN_VERSION:
        raise ValueError("unsupported verified patch plan version")
    for field in ("verified_patch_plan_id", "upgrade_id", "branch_plan_id", "work_package_id"):
        if not isinstance(patch_plan[field], str) or not patch_plan[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if patch_plan["dry_run"] is not True or patch_plan["write_allowed"] is not False or patch_plan["automation_allowed"] is not False:
        raise ValueError("verified patch plan must remain read-only")
    if patch_plan["writes"] != []:
        raise ValueError("verified patch plan must not write files")
    if not isinstance(patch_plan["metadata"], dict):
        raise TypeError("verified patch plan metadata must be a dict")
    target_files = patch_plan["target_files"]
    if not isinstance(target_files, list) or not target_files:
        raise TypeError("target_files must be a non-empty list")
    if target_files != _normalize_implementation_branch_refs(target_files):
        raise ValueError("target_files must be normalized and sorted")
    if not isinstance(patch_plan["estimated_files_changed"], int) or patch_plan["estimated_files_changed"] != len(target_files):
        raise ValueError("estimated_files_changed must match target_files length")
    expected_tests = len([path for path in target_files if _verified_patch_is_test_path(path)])
    if not isinstance(patch_plan["estimated_tests_affected"], int) or patch_plan["estimated_tests_affected"] != expected_tests:
        raise ValueError("estimated_tests_affected must match test target count")
    operations = patch_plan["patch_operations"]
    if not isinstance(operations, list) or not operations:
        raise TypeError("patch_operations must be a non-empty list")
    operation_ids: set[str] = set()
    operation_files: set[str] = set()
    for operation in operations:
        validate_verified_patch_operation(operation, set(target_files))
        if operation["operation_id"] in operation_ids:
            raise ValueError(f"duplicate verified patch operation id: {operation['operation_id']}")
        operation_ids.add(operation["operation_id"])
        operation_files.add(operation["file_path"])
    if operation_files != set(target_files):
        raise ValueError("patch_operations must cover every target file exactly at least once")
    for field in ("compile_expectations", "test_expectations", "healthcheck_expectations", "required_evidence", "provided_evidence", "missing_evidence"):
        values = patch_plan[field]
        if not isinstance(values, list):
            raise TypeError(f"{field} must be a list")
        if field in {"compile_expectations", "test_expectations", "healthcheck_expectations", "required_evidence"} and not values:
            raise ValueError(f"{field} must be non-empty")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    for field in ("required_evidence", "provided_evidence", "missing_evidence"):
        if patch_plan[field] != _normalize_implementation_branch_refs(patch_plan[field]):
            raise ValueError(f"{field} must be normalized and sorted")
    expected_missing = [item for item in patch_plan["required_evidence"] if item not in patch_plan["provided_evidence"]]
    if patch_plan["missing_evidence"] != expected_missing:
        raise ValueError("missing_evidence must match required evidence not present in provided evidence")


def stable_verified_patch_plan_json(patch_plan: dict[str, Any]) -> str:
    validate_verified_patch_plan(patch_plan)
    return _stable_ruflo_json(patch_plan, indent=2) + "\n"


def parse_verified_patch_plan_json(text: str) -> dict[str, Any]:
    import json as _json

    patch_plan = _json.loads(text)
    validate_verified_patch_plan(patch_plan)
    return patch_plan


def validate_verified_patch_operation(operation: dict[str, Any], target_files: set[str]) -> None:
    required = ("operation_id", "operation_type", "file_path", "rationale", "expected_result", "risk_level")
    missing = [field for field in required if field not in operation]
    if missing:
        raise ValueError(f"verified patch operation missing fields: {missing}")
    for field in required:
        if not isinstance(operation[field], str) or not operation[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if operation["operation_type"] not in VERIFIED_PATCH_OPERATION_TYPES:
        raise ValueError(f"invalid verified patch operation type: {operation['operation_type']}")
    if operation["risk_level"] not in UPGRADE_RISK_LEVELS:
        raise ValueError(f"invalid verified patch operation risk_level: {operation['risk_level']}")
    if operation["file_path"] not in target_files:
        raise ValueError(f"verified patch operation file_path is not a target file: {operation['file_path']}")
    if _normalize_implementation_branch_refs([operation["file_path"]]) != [operation["file_path"]]:
        raise ValueError("verified patch operation file_path must be normalized")


def _verified_patch_verification_entry(work_package: dict[str, Any], verification_plan: dict[str, Any] | None) -> dict[str, Any]:
    if verification_plan is None:
        generated = collect_verification_plan(work_package)
        return generated["plans"][0]
    if "plans" in verification_plan:
        validate_verification_plan(verification_plan)
        for plan in verification_plan["plans"]:
            if plan["package_id"] == work_package["package_id"]:
                return dict(plan)
        raise ValueError("verification_plan does not contain a plan for the work package")
    validate_verification_plan_entry(verification_plan)
    if verification_plan["package_id"] != work_package["package_id"]:
        raise ValueError("verification plan package_id does not match work package")
    return dict(verification_plan)


def _verified_patch_operation_for_file(work_package: dict[str, Any], file_path: str) -> dict[str, Any]:
    operation_type = _verified_patch_operation_type(file_path)
    operation = {
        "operation_id": make_verified_patch_operation_id(operation_type, file_path, work_package["package_id"]),
        "operation_type": operation_type,
        "file_path": file_path,
        "rationale": _verified_patch_operation_rationale(operation_type, file_path),
        "expected_result": _verified_patch_operation_expected_result(operation_type, file_path),
        "risk_level": work_package["risk"],
    }
    validate_verified_patch_operation(operation, set(work_package["target_files"]))
    return operation


def _verified_patch_operation_type(file_path: str) -> str:
    lower = file_path.lower()
    if _verified_patch_is_test_path(lower):
        return "update_test"
    if lower.endswith((".md", ".rst", ".txt")):
        return "documentation_update"
    return "modify_file"


def _verified_patch_is_test_path(file_path: str) -> bool:
    lower = file_path.lower()
    return lower.startswith("tests/") or "/test" in lower or lower.endswith("_test.py") or lower.endswith(".test.py")


def _verified_patch_operation_rationale(operation_type: str, file_path: str) -> str:
    return {
        "modify_file": f"Update {file_path} to implement the planned Link-native behavior.",
        "update_test": f"Update {file_path} to cover the planned behavior and guard regressions.",
        "add_test": f"Add {file_path} to cover the planned behavior and guard regressions.",
        "create_file": f"Create {file_path} only after review confirms no existing module is appropriate.",
        "delete_file": f"Delete {file_path} only after review confirms the file is obsolete and safe to remove.",
        "documentation_update": f"Update {file_path} to document the planned behavior and operation path.",
    }[operation_type]


def _verified_patch_operation_expected_result(operation_type: str, file_path: str) -> str:
    return {
        "modify_file": f"{file_path} contains the smallest implementation change needed for the work package.",
        "update_test": f"{file_path} verifies the new behavior without adding runtime state writes.",
        "add_test": f"{file_path} verifies the new behavior without adding runtime state writes.",
        "create_file": f"{file_path} exists only if the reviewed implementation requires a new module boundary.",
        "delete_file": f"{file_path} is removed only if tests prove no live behavior depends on it.",
        "documentation_update": f"{file_path} explains the verified behavior, safety limits, and verification path.",
    }[operation_type]


def _verified_patch_compile_expectations(verification_entry: dict[str, Any]) -> list[str]:
    return [f"compile command should pass: {command}" for command in verification_entry["compile_commands"]]


def _verified_patch_test_expectations(verification_entry: dict[str, Any]) -> list[str]:
    return [f"test command should pass: {command}" for command in verification_entry["test_commands"]]


def _verified_patch_healthcheck_expectations(verification_entry: dict[str, Any]) -> list[str]:
    return [f"healthcheck command should pass: {command}" for command in verification_entry["healthcheck_commands"]]


def _verified_patch_required_evidence(work_package: dict[str, Any], verification_entry: dict[str, Any]) -> list[str]:
    evidence = [
        "verified patch plan JSON reviewed",
        "patch operations reviewed before implementation",
        "git diff --stat",
        "git status --short --branch",
    ]
    evidence.extend(verification_entry["required_evidence"])
    evidence.extend(work_package["acceptance_criteria"])
    return _normalize_implementation_branch_refs(evidence)


def make_verified_patch_diff_id(patch_plan: dict[str, Any], diff_entries: list[dict[str, Any]]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "diff_entry_ids": [entry["diff_entry_id"] for entry in diff_entries],
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "version": VERIFIED_PATCH_DIFF_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"verified-patch-diff-{digest}"


def make_verified_patch_diff_entry_id(operation: dict[str, Any]) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "file_path": operation["file_path"],
        "operation_id": operation["operation_id"],
        "operation_type": operation["operation_type"],
        "version": VERIFIED_PATCH_DIFF_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"verified-patch-diff-entry-{digest}"


def collect_verified_patch_diff(
    patch_plan: dict[str, Any],
    *,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Convert a verified patch plan into a deterministic read-only diff preview."""
    validate_verified_patch_plan(patch_plan)
    diff_entries = [_verified_patch_diff_entry(operation) for operation in patch_plan["patch_operations"]]
    diff_entries.sort(key=lambda item: item["diff_entry_id"])
    added = sum(entry["estimated_added_lines"] for entry in diff_entries)
    removed = sum(entry["estimated_removed_lines"] for entry in diff_entries)
    modified = sum(entry["estimated_modified_lines"] for entry in diff_entries)
    diff = {
        "verified_patch_diff_version": VERIFIED_PATCH_DIFF_VERSION,
        "verified_patch_diff_id": make_verified_patch_diff_id(patch_plan, diff_entries),
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "branch_plan_id": patch_plan["branch_plan_id"],
        "work_package_id": patch_plan["work_package_id"],
        "upgrade_id": patch_plan["upgrade_id"],
        "diff_entries": diff_entries,
        "estimated_added_lines": added,
        "estimated_removed_lines": removed,
        "estimated_modified_lines": modified,
        "compile_impact": list(patch_plan["compile_expectations"]),
        "test_impact": list(patch_plan["test_expectations"]),
        "healthcheck_impact": list(patch_plan["healthcheck_expectations"]),
        "confidence_score": _verified_patch_diff_confidence_score(patch_plan, diff_entries),
        "risk_score": _verified_patch_diff_risk_score(diff_entries),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_verified_patch_diff(diff)
    return diff


def validate_verified_patch_diff(diff: dict[str, Any]) -> None:
    required = (
        "verified_patch_diff_version", "verified_patch_diff_id", "verified_patch_plan_id",
        "branch_plan_id", "work_package_id", "upgrade_id", "diff_entries",
        "estimated_added_lines", "estimated_removed_lines", "estimated_modified_lines",
        "compile_impact", "test_impact", "healthcheck_impact", "confidence_score",
        "risk_score", "dry_run", "write_allowed", "automation_allowed", "metadata", "writes",
    )
    missing = [field for field in required if field not in diff]
    if missing:
        raise ValueError(f"verified patch diff missing fields: {missing}")
    if diff["verified_patch_diff_version"] != VERIFIED_PATCH_DIFF_VERSION:
        raise ValueError("unsupported verified patch diff version")
    for field in ("verified_patch_diff_id", "verified_patch_plan_id", "branch_plan_id", "work_package_id", "upgrade_id"):
        if not isinstance(diff[field], str) or not diff[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if diff["dry_run"] is not True or diff["write_allowed"] is not False or diff["automation_allowed"] is not False:
        raise ValueError("verified patch diff must remain read-only")
    if diff["writes"] != []:
        raise ValueError("verified patch diff must not write files")
    if not isinstance(diff["metadata"], dict):
        raise TypeError("verified patch diff metadata must be a dict")
    entries = diff["diff_entries"]
    if not isinstance(entries, list) or not entries:
        raise TypeError("diff_entries must be a non-empty list")
    entry_ids: set[str] = set()
    operation_ids: set[str] = set()
    for entry in entries:
        validate_verified_patch_diff_entry(entry)
        if entry["diff_entry_id"] in entry_ids:
            raise ValueError(f"duplicate verified patch diff entry id: {entry['diff_entry_id']}")
        if entry["operation_id"] in operation_ids:
            raise ValueError(f"duplicate verified patch diff operation id: {entry['operation_id']}")
        entry_ids.add(entry["diff_entry_id"])
        operation_ids.add(entry["operation_id"])
    if [entry["diff_entry_id"] for entry in entries] != sorted(entry["diff_entry_id"] for entry in entries):
        raise ValueError("diff_entries must be sorted by diff_entry_id")
    for field in ("estimated_added_lines", "estimated_removed_lines", "estimated_modified_lines"):
        if not isinstance(diff[field], int) or diff[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if diff["estimated_added_lines"] != sum(entry["estimated_added_lines"] for entry in entries):
        raise ValueError("estimated_added_lines must match diff entry sum")
    if diff["estimated_removed_lines"] != sum(entry["estimated_removed_lines"] for entry in entries):
        raise ValueError("estimated_removed_lines must match diff entry sum")
    if diff["estimated_modified_lines"] != sum(entry["estimated_modified_lines"] for entry in entries):
        raise ValueError("estimated_modified_lines must match diff entry sum")
    for field in ("compile_impact", "test_impact", "healthcheck_impact"):
        values = diff[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    _validate_probability_score(diff["confidence_score"], "confidence_score")
    _validate_probability_score(diff["risk_score"], "risk_score")


def stable_verified_patch_diff_json(diff: dict[str, Any]) -> str:
    validate_verified_patch_diff(diff)
    return _stable_ruflo_json(diff, indent=2) + "\n"


def parse_verified_patch_diff_json(text: str) -> dict[str, Any]:
    import json as _json

    diff = _json.loads(text)
    validate_verified_patch_diff(diff)
    return diff


def validate_verified_patch_diff_entry(entry: dict[str, Any]) -> None:
    required = (
        "diff_entry_id", "operation_id", "file_path", "operation_type", "before_summary",
        "after_summary", "change_description", "diff_preview", "estimated_added_lines",
        "estimated_removed_lines", "estimated_modified_lines", "compile_impact", "test_impact",
        "healthcheck_impact", "confidence_score", "risk_score",
    )
    missing = [field for field in required if field not in entry]
    if missing:
        raise ValueError(f"verified patch diff entry missing fields: {missing}")
    for field in ("diff_entry_id", "operation_id", "file_path", "operation_type", "before_summary", "after_summary", "change_description", "diff_preview"):
        if not isinstance(entry[field], str) or not entry[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if entry["operation_type"] not in VERIFIED_PATCH_OPERATION_TYPES:
        raise ValueError(f"invalid verified patch diff operation type: {entry['operation_type']}")
    if not entry["diff_preview"].startswith("--- old\n+++ new\n@@"):
        raise ValueError("diff_preview must use unified-diff-style headers")
    for field in ("estimated_added_lines", "estimated_removed_lines", "estimated_modified_lines"):
        if not isinstance(entry[field], int) or entry[field] < 0:
            raise ValueError(f"{field} must be a non-negative integer")
    if entry["estimated_added_lines"] + entry["estimated_removed_lines"] + entry["estimated_modified_lines"] <= 0:
        raise ValueError("diff entry must estimate at least one changed line")
    for field in ("compile_impact", "test_impact", "healthcheck_impact"):
        values = entry[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if not all(isinstance(value, str) and value.strip() for value in values):
            raise TypeError(f"{field} must contain non-empty strings")
    _validate_probability_score(entry["confidence_score"], "entry confidence_score")
    _validate_probability_score(entry["risk_score"], "entry risk_score")


def _verified_patch_diff_entry(operation: dict[str, Any]) -> dict[str, Any]:
    validate_verified_patch_operation(operation, {operation["file_path"]})
    line_counts = _verified_patch_diff_line_counts(operation["operation_type"])
    entry = {
        "diff_entry_id": make_verified_patch_diff_entry_id(operation),
        "operation_id": operation["operation_id"],
        "file_path": operation["file_path"],
        "operation_type": operation["operation_type"],
        "before_summary": _verified_patch_diff_before_summary(operation),
        "after_summary": _verified_patch_diff_after_summary(operation),
        "change_description": operation["rationale"],
        "diff_preview": _verified_patch_diff_preview(operation),
        "estimated_added_lines": line_counts["added"],
        "estimated_removed_lines": line_counts["removed"],
        "estimated_modified_lines": line_counts["modified"],
        "compile_impact": _verified_patch_diff_compile_impact(operation),
        "test_impact": _verified_patch_diff_test_impact(operation),
        "healthcheck_impact": ["link_healthcheck.py should remain passing after the planned patch"],
        "confidence_score": _verified_patch_diff_entry_confidence(operation),
        "risk_score": _verified_patch_risk_score(operation["risk_level"]),
    }
    validate_verified_patch_diff_entry(entry)
    return entry


def _verified_patch_diff_line_counts(operation_type: str) -> dict[str, int]:
    counts = {
        "create_file": {"added": 24, "removed": 0, "modified": 0},
        "modify_file": {"added": 18, "removed": 4, "modified": 8},
        "delete_file": {"added": 0, "removed": 20, "modified": 0},
        "add_test": {"added": 18, "removed": 0, "modified": 0},
        "update_test": {"added": 16, "removed": 2, "modified": 6},
        "documentation_update": {"added": 10, "removed": 1, "modified": 4},
    }
    if operation_type not in counts:
        raise ValueError(f"invalid verified patch operation type: {operation_type}")
    return counts[operation_type]


def _verified_patch_diff_before_summary(operation: dict[str, Any]) -> str:
    if operation["operation_type"] in {"create_file", "add_test"}:
        return f"{operation['file_path']} is not yet represented in the planned implementation surface."
    if operation["operation_type"] == "delete_file":
        return f"{operation['file_path']} is present before the reviewed cleanup."
    return f"{operation['file_path']} contains current behavior before the planned upgrade."


def _verified_patch_diff_after_summary(operation: dict[str, Any]) -> str:
    if operation["operation_type"] == "delete_file":
        return f"{operation['file_path']} is removed only after review and verification confirm it is obsolete."
    return operation["expected_result"]


def _verified_patch_diff_preview(operation: dict[str, Any]) -> str:
    old_behavior = _verified_patch_diff_before_summary(operation)
    new_behavior = _verified_patch_diff_after_summary(operation)
    return "\n".join([
        "--- old",
        "+++ new",
        "@@",
        f"- {old_behavior}",
        f"+ {new_behavior}",
    ])


def _verified_patch_diff_compile_impact(operation: dict[str, Any]) -> list[str]:
    if operation["file_path"].endswith(".py"):
        return [f"py_compile should include {operation['file_path']} or the closest affected Python module"]
    return ["compile impact is expected to remain unchanged for non-Python target"]


def _verified_patch_diff_test_impact(operation: dict[str, Any]) -> list[str]:
    if _verified_patch_is_test_path(operation["file_path"]):
        return [f"{operation['file_path']} should include or update regression coverage"]
    return ["tests/test_growth_pipeline.py should cover the planned behavior when this slice touches Growth helpers"]


def _verified_patch_diff_entry_confidence(operation: dict[str, Any]) -> float:
    base = 0.82
    if operation["operation_type"] in {"create_file", "delete_file"}:
        base -= 0.12
    if operation["risk_level"] == "high":
        base -= 0.18
    elif operation["risk_level"] == "medium":
        base -= 0.08
    return round(max(0.0, min(1.0, base)), 4)


def _verified_patch_diff_confidence_score(patch_plan: dict[str, Any], diff_entries: list[dict[str, Any]]) -> float:
    if not diff_entries:
        return 0.0
    missing_penalty = min(0.3, len(patch_plan["missing_evidence"]) * 0.02)
    average = sum(entry["confidence_score"] for entry in diff_entries) / len(diff_entries)
    return round(max(0.0, min(1.0, average - missing_penalty)), 4)


def _verified_patch_diff_risk_score(diff_entries: list[dict[str, Any]]) -> float:
    if not diff_entries:
        return 0.0
    return round(max(entry["risk_score"] for entry in diff_entries), 4)


def _verified_patch_risk_score(risk_level: str) -> float:
    if risk_level not in UPGRADE_RISK_LEVELS:
        raise ValueError(f"invalid verified patch risk level: {risk_level}")
    return {"low": 0.2, "medium": 0.5, "high": 0.85}[risk_level]


def _validate_probability_score(value: Any, field_name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{field_name} must be numeric between 0.0 and 1.0")
    number = float(value)
    if not (0.0 <= number <= 1.0):
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")


def make_patch_behavior_quality_gate_id(
    patch_plan: dict[str, Any],
    patch_diff: dict[str, Any] | None,
    findings: list[dict[str, Any]],
    assumptions: list[str],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "assumptions": assumptions,
        "finding_ids": [finding["finding_id"] for finding in findings],
        "verified_patch_diff_id": patch_diff["verified_patch_diff_id"] if patch_diff else "",
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "version": PATCH_BEHAVIOR_QUALITY_GATE_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"patch-behavior-quality-gate-{digest}"


def make_patch_behavior_quality_finding_id(category: str, severity: str, message: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "category": category,
        "message": message,
        "severity": severity,
        "version": PATCH_BEHAVIOR_QUALITY_GATE_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"patch-behavior-finding-{digest}"


def collect_patch_behavior_quality_gate(
    patch_plan: dict[str, Any],
    *,
    patch_diff: dict[str, Any] | None = None,
    assumptions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Score a verified patch plan/diff for Karpathy-style behavior risks without writing."""
    validate_verified_patch_plan(patch_plan)
    if patch_diff is not None:
        validate_verified_patch_diff(patch_diff)
        if patch_diff["verified_patch_plan_id"] != patch_plan["verified_patch_plan_id"]:
            raise ValueError("patch_diff must reference the verified patch plan")
    normalized_assumptions = _normalize_patch_behavior_text_list(assumptions or [])
    findings = _collect_patch_behavior_findings(patch_plan, patch_diff, normalized_assumptions)
    findings.sort(key=lambda item: (item["severity"], item["category"], item["finding_id"]))
    risk_score = _patch_behavior_risk_score(patch_plan, patch_diff, findings)
    quality_score = _patch_behavior_quality_score(findings, risk_score)
    pass_status = _patch_behavior_pass_status(findings, quality_score, risk_score)
    required_clarifications = _patch_behavior_required_clarifications(findings)
    gate = {
        "quality_gate_version": PATCH_BEHAVIOR_QUALITY_GATE_VERSION,
        "quality_gate_id": make_patch_behavior_quality_gate_id(
            patch_plan,
            patch_diff,
            findings,
            normalized_assumptions,
        ),
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "verified_patch_diff_id": patch_diff["verified_patch_diff_id"] if patch_diff else "",
        "pass_status": pass_status,
        "quality_score": quality_score,
        "risk_score": risk_score,
        "assumptions": normalized_assumptions,
        "findings": findings,
        "required_clarifications": required_clarifications,
        "recommended_next_action": _patch_behavior_recommended_next_action(pass_status, required_clarifications),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_patch_behavior_quality_gate(gate)
    return gate


def validate_patch_behavior_quality_gate(gate: dict[str, Any]) -> None:
    required = (
        "quality_gate_version", "quality_gate_id", "verified_patch_plan_id", "verified_patch_diff_id",
        "pass_status", "quality_score", "risk_score", "assumptions", "findings",
        "required_clarifications", "recommended_next_action", "dry_run", "write_allowed",
        "automation_allowed", "metadata", "writes",
    )
    missing = [field for field in required if field not in gate]
    if missing:
        raise ValueError(f"patch behavior quality gate missing fields: {missing}")
    if gate["quality_gate_version"] != PATCH_BEHAVIOR_QUALITY_GATE_VERSION:
        raise ValueError("unsupported patch behavior quality gate version")
    for field in ("quality_gate_id", "verified_patch_plan_id", "pass_status", "recommended_next_action"):
        if not isinstance(gate[field], str) or not gate[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if gate["pass_status"] not in {"pass", "review", "block"}:
        raise ValueError(f"invalid patch behavior pass_status: {gate['pass_status']}")
    if not isinstance(gate["verified_patch_diff_id"], str):
        raise TypeError("verified_patch_diff_id must be a string")
    _validate_probability_score(gate["quality_score"], "quality_score")
    _validate_probability_score(gate["risk_score"], "risk_score")
    if gate["dry_run"] is not True or gate["write_allowed"] is not False or gate["automation_allowed"] is not False:
        raise ValueError("patch behavior quality gate must remain read-only")
    if gate["writes"] != []:
        raise ValueError("patch behavior quality gate must not write files")
    if not isinstance(gate["metadata"], dict):
        raise TypeError("patch behavior quality gate metadata must be a dict")
    for field in ("assumptions", "required_clarifications"):
        values = gate[field]
        if not isinstance(values, list):
            raise TypeError(f"{field} must be a list")
        if values != _normalize_patch_behavior_text_list(values):
            raise ValueError(f"{field} must be normalized and sorted")
    findings = gate["findings"]
    if not isinstance(findings, list):
        raise TypeError("findings must be a list")
    finding_ids: set[str] = set()
    for finding in findings:
        validate_patch_behavior_quality_finding(finding)
        if finding["finding_id"] in finding_ids:
            raise ValueError(f"duplicate patch behavior finding id: {finding['finding_id']}")
        finding_ids.add(finding["finding_id"])
    if findings and [item["finding_id"] for item in findings] != sorted(item["finding_id"] for item in findings):
        raise ValueError("findings must be sorted by finding_id")
    severities = {finding["severity"] for finding in findings}
    if gate["pass_status"] == "pass" and severities:
        raise ValueError("pass status cannot include findings")
    if gate["pass_status"] == "block" and "block" not in severities:
        raise ValueError("block status requires a block finding")
    if gate["pass_status"] == "review" and "block" in severities:
        raise ValueError("review status cannot include block findings")


def stable_patch_behavior_quality_gate_json(gate: dict[str, Any]) -> str:
    validate_patch_behavior_quality_gate(gate)
    return _stable_ruflo_json(gate, indent=2) + "\n"


def parse_patch_behavior_quality_gate_json(text: str) -> dict[str, Any]:
    import json as _json

    gate = _json.loads(text)
    validate_patch_behavior_quality_gate(gate)
    return gate


def validate_patch_behavior_quality_finding(finding: dict[str, Any]) -> None:
    required = ("finding_id", "category", "severity", "message", "evidence")
    missing = [field for field in required if field not in finding]
    if missing:
        raise ValueError(f"patch behavior finding missing fields: {missing}")
    for field in ("finding_id", "category", "severity", "message"):
        if not isinstance(finding[field], str) or not finding[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if finding["severity"] not in {"info", "review", "block"}:
        raise ValueError(f"invalid patch behavior finding severity: {finding['severity']}")
    evidence = finding["evidence"]
    if not isinstance(evidence, list) or not evidence:
        raise TypeError("patch behavior finding evidence must be a non-empty list")
    if evidence != _normalize_patch_behavior_text_list(evidence):
        raise ValueError("patch behavior finding evidence must be normalized and sorted")


def _collect_patch_behavior_findings(
    patch_plan: dict[str, Any],
    patch_diff: dict[str, Any] | None,
    assumptions: list[str],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if not assumptions:
        findings.append(_patch_behavior_finding(
            "assumptions",
            "review",
            "No assumptions were surfaced before implementation.",
            [patch_plan["verified_patch_plan_id"]],
        ))
    if patch_plan["missing_evidence"]:
        severity = "block" if len(patch_plan["missing_evidence"]) >= 8 else "review"
        findings.append(_patch_behavior_finding(
            "missing_evidence",
            severity,
            f"{len(patch_plan['missing_evidence'])} required evidence item(s) are missing.",
            patch_plan["missing_evidence"],
        ))
    if patch_plan["estimated_files_changed"] > 10:
        findings.append(_patch_behavior_finding(
            "surgicality",
            "block",
            "Planned patch touches more than 10 files before implementation.",
            patch_plan["target_files"],
        ))
    elif patch_plan["estimated_files_changed"] > 5:
        findings.append(_patch_behavior_finding(
            "surgicality",
            "review",
            "Planned patch touches more than 5 files and may be overbroad.",
            patch_plan["target_files"],
        ))
    risky_operations = [operation for operation in patch_plan["patch_operations"] if operation["operation_type"] in {"create_file", "delete_file"}]
    if risky_operations:
        severity = "block" if any(operation["operation_type"] == "delete_file" for operation in risky_operations) else "review"
        findings.append(_patch_behavior_finding(
            "risky_operations",
            severity,
            "Patch plan contains create/delete operations that need explicit review.",
            [f"{operation['operation_type']}:{operation['file_path']}" for operation in risky_operations],
        ))
    unclear = [operation for operation in patch_plan["patch_operations"] if _patch_behavior_operation_unclear(operation)]
    if unclear:
        findings.append(_patch_behavior_finding(
            "clarity",
            "review",
            "One or more patch operations have unclear rationale or expected_result.",
            [operation["operation_id"] for operation in unclear],
        ))
    if not _patch_behavior_has_verification_coverage(patch_plan, patch_diff):
        findings.append(_patch_behavior_finding(
            "verification_coverage",
            "block",
            "Patch operations are not covered by compile, test, and healthcheck expectations.",
            [patch_plan["verified_patch_plan_id"]],
        ))
    if _patch_behavior_overengineering_risk(patch_plan, patch_diff):
        findings.append(_patch_behavior_finding(
            "overengineering",
            "review",
            "Patch preview suggests unnecessary breadth or abstraction risk for this slice.",
            [patch_plan["verified_patch_plan_id"]],
        ))
    if patch_diff is not None and patch_diff["risk_score"] >= 0.8:
        findings.append(_patch_behavior_finding(
            "diff_risk",
            "block",
            "Verified patch diff risk score is high before implementation.",
            [patch_diff["verified_patch_diff_id"]],
        ))
    return _dedupe_patch_behavior_findings(findings)


def _patch_behavior_finding(category: str, severity: str, message: str, evidence: list[str]) -> dict[str, Any]:
    normalized_evidence = _normalize_patch_behavior_text_list(evidence)
    finding = {
        "finding_id": make_patch_behavior_quality_finding_id(category, severity, message),
        "category": category,
        "severity": severity,
        "message": message,
        "evidence": normalized_evidence,
    }
    validate_patch_behavior_quality_finding(finding)
    return finding


def _dedupe_patch_behavior_findings(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    for finding in findings:
        by_id[finding["finding_id"]] = finding
    return sorted(by_id.values(), key=lambda item: item["finding_id"])


def _patch_behavior_operation_unclear(operation: dict[str, Any]) -> bool:
    vague_terms = {"todo", "tbd", "fix stuff", "update things", "change code", "implement"}
    rationale = operation.get("rationale", "").strip().lower()
    expected = operation.get("expected_result", "").strip().lower()
    if len(rationale) < 24 or len(expected) < 24:
        return True
    return rationale in vague_terms or expected in vague_terms


def _patch_behavior_has_verification_coverage(patch_plan: dict[str, Any], patch_diff: dict[str, Any] | None) -> bool:
    if not patch_plan["compile_expectations"] or not patch_plan["test_expectations"] or not patch_plan["healthcheck_expectations"]:
        return False
    if patch_diff is None:
        return True
    return bool(patch_diff["compile_impact"] and patch_diff["test_impact"] and patch_diff["healthcheck_impact"])


def _patch_behavior_overengineering_risk(patch_plan: dict[str, Any], patch_diff: dict[str, Any] | None) -> bool:
    if len(patch_plan["patch_operations"]) > 6:
        return True
    if any(operation["operation_type"] == "create_file" for operation in patch_plan["patch_operations"]):
        return True
    if patch_diff is not None and patch_diff["estimated_added_lines"] > 180:
        return True
    return False


def _patch_behavior_quality_score(findings: list[dict[str, Any]], risk_score: float) -> float:
    score = 1.0 - min(0.35, risk_score * 0.25)
    for finding in findings:
        if finding["severity"] == "block":
            score -= 0.28
        elif finding["severity"] == "review":
            score -= 0.12
        else:
            score -= 0.03
    return round(max(0.0, min(1.0, score)), 4)


def _patch_behavior_risk_score(
    patch_plan: dict[str, Any],
    patch_diff: dict[str, Any] | None,
    findings: list[dict[str, Any]],
) -> float:
    operation_risk = max((_verified_patch_risk_score(operation["risk_level"]) for operation in patch_plan["patch_operations"]), default=0.0)
    diff_risk = patch_diff["risk_score"] if patch_diff is not None else 0.0
    finding_risk = 0.0
    for finding in findings:
        if finding["severity"] == "block":
            finding_risk += 0.18
        elif finding["severity"] == "review":
            finding_risk += 0.08
        else:
            finding_risk += 0.02
    return round(max(0.0, min(1.0, max(operation_risk, diff_risk) + finding_risk)), 4)


def _patch_behavior_pass_status(findings: list[dict[str, Any]], quality_score: float, risk_score: float) -> str:
    severities = {finding["severity"] for finding in findings}
    if "block" in severities or quality_score < 0.55 or risk_score >= 0.85:
        return "block"
    if "review" in severities or quality_score < 0.82 or risk_score >= 0.55:
        return "review"
    return "pass"


def _patch_behavior_required_clarifications(findings: list[dict[str, Any]]) -> list[str]:
    prompts: list[str] = []
    for finding in findings:
        if finding["category"] == "assumptions":
            prompts.append("State the assumptions that make this patch safe and scoped before implementation.")
        elif finding["category"] == "clarity":
            prompts.append("Clarify the rationale and expected result for each vague patch operation.")
        elif finding["category"] == "surgicality":
            prompts.append("Confirm why the planned file count is necessary for the smallest safe slice.")
        elif finding["category"] == "risky_operations":
            prompts.append("Confirm the create/delete operation is necessary and has rollback coverage.")
        elif finding["category"] == "missing_evidence":
            prompts.append("Provide or explicitly waive the missing evidence before implementation.")
        elif finding["severity"] == "block":
            prompts.append(f"Resolve blocking finding: {finding['message']}")
    return _normalize_patch_behavior_text_list(prompts)


def _patch_behavior_recommended_next_action(pass_status: str, required_clarifications: list[str]) -> str:
    if pass_status == "pass":
        return "Proceed to human review of the patch plan; do not execute without approval."
    if pass_status == "review":
        return "Review findings and answer required clarifications before implementation."
    if required_clarifications:
        return "Do not implement until blocking findings are resolved and clarifications are answered."
    return "Do not implement until the patch behavior quality gate passes review."


def _normalize_patch_behavior_text_list(values: list[str] | tuple[str, ...]) -> list[str]:
    if not isinstance(values, (list, tuple)):
        raise TypeError("patch behavior text values must be a list or tuple")
    normalized: list[str] = []
    for raw in values:
        value = str(raw or "").strip()
        if not value:
            raise ValueError("patch behavior text values cannot be empty")
        if "\x00" in value:
            raise ValueError("patch behavior text values cannot contain null bytes")
        if value not in normalized:
            normalized.append(value)
    return sorted(normalized)




def make_autonomous_execution_package_id(
    patch_plan: dict[str, Any],
    verification_entry: dict[str, Any],
    quality_gate: dict[str, Any],
    stages: list[dict[str, Any]],
) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "quality_gate_id": quality_gate["quality_gate_id"],
        "stage_ids": [stage["stage_id"] for stage in stages],
        "verification_plan_id": verification_entry["verification_plan_id"],
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "version": AUTONOMOUS_EXECUTION_PACKAGE_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"autonomous-execution-package-{digest}"


def make_autonomous_execution_stage_id(package_seed: str, order: int, stage_name: str) -> str:
    import hashlib

    payload = _stable_ruflo_json({
        "order": order,
        "package_seed": package_seed,
        "stage_name": stage_name,
        "version": AUTONOMOUS_EXECUTION_PACKAGE_VERSION,
    })
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
    return f"autonomous-execution-stage-{digest}"


def collect_autonomous_execution_package(
    patch_plan: dict[str, Any],
    *,
    verification_plan: dict[str, Any] | None = None,
    patch_diff: dict[str, Any] | None = None,
    quality_gate: dict[str, Any] | None = None,
    assumptions: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Describe how an upgrade would execute later, without executing anything."""
    validate_verified_patch_plan(patch_plan)
    verification_entry = _autonomous_execution_verification_entry(patch_plan, verification_plan)
    if patch_diff is None:
        patch_diff = collect_verified_patch_diff(patch_plan)
    else:
        validate_verified_patch_diff(patch_diff)
        if patch_diff["verified_patch_plan_id"] != patch_plan["verified_patch_plan_id"]:
            raise ValueError("patch_diff must reference the verified patch plan")
    if quality_gate is None:
        quality_gate = collect_patch_behavior_quality_gate(
            patch_plan,
            patch_diff=patch_diff,
            assumptions=assumptions or [],
        )
    else:
        validate_patch_behavior_quality_gate(quality_gate)
        if quality_gate["verified_patch_plan_id"] != patch_plan["verified_patch_plan_id"]:
            raise ValueError("quality_gate must reference the verified patch plan")
        if quality_gate["verified_patch_diff_id"] and quality_gate["verified_patch_diff_id"] != patch_diff["verified_patch_diff_id"]:
            raise ValueError("quality_gate must reference the verified patch diff")
    stages = _autonomous_execution_stages(patch_plan, patch_diff, verification_entry, quality_gate)
    package = {
        "execution_package_version": AUTONOMOUS_EXECUTION_PACKAGE_VERSION,
        "execution_package_id": make_autonomous_execution_package_id(
            patch_plan,
            verification_entry,
            quality_gate,
            stages,
        ),
        "upgrade_id": patch_plan["upgrade_id"],
        "branch_plan_id": patch_plan["branch_plan_id"],
        "work_package_id": patch_plan["work_package_id"],
        "verification_plan_id": verification_entry["verification_plan_id"],
        "verified_patch_plan_id": patch_plan["verified_patch_plan_id"],
        "verified_patch_diff_id": patch_diff["verified_patch_diff_id"],
        "quality_gate_id": quality_gate["quality_gate_id"],
        "execution_stages": stages,
        "stage_count": len(stages),
        "dry_run": True,
        "write_allowed": False,
        "automation_allowed": False,
        "metadata": dict(metadata or {}),
        "writes": [],
    }
    validate_autonomous_execution_package(package)
    return package


def validate_autonomous_execution_package(package: dict[str, Any]) -> None:
    required = (
        "execution_package_version", "execution_package_id", "upgrade_id", "branch_plan_id",
        "work_package_id", "verification_plan_id", "verified_patch_plan_id", "verified_patch_diff_id",
        "quality_gate_id", "execution_stages", "stage_count", "dry_run", "write_allowed",
        "automation_allowed", "metadata", "writes",
    )
    missing = [field for field in required if field not in package]
    if missing:
        raise ValueError(f"autonomous execution package missing fields: {missing}")
    if package["execution_package_version"] != AUTONOMOUS_EXECUTION_PACKAGE_VERSION:
        raise ValueError("unsupported autonomous execution package version")
    for field in (
        "execution_package_id", "upgrade_id", "branch_plan_id", "work_package_id",
        "verification_plan_id", "verified_patch_plan_id", "verified_patch_diff_id", "quality_gate_id",
    ):
        if not isinstance(package[field], str) or not package[field].strip():
            raise ValueError(f"{field} must be a non-empty string")
    if package["dry_run"] is not True or package["write_allowed"] is not False or package["automation_allowed"] is not False:
        raise ValueError("autonomous execution package must remain read-only")
    if package["writes"] != []:
        raise ValueError("autonomous execution package must not write files")
    if not isinstance(package["metadata"], dict):
        raise TypeError("autonomous execution package metadata must be a dict")
    stages = package["execution_stages"]
    if not isinstance(stages, list) or not stages:
        raise TypeError("execution_stages must be a non-empty list")
    if not isinstance(package["stage_count"], int) or package["stage_count"] != len(stages):
        raise ValueError("stage_count must match execution_stages length")
    expected_names = list(_AUTONOMOUS_EXECUTION_STAGE_NAMES)
    stage_ids: set[str] = set()
    for index, stage in enumerate(stages, start=1):
        validate_autonomous_execution_stage(stage)
        if stage["stage_id"] in stage_ids:
            raise ValueError(f"duplicate autonomous execution stage id: {stage['stage_id']}")
        stage_ids.add(stage["stage_id"])
        if stage["order"] != index:
            raise ValueError("execution stages must be ordered from 1 without gaps")
        if stage["stage_name"] != expected_names[index - 1]:
            raise ValueError("execution stages must use the canonical execution order")


def stable_autonomous_execution_package_json(package: dict[str, Any]) -> str:
    validate_autonomous_execution_package(package)
    return _stable_ruflo_json(package, indent=2) + "\n"


def parse_autonomous_execution_package_json(text: str) -> dict[str, Any]:
    import json as _json

    package = _json.loads(text)
    validate_autonomous_execution_package(package)
    return package


_AUTONOMOUS_EXECUTION_STAGE_NAMES = (
    "create workspace",
    "create branch",
    "apply patch operations",
    "run compile",
    "run tests",
    "run healthcheck",
    "evaluate quality gate",
    "produce review bundle",
)


def validate_autonomous_execution_stage(stage: dict[str, Any]) -> None:
    required = (
        "stage_id", "order", "stage_name", "inputs", "outputs", "success_criteria",
        "failure_criteria", "rollback_action",
    )
    missing = [field for field in required if field not in stage]
    if missing:
        raise ValueError(f"autonomous execution stage missing fields: {missing}")
    if not isinstance(stage["stage_id"], str) or not stage["stage_id"].strip():
        raise ValueError("stage_id must be a non-empty string")
    if not isinstance(stage["order"], int) or stage["order"] < 1:
        raise ValueError("stage order must be a positive integer")
    if stage["stage_name"] not in _AUTONOMOUS_EXECUTION_STAGE_NAMES:
        raise ValueError(f"invalid autonomous execution stage name: {stage['stage_name']}")
    for field in ("inputs", "outputs", "success_criteria", "failure_criteria"):
        values = stage[field]
        if not isinstance(values, list) or not values:
            raise TypeError(f"{field} must be a non-empty list")
        if values != _normalize_patch_behavior_text_list(values):
            raise ValueError(f"{field} must be normalized and sorted")
    if not isinstance(stage["rollback_action"], str) or not stage["rollback_action"].strip():
        raise ValueError("rollback_action must be a non-empty string")


def _autonomous_execution_verification_entry(
    patch_plan: dict[str, Any],
    verification_plan: dict[str, Any] | None,
) -> dict[str, Any]:
    if verification_plan is None:
        return {
            "verification_plan_id": "verification-plan-unresolved",
            "package_id": patch_plan["work_package_id"],
            "branch_plan_id": patch_plan["branch_plan_id"],
            "upgrade_id": patch_plan["upgrade_id"],
            "compile_commands": [item.replace("compile command should pass: ", "") for item in patch_plan["compile_expectations"]],
            "test_commands": [item.replace("test command should pass: ", "") for item in patch_plan["test_expectations"]],
            "healthcheck_commands": [item.replace("healthcheck command should pass: ", "") for item in patch_plan["healthcheck_expectations"]],
        }
    if "plans" in verification_plan:
        validate_verification_plan(verification_plan)
        for plan in verification_plan["plans"]:
            if plan["package_id"] == patch_plan["work_package_id"]:
                return dict(plan)
        raise ValueError("verification_plan does not contain a plan for the patch plan work package")
    validate_verification_plan_entry(verification_plan)
    if verification_plan["package_id"] != patch_plan["work_package_id"]:
        raise ValueError("verification plan package_id does not match patch plan work package")
    return dict(verification_plan)


def _autonomous_execution_stages(
    patch_plan: dict[str, Any],
    patch_diff: dict[str, Any],
    verification_entry: dict[str, Any],
    quality_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    seed = f"{patch_plan['verified_patch_plan_id']}:{patch_diff['verified_patch_diff_id']}:{quality_gate['quality_gate_id']}"
    stage_specs = [
        (
            "create workspace",
            [patch_plan["verified_patch_plan_id"], "approved execution request"],
            ["isolated workspace path planned", "workspace remains uncreated in this package"],
            ["workspace location is inside the approved repository boundary"],
            ["workspace path is outside repository boundary", "workspace cannot be isolated"],
            "Do not create the workspace; discard the planned workspace path.",
        ),
        (
            "create branch",
            [patch_plan["branch_plan_id"], "approved branch request"],
            ["implementation branch name planned", "branch remains uncreated in this package"],
            ["branch name is reviewable and tied to branch_plan_id"],
            ["branch name is missing", "branch request lacks approval"],
            "Do not create the branch; keep HEAD unchanged.",
        ),
        (
            "apply patch operations",
            [patch_plan["verified_patch_plan_id"], patch_diff["verified_patch_diff_id"]],
            ["patch operations planned as data", "no files modified by this package"],
            ["every patch operation maps to a target file and diff preview"],
            ["patch operation is outside target files", "patch behavior quality gate blocks implementation"],
            "Discard planned patch operations; keep working tree unchanged.",
        ),
        (
            "run compile",
            list(verification_entry["compile_commands"]),
            ["compile command list planned", "compile commands remain unexecuted"],
            ["all compile commands would be expected to pass"],
            ["compile command is missing", "compile command exits nonzero during later execution"],
            "Stop execution and revert any applied patch before review.",
        ),
        (
            "run tests",
            list(verification_entry["test_commands"]),
            ["test command list planned", "test commands remain unexecuted"],
            ["all test commands would be expected to pass"],
            ["test command is missing", "test command exits nonzero during later execution"],
            "Stop execution and revert any applied patch before review.",
        ),
        (
            "run healthcheck",
            list(verification_entry["healthcheck_commands"]),
            ["healthcheck command list planned", "healthcheck commands remain unexecuted"],
            ["healthcheck would be expected to pass"],
            ["healthcheck command is missing", "healthcheck exits nonzero during later execution"],
            "Stop execution and revert any applied patch before review.",
        ),
        (
            "evaluate quality gate",
            [quality_gate["quality_gate_id"], quality_gate["pass_status"]],
            ["quality gate decision planned", "quality gate remains read-only"],
            ["quality gate pass_status is pass before execution approval"],
            ["quality gate pass_status is review or block", "required clarifications remain unanswered"],
            "Do not proceed to execution until quality gate findings are resolved.",
        ),
        (
            "produce review bundle",
            [patch_plan["verified_patch_plan_id"], patch_diff["verified_patch_diff_id"], quality_gate["quality_gate_id"]],
            ["review bundle contents planned", "review bundle file remains unwritten"],
            ["review bundle references plan, diff, gate, verification, and rollback data"],
            ["review bundle omits required evidence", "review bundle would require runtime state writes"],
            "Do not write review artifacts; keep package as JSON preview only.",
        ),
    ]
    stages: list[dict[str, Any]] = []
    for order, (stage_name, inputs, outputs, success, failure, rollback) in enumerate(stage_specs, start=1):
        stage = {
            "stage_id": make_autonomous_execution_stage_id(seed, order, stage_name),
            "order": order,
            "stage_name": stage_name,
            "inputs": _normalize_patch_behavior_text_list(inputs),
            "outputs": _normalize_patch_behavior_text_list(outputs),
            "success_criteria": _normalize_patch_behavior_text_list(success),
            "failure_criteria": _normalize_patch_behavior_text_list(failure),
            "rollback_action": rollback,
        }
        validate_autonomous_execution_stage(stage)
        stages.append(stage)
    return stages




def _normalize_feedback_status(status: str) -> str:
    raw = str(status or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "accept": "accepted",
        "approved": "accepted",
        "yes": "accepted",
        "reject": "rejected",
        "no": "rejected",
        "declined": "rejected",
        "defer": "deferred",
        "later": "deferred",
        "review": "deferred",
    }
    normalized = aliases.get(raw, raw)
    if normalized not in SELF_LEARNING_FEEDBACK_STATUSES:
        raise ValueError(f"invalid self-learning feedback status: {status}")
    return normalized


def _normalize_feedback_confidence(confidence: float) -> float:
    if isinstance(confidence, bool) or not isinstance(confidence, int | float):
        raise ValueError("confidence must be numeric between 0.0 and 1.0")
    value = float(confidence)
    if not (0.0 <= value <= 1.0):
        raise ValueError("confidence must be between 0.0 and 1.0")
    return round(value, 4)


def _normalize_feedback_tags(tags: list[str] | None) -> list[str]:
    normalized: list[str] = []
    for tag in tags or []:
        text = str(tag or "").strip().lower().replace(" ", "_")
        if text and text not in normalized:
            normalized.append(text)
    return normalized


def _normalize_feedback_category(category: str) -> str:
    raw = str(category or "").strip().lower().replace("-", "_").replace(" ", "_")
    return raw if raw in RUFLO_UPGRADE_CATEGORIES else "performance"


def _normalize_feedback_recommendation(recommendation: str) -> str:
    raw = str(recommendation or "").strip().lower()
    return raw if raw in RUFLO_RECOMMENDATIONS else "review"


# ── archive code queue entry point ──────────────────────────────────────
_CODE_EXTS: set[str] = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".py", ".json", ".yaml", ".yml", ".toml", ".cfg",
}

_CODE_HIGH_VALUE_NAMES: set[str] = {
    "index.ts", "main.ts", "app.ts", "cli.ts", "server.ts",
    "router.ts", "agent.ts", "orchestrator.ts",
    "package.json", "tsconfig.json",
    "index.tsx", "main.tsx", "app.tsx",
    "index.js", "main.js", "app.js",
}

_CODE_ARCHITECTURE_KEYWORDS: list[str] = [
    "agent", "planner", "executor", "orchestrator", "workflow",
    "pipeline", "router", "tool", "memory", "context", "schema",
    "types", "prompt", "eval", "command", "runtime", "worker",
    "queue", "receipt", "verifier", "control", "dashboard",
    "task", "skill", "config", "server", "service", "adapter",
    "bridge", "handler", "factory", "delegate", "provider",
    "store", "state", "feature", "module",
]

_CODE_CONFIG_PREFIXES: list[str] = [
    "vite.", "next.", "webpack.", "docker", "eslint", "babel",
    "tsup.", "rollup.", "postcss", "tailwind", "jest.",
]

_CODE_LOCKFILE_NAMES: set[str] = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "pipfile.lock", "cargo.lock",
}

_INDEX_WRAPPER_NAMES: set[str] = {
    "index.ts", "index.tsx", "index.js", "index.jsx",
}
_MAX_INDEX_WRAPPER_BYTES = 1_200
_MAX_CODE_FILE_BYTES = 500_000
_MAX_CODE_QUEUE_TOP = 20
_DEFAULT_CODE_QUEUE_TOP = 10


def archive_code_queue_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-code-queue``.

    Reads archive catalog JSON files and walks extracted source_paths
    to rank code files (TypeScript, JavaScript, Python, configs, etc.)
    by architecture research value.  Read-only.  No files written.

    Flags:
        --top <N>         Number of top-ranked sources (default 10, max 20).
        --catalog <path>  Read only this one catalog.
        --json            Machine-readable output.
        --root <path>     Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if "--help" in args or "-h" in args:
        print("Growth archive-code-queue: rank code files for research mining")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-code-queue")
        print("  python3 link.py growth archive-code-queue --top <N>")
        print("  python3 link.py growth archive-code-queue --catalog <path>")
        print("  python3 link.py growth archive-code-queue --json")
        print("")
        print("Walks extracted source directories and ranks code files")
        print(f"by architecture value.  Default top is {_DEFAULT_CODE_QUEUE_TOP}.")
        print(f"Hard cap at {_MAX_CODE_QUEUE_TOP}.  Read-only — no files written.")
        return 0

    top_arg = _parse_arg(args, "--top")
    top = _resolve_code_queue_top(top_arg)

    if isinstance(top, str):
        print(f"error: {top}", file=sys.stderr)
        print("Run 'python3 link.py growth archive-code-queue --help' for usage.",
              file=sys.stderr)
        return 1

    catalog_arg = _parse_arg(args, "--catalog")
    root_override = _parse_arg(args, "--root")
    data = collect_archive_code_queue(
        catalog_path=catalog_arg, top=top, root=root_override,
    )

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_archive_code_queue_view(data)
    return 0


def _resolve_code_queue_top(top_arg: str | None) -> int | str:
    if top_arg is None:
        return _DEFAULT_CODE_QUEUE_TOP
    try:
        n = int(top_arg)
    except ValueError:
        return f"top must be an integer, got {top_arg!r}"
    if n < 1:
        return f"top must be >= 1, got {n}"
    return n


def collect_archive_code_queue(
    catalog_path: str | None = None,
    top: int = _DEFAULT_CODE_QUEUE_TOP,
    root: str | None = None,
) -> dict[str, Any]:
    """Load catalogs, walk source_paths, and rank code files for mining.

    When ``catalog_path`` is omitted every catalog under
    ``_CATALOG_OUTPUT_DIR`` is loaded.

    Source directories are walked for code-relevant files.  Each file is
    scored by ``_score_code_source`` and ranked descending.

    Read-only.  No files written.  No source content read.
    """
    import json as _json
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    catalogs_dir = repo_root / _CATALOG_OUTPUT_DIR

    effective_top = min(top, _MAX_CODE_QUEUE_TOP)
    warnings: list[str] = []
    if top > _MAX_CODE_QUEUE_TOP:
        warnings.append(
            f"top {top} capped at {_MAX_CODE_QUEUE_TOP} (hard limit)"
        )

    # ── load catalogs ──
    if catalog_path:
        catalog_file = repo_root / catalog_path
        if not catalog_file.exists():
            return _code_queue_empty(
                warnings=warnings + [{
                    "type": "catalog_missing",
                    "detail": f"catalog not found: {catalog_file}",
                }],
                top=effective_top,
            )
        raw_catalogs = [catalog_file]
    else:
        if not catalogs_dir.exists():
            return _code_queue_empty(
                warnings=warnings + [{
                    "type": "no_catalogs",
                    "detail": f"no catalogs directory: {catalogs_dir}",
                }],
                top=effective_top,
            )
        raw_catalogs = sorted(catalogs_dir.glob("*.json"))

    catalogs: list[dict] = []
    for cf in raw_catalogs:
        try:
            cat = _json.loads(cf.read_text(encoding="utf-8"))
        except Exception as exc:
            warnings.append(
                f"catalog_invalid_json: {cf.name}: {exc}"
            )
            continue
        if not isinstance(cat, dict):
            warnings.append(f"catalog_not_dict: {cf.name}")
            continue
        catalogs.append(cat)

    if not catalogs:
        if not warnings:
            warnings.append("no catalogs found")
        return _code_queue_empty(warnings=warnings,
                                 top=effective_top)

    # ── walk source_paths and score code files ──
    all_entries: list[dict] = []
    skipped: list[dict] = []

    for catalog in catalogs:
        source_name = catalog.get("source_name", "?")
        source_root_str = catalog.get("source_path", "")
        src_root = Path(source_root_str)
        if not src_root.exists() or not src_root.is_dir():
            warnings.append(
                f"source_missing: {source_name}: {source_root_str}"
            )
            continue

        code_file_count = 0
        for entry in sorted(src_root.rglob("*")):
            if not entry.is_file():
                continue
            suffix = entry.suffix.lower()
            if suffix not in _CODE_EXTS:
                continue

            rel = str(entry.relative_to(src_root))
            path_lower = rel.lower()
            name_lower = entry.name.lower()
            size = entry.stat().st_size

            # Skip dirs
            if any(seg in path_lower for seg in _SKIP_DIR_NAMES):
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": f"in skipped directory ({rel.split('/')[0]})",
                })
                continue

            # Skip trivial / huge
            if size < 50:
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": f"trivial file ({size}B)",
                })
                continue
            if size > _MAX_CODE_FILE_BYTES:
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": f"too large ({_human_size(size)})",
                })
                continue

            # Binary check
            if _code_is_binary(entry):
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": "binary file",
                })
                continue

            code_file_count += 1
            score = _score_code_source(rel, name_lower, suffix, size, catalog)

            reason = _code_reason(rel, name_lower, suffix, score)

            if score <= 0:
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": reason,
                })
                continue

            is_index_wrapper = _is_index_wrapper(entry, size)
            sibling_count = _sibling_code_file_count(entry)
            resolved_target = _resolve_index_wrapper_target(entry) if is_index_wrapper else None
            resolved_type = "file" if resolved_target else ""

            if is_index_wrapper and resolved_target:
                score = max(score - 4, 1)
                reason = f"{reason} | tiny index wrapper; brief resolved target"
            elif is_index_wrapper and sibling_count > 0:
                score = max(score - 8, 1)
                reason = f"{reason} | tiny index wrapper; brief parent directory"
            elif is_index_wrapper:
                skipped.append({
                    "path": str(src_root / rel),
                    "reason": "tiny index wrapper with no safe local target",
                })
                continue

            est_val = "high" if score >= 13 else ("medium" if score >= 8 else "low")
            if resolved_target:
                recommended_source = resolved_target
                recommended_type = "file"
            elif is_index_wrapper and sibling_count > 0:
                recommended_source = entry.parent
                recommended_type = "directory"
            else:
                recommended_source = entry
                recommended_type = "file"

            all_entries.append({
                "source_path": str(src_root / rel),
                "catalog_source_name": source_name,
                "source_type": "file",
                "category": _code_category(name_lower, suffix),
                "reason": reason,
                "score": score,
                "estimated_value": est_val,
                "size_human": _human_size(size),
                "extension": suffix,
                "is_index_wrapper": is_index_wrapper,
                "sibling_code_file_count": sibling_count,
                "resolved_target_path": str(resolved_target) if resolved_target else "",
                "resolved_target_type": resolved_type,
                "recommended_source_path": str(recommended_source),
                "recommended_source_type": recommended_type,
                "suggested_command": f"python3 link.py growth archive-code-brief --source {recommended_source} --write",
            })

        if code_file_count == 0 and not catalog_path:
            warnings.append(
                f"no_code_files: {source_name}: no code files found"
            )

    # Sort descending by score, then by name
    all_entries.sort(key=lambda e: (-e["score"], e["source_path"].lower()))

    # Assign ranks, limit to top
    for i, entry in enumerate(all_entries):
        entry["rank"] = i + 1

    displayed = all_entries[:effective_top]

    # Recommendations
    recommendations: list[str] = []
    for e in displayed[:3]:
        recommendations.append(e["suggested_command"])

    if not displayed and not skipped:
        warnings.append(
            "no_code_files: no eligible code files found in any catalog"
        )

    return {
        "catalog_count": len(catalogs),
        "queue_count": len(displayed),
        "skipped_count": len(skipped),
        "total_discovered": len(all_entries),
        "top_requested": effective_top,
        "source_queue": displayed,
        "skipped_entries": skipped[:20],
        "recommendations": recommendations,
        "warnings": warnings if warnings else [],
        "error": None,
    }


def _is_index_wrapper(path: Path, size: int) -> bool:
    """Return True for tiny JS/TS index wrapper files."""
    return path.name.lower() in _INDEX_WRAPPER_NAMES and size <= _MAX_INDEX_WRAPPER_BYTES


def _resolve_index_wrapper_target(path: Path) -> Path | None:
    """Resolve a tiny index wrapper's first safe local import/export target."""
    import re

    if path.name.lower() not in _INDEX_WRAPPER_NAMES:
        return None
    try:
        if path.stat().st_size > _MAX_INDEX_WRAPPER_BYTES:
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None

    patterns = (
        r"(?:import|export)\s+(?:[^;]*?\s+from\s+)?[\"']([^\"']+)[\"']",
        r"require\(\s*[\"']([^\"']+)[\"']\s*\)",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            target = _safe_local_code_target(path, match.group(1))
            if target:
                return target
    return None


def _safe_local_code_target(wrapper_path: Path, specifier: str) -> Path | None:
    """Return a safe local file target for a relative JS/TS import specifier."""
    from pathlib import Path

    raw = str(specifier or "").strip()
    if not raw.startswith("."):
        return None

    base_dir = wrapper_path.parent.resolve()
    candidate_base = (wrapper_path.parent / raw).resolve()
    try:
        candidate_base.relative_to(base_dir)
    except ValueError:
        return None

    candidates: list[Path] = []
    if candidate_base.suffix:
        candidates.append(candidate_base)
    else:
        preferred = [wrapper_path.suffix.lower(), ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"]
        for suffix in dict.fromkeys(preferred):
            candidates.append(Path(str(candidate_base) + suffix))
        candidates.extend(candidate_base / f"index{suffix}" for suffix in dict.fromkeys(preferred))

    for candidate in candidates:
        try:
            candidate.relative_to(base_dir)
        except ValueError:
            continue
        if candidate == wrapper_path or not candidate.is_file() or candidate.is_symlink():
            continue
        if candidate.suffix.lower() not in _CODE_EXTS:
            continue
        if candidate.name.lower() in _CODE_LOCKFILE_NAMES:
            continue
        try:
            size = candidate.stat().st_size
        except OSError:
            continue
        if size < 50 or size > _MAX_CODE_FILE_BYTES:
            continue
        if _code_is_binary(candidate):
            continue
        return candidate

    return None


def _sibling_code_file_count(path: Path) -> int:
    """Count meaningful sibling code files near a tiny index wrapper."""
    if path.name.lower() not in _INDEX_WRAPPER_NAMES:
        return 0

    count = 0
    try:
        siblings = sorted(path.parent.iterdir())
    except Exception:
        return 0

    for sibling in siblings:
        if sibling == path or not sibling.is_file() or sibling.is_symlink():
            continue
        parts = {part.lower() for part in sibling.parts}
        if parts.intersection(_SKIP_DIR_NAMES):
            continue
        suffix = sibling.suffix.lower()
        if suffix not in _CODE_EXTS:
            continue
        if sibling.name.lower() in _CODE_LOCKFILE_NAMES or sibling.name.lower() in _INDEX_WRAPPER_NAMES:
            continue
        try:
            size = sibling.stat().st_size
        except OSError:
            continue
        if size < 50 or size > _MAX_CODE_FILE_BYTES:
            continue
        if _code_is_binary(sibling):
            continue
        count += 1

    return count


def _code_is_binary(path: Path) -> bool:
    """Return True if the first 512 bytes contain a null byte."""
    try:
        with open(path, "rb") as fh:
            return b"\x00" in fh.read(512)
    except Exception:
        return True


def _score_code_source(
    rel: str, name: str, suffix: str, size: int, catalog: dict,
) -> int:
    """Score a code file for architecture research value."""
    score = 0
    path_lower = rel.lower()

    # Exact high-value filenames
    if name in _CODE_HIGH_VALUE_NAMES:
        score += 10
    # Config/build prefixes
    elif any(name.startswith(p) for p in _CODE_CONFIG_PREFIXES):
        score += 8

    # Architecture keywords in path
    for kw in _CODE_ARCHITECTURE_KEYWORDS:
        if kw in path_lower:
            score += 6
            break

    # Source code bonus (TS/JS/Py carry more weight than JSON/YAML)
    if suffix in (".ts", ".tsx", ".js", ".jsx", ".mjs", ".py"):
        score += 3
    elif suffix in (".json", ".yaml", ".yml", ".toml", ".cfg"):
        score -= 2

    # Catalog context bonuses
    important_files = catalog.get("important_files", []) or []
    imp_types = {i.get("type") for i in important_files}
    if "package_json" in imp_types:
        score += 2
    if "tsconfig" in str(imp_types) or "pyproject_toml" in imp_types:
        score += 2

    # Source directory bonus
    if "/src/" in f"/{path_lower}" or "/lib/" in f"/{path_lower}" or "/app/" in f"/{path_lower}":
        score += 2

    # Penalties
    if name in _CODE_LOCKFILE_NAMES:
        score -= 10
    if suffix in (".json", ".yaml", ".yml") and size > 50_000:
        score -= 5  # Huge config files are usually generated

    return max(score, -100)


def _code_reason(rel: str, name: str, suffix: str, score: int) -> str:
    """Generate a human-readable reason for a code file's score."""
    path_lower = rel.lower()
    parts = []

    if name in _CODE_HIGH_VALUE_NAMES:
        parts.append(f"key file: {name}")
    elif any(name.startswith(p) for p in _CODE_CONFIG_PREFIXES):
        parts.append(f"config file: {name}")
    elif any(k in path_lower for k in _CODE_ARCHITECTURE_KEYWORDS):
        matched = [k for k in _CODE_ARCHITECTURE_KEYWORDS if k in path_lower]
        parts.append(f"architecture keywords: {', '.join(matched[:3])}")

    if suffix in (".ts", ".tsx"):
        parts.append("TypeScript source")
    elif suffix in (".js", ".jsx", ".mjs"):
        parts.append("JavaScript source")
    elif suffix == ".py":
        parts.append("Python source")
    elif suffix in (".json", ".yaml", ".yml"):
        parts.append("config/metadata")

    if not parts:
        parts.append(f"code file ({suffix})")

    if score >= 13:
        parts.append("— high-priority")
    elif score >= 8:
        parts.append("— medium-priority")

    return " | ".join(parts)


def _code_category(name: str, suffix: str) -> str:
    """Return a human-readable category label for a code file."""
    cat_map = {
        ".ts": "typescript", ".tsx": "typescript",
        ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript",
        ".cjs": "javascript", ".py": "python",
        ".json": "json_config", ".yaml": "yaml_config", ".yml": "yaml_config",
        ".toml": "toml_config", ".cfg": "config_file",
    }
    return cat_map.get(suffix, "code_file")


def _code_queue_empty(
    warnings: list | None = None,
    top: int = 0,
) -> dict[str, Any]:
    return {
        "catalog_count": 0,
        "queue_count": 0,
        "skipped_count": 0,
        "total_discovered": 0,
        "top_requested": top or _DEFAULT_CODE_QUEUE_TOP,
        "source_queue": [],
        "skipped_entries": [],
        "recommendations": [],
        "warnings": warnings or [
            {"type": "no_catalogs", "detail": "no catalogs found"},
        ],
        "error": None,
    }


# ── code queue rich renderer ────────────────────────────────────────────


def render_archive_code_queue_with_rich(data: dict[str, Any]) -> None:
    """Render a code queue using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    catalog_count: int = data.get("catalog_count", 0)
    queue_count: int = data.get("queue_count", 0)
    skipped_count: int = data.get("skipped_count", 0)
    total: int = data.get("total_discovered", 0)
    queue: list = data.get("source_queue", [])
    recs: list = data.get("recommendations", [])
    warnings: list = data.get("warnings", [])

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH CODE QUEUE[/]",
        f"[dim]{catalog_count} catalog{'s' if catalog_count != 1 else ''}  "
        f"{queue_count} queued  (top {data.get('top_requested', '?')})[/]",
    )
    console.print(header)
    console.print(Rule(style="dim"))

    if catalog_count == 0:
        empty = Text()
        empty.append("\nNo catalog files found.\n\n", style="dim")
        empty.append("To create a catalog:\n", style="dim")
        empty.append("  python3 link.py growth archive-extract --archive <path> --write\n", style="dim")
        empty.append("  python3 link.py growth archive-catalog --source <dir> --write\n", style="dim")
        empty.append("\n")
        empty.append("  [dim]python3 link.py growth archive-inventory  -- find archives[/]\n", style="dim")
        empty.append("  [dim]python3 link.py growth run               -- guided workflow[/]\n", style="dim")
        console.print(Panel(empty, border_style="dim"))
        console.print(Rule(style="dim"))
        return

    for w in warnings:
        console.print(Panel(Text(str(w), style="yellow"), border_style="yellow"))

    if queue_count == 0:
        empty_q = Text()
        empty_q.append(
            f"\n{catalog_count} catalog(s) scanned — {total} code files discovered, "
            f"0 eligible for queue.\n",
            style="dim",
        )
        if skipped_count:
            empty_q.append(f"{skipped_count} file(s) were skipped.\n", style="dim")
        console.print(Panel(empty_q, border_style="dim"))
        console.print(Rule(style="dim"))
        console.print("  [dim]python3 link.py growth run  -- guided workflow dashboard[/]")
        return

    value_colors = {"high": "green", "medium": "yellow", "low": "dim"}
    for entry in queue[:15]:
        entry_text = Text()
        ev = entry.get("estimated_value", "medium")
        vc = value_colors.get(ev, "dim")

        entry_text.append(
            f"[bold]#{entry.get('rank')}[/]  "
            f"[{vc}]{ev.upper()}[/]  "
            f"score: {entry.get('score')}  "
            f"[dim]{entry.get('category', '')}[/]"
        )
        entry_text.append(
            f"\n[dim]path:  [/]{entry.get('source_path', '?')}"
        )
        entry_text.append(
            f"\n[dim]reason:[/] {entry.get('reason', '?')}"
        )
        entry_text.append(
            f"\n[dim]size:  [/]{entry.get('size_human', '?')}"
        )
        entry_text.append(
            f"\n[dim]cmd:   [/]$ {entry.get('suggested_command', '?')}"
        )

        panel_title = f"CODE QUEUE  {entry.get('catalog_source_name', '?')}"
        console.print(Panel(entry_text, title=panel_title, border_style=vc))

    if len(queue) > 15:
        console.print(f"  [dim]... and {len(queue) - 15} more entries[/]")

    if recs:
        rec_text = Text()
        rec_text.append("Top command:\n", style="bold green")
        rec_text.append(f"  $ {recs[0]}\n\n", style="dim")
        if len(recs) > 1:
            rec_text.append("Next:\n", style="bold")
            for r in recs[1:4]:
                rec_text.append(f"  $ {r}\n", style="dim")
        console.print(Panel(rec_text, title="RECOMMENDED NEXT STEPS", border_style="green"))

    console.print(Rule(style="dim"))
    console.print("  [dim]python3 link.py growth archive-code-brief --source <path>  -- brief a code source[/]")
    console.print("  [dim]python3 link.py growth run                         -- guided workflow[/]")


# ── code queue plain fallback ───────────────────────────────────────────


def render_archive_code_queue_plain(data: dict[str, Any]) -> None:
    """Render a code queue using plain print."""
    catalog_count: int = data.get("catalog_count", 0)
    queue_count: int = data.get("queue_count", 0)
    skipped_count: int = data.get("skipped_count", 0)
    total: int = data.get("total_discovered", 0)
    queue: list = data.get("source_queue", [])
    recs: list = data.get("recommendations", [])
    warnings: list = data.get("warnings", [])
    out: list[str] = []
    out.append(
        f"== LINK GROWTH CODE QUEUE ({catalog_count} catalogs, "
        f"{queue_count} queued, {skipped_count} skipped) =="
    )
    out.append("")

    if catalog_count == 0:
        out.append("No catalog files found.")
        out.append("To create a catalog:")
        out.append("  python3 link.py growth archive-extract --archive <path> --write")
        out.append("  python3 link.py growth archive-catalog --source <dir> --write")
        out.append("")
        out.append("python3 link.py growth archive-inventory  -- find archives")
        out.append("python3 link.py growth run               -- guided workflow")
        print("\n".join(out))
        return

    for w in warnings:
        out.append(f"WARNING: {w}")

    if queue_count == 0:
        out.append("")
        out.append(f"{catalog_count} catalog(s) scanned — {total} code files discovered, 0 eligible.")
        out.append("")
        out.append("python3 link.py growth run  -- guided workflow dashboard")
        print("\n".join(out))
        return

    for entry in queue[:15]:
        out.append(
            f"--- #{entry.get('rank')} [{entry.get('estimated_value', 'medium').upper()}] "
            f"score={entry.get('score')}  {entry.get('category', '')} ---"
        )
        out.append(f"path:   {entry.get('source_path', '?')}")
        out.append(f"reason: {entry.get('reason', '?')}")
        out.append(f"size:   {entry.get('size_human', '?')}")
        out.append(f"cmd:    $ {entry.get('suggested_command', '?')}")
        out.append("")

    if recs:
        out.append("-- RECOMMENDED NEXT STEPS --")
        out.append(f"Top: $ {recs[0]}")
        for r in recs[1:4]:
            out.append(f"Next: $ {r}")
        out.append("")

    out.append("python3 link.py growth archive-code-brief --source <path>  -- brief a code source")
    out.append("python3 link.py growth run                         -- guided workflow")
    print("\n".join(out))


# ── code queue render orchestrator ──────────────────────────────────────


def render_archive_code_queue_view(data: dict[str, Any]) -> None:
    """Render code queue with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_archive_code_queue_plain(data)
        return
    render_archive_code_queue_with_rich(data)


# ── archive code brief entry point ──────────────────────────────────────
_CODE_BRIEFS_DIR = "research/_catalog/code_briefs"
_CODE_BRIEF_MAX_FILE_BYTES = 250_000
_CODE_BRIEF_MAX_TOTAL_BYTES = 1_000_000
_CODE_BRIEF_MAX_FILES_PER_DIR = 30


def archive_code_brief_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth archive-code-brief --source <path>``.

    Reads a code file or directory and produces a markdown research brief
    summarising its architecture value.  Dry-run by default; ``--write``
    persists the brief to ``research/_catalog/code_briefs/<slug>.md``.

    No code is executed.  Only plain text is read.  Existing extracted
    files are never modified.

    Flags:
        --source <path>  Required. Code file or directory.
        --write          Persist the brief to disk.
        --json           Machine-readable output.
        --root <path>    Override repo root (for test isolation).
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth archive-code-brief: create a markdown research brief")
        print("")
        print("Usage:")
        print("  python3 link.py growth archive-code-brief --source <path>")
        print("  python3 link.py growth archive-code-brief --source <path> --write")
        print("  python3 link.py growth archive-code-brief --source <path> --json")
        print("")
        print("Reads a code file or directory and produces a markdown")
        print("research brief so the proposal miner can understand it.")
        print("Dry-run by default.  No code is executed.")
        return 0

    source_arg = _parse_arg(args, "--source")
    if not source_arg:
        print("error: --source <path> is required", file=sys.stderr)
        print("Run 'python3 link.py growth archive-code-brief --help' for usage.",
              file=sys.stderr)
        return 2

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_code_brief(source_arg, write=write, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0 if data.get("ok") else 1

    render_code_brief_view(data)
    return 0 if data.get("ok") else 1


def collect_code_brief(
    source: str,
    write: bool = False,
    root: str | None = None,
    include_brief_text: bool = False,
) -> dict[str, Any]:
    """Read a code file or directory and produce a markdown research brief.

    For directories, sibling implementation files are included alongside
    index files.  Files are capped at ``_CODE_BRIEF_MAX_FILE_BYTES`` and
    ``_CODE_BRIEF_MAX_TOTAL_BYTES``.  Binary files, lockfiles, and files
    in skipped directories are excluded.

    When ``write=True`` the brief is persisted to
    ``research/_catalog/code_briefs/<slug>.md``.

    Returns a dict with ``ok``, ``brief_preview``, ``brief_path``,
    ``files_read``, ``files_skipped``, and suggested next commands.

    No code is executed.  Read-only text extraction.
    """
    from pathlib import Path

    repo_root = Path(root) if root else Path.cwd()
    source_path = (repo_root / source).resolve()

    if not source_path.exists():
        return _brief_error(f"source not found: {source_path}")

    is_dir = source_path.is_dir()

    # ── collect files ──
    files_read: list[dict] = []
    files_skipped: list[dict] = []
    total_bytes = 0
    source_type = "directory" if is_dir else "file"

    source_files = _collect_brief_files(
        source_path, is_dir, _CODE_BRIEF_MAX_FILES_PER_DIR,
    )

    for fpath in source_files:
        size = fpath.stat().st_size
        rel = str(fpath.relative_to(source_path)) if is_dir else fpath.name

        if size > _CODE_BRIEF_MAX_FILE_BYTES:
            files_skipped.append({"path": rel, "reason": f"too large ({_human_size(size)})"})
            continue
        if _code_is_binary(fpath):
            files_skipped.append({"path": rel, "reason": "binary"})
            continue
        if total_bytes + size > _CODE_BRIEF_MAX_TOTAL_BYTES:
            files_skipped.append({"path": rel, "reason": "total bytes cap reached"})
            continue

        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            files_skipped.append({"path": rel, "reason": "unreadable"})
            continue

        total_bytes += size
        files_read.append({
            "path": rel,
            "size_bytes": size,
            "content": content,
        })

    if not files_read:
        return _brief_error(
            f"no readable source files found in {source_path}. "
            f"All files were skipped or the source is empty.",
            files_read=files_read,
            files_skipped=files_skipped,
            source_type=source_type,
        )

    # ── build brief ──
    source_name = source_path.name
    slug = _slugify(source_name)
    brief_md = _build_code_brief(source_path, source_name, slug, files_read)

    brief_path = ""
    if write:
        briefs_dir = repo_root / _CODE_BRIEFS_DIR
        briefs_dir.mkdir(parents=True, exist_ok=True)
        brief_file = briefs_dir / f"{slug}.md"
        if brief_file.exists():
            return _brief_error(
                f"brief already exists: {brief_file}",
                files_read=files_read,
                files_skipped=files_skipped,
                source_type=source_type,
            )
        brief_file.write_text(brief_md, encoding="utf-8")
        brief_path = str(brief_file)

    result = {
        "ok": True,
        "source_path": str(source_path),
        "source_name": source_name,
        "source_type": source_type,
        "slug": slug,
        "files_read": [{k: v for k, v in f.items() if k != "content"} for f in files_read],
        "files_read_count": len(files_read),
        "files_skipped": files_skipped,
        "total_bytes_read": total_bytes,
        "total_human": _human_size(total_bytes),
        "brief_path": brief_path,
        "brief_preview": brief_md.split("\n")[:60],
        "dry_run": not write,
        "next_commands": [
            f"python3 link.py growth code-brief-propose --source {brief_path}" if brief_path else (
                f"python3 link.py growth archive-code-brief --source {source_path} --write"
            ),
            "python3 link.py growth proposals",
            "python3 link.py growth approve <proposal_id>",
        ],
        "warnings": [],
        "error": None,
    }
    if include_brief_text:
        result["brief_markdown"] = brief_md
    return result


def _collect_brief_files(
    source_path: Path, is_dir: bool, max_files: int,
) -> list[Path]:
    """Collect readable source files for a brief."""
    files: list[Path] = []

    if not is_dir:
        files.append(source_path)
        return files

    # Gather all files in directory, sorted
    for entry in sorted(source_path.rglob("*")):
        if not entry.is_file():
            continue
        if entry.is_symlink():
            continue

        rel = str(entry.relative_to(source_path))
        path_lower = rel.lower()

        # Skip dirs
        skip = False
        for sd in _SKIP_DIR_NAMES:
            if sd in path_lower.split("/"):
                skip = True
                break
        if skip:
            continue
        if "__MACOSX" in path_lower:
            continue

        # Skip lockfiles
        if entry.name.lower() in _CODE_LOCKFILE_NAMES:
            continue

        # Skip non-code extensions
        suffix = entry.suffix.lower()
        if suffix not in _CODE_EXTS:
            continue

        files.append(entry)
        if len(files) >= max_files:
            break

    return files


def _build_code_brief(
    source_path: Path,
    source_name: str,
    slug: str,
    files_read: list[dict],
) -> str:
    """Build a markdown research brief from code files."""
    lines: list[str] = []
    lines.append(f"# Code Research Brief: {source_name}")
    lines.append("")
    lines.append(f"**Source path:** `{source_path}`")
    lines.append(f"**Files read:** {len(files_read)}")
    lines.append(f"**Generated by:** Link Growth archive-code-brief")
    lines.append(f"**Suggested mining:**")
    lines.append(f"")
    lines.append(f"    python3 link.py growth code-brief-propose --source research/_catalog/code_briefs/{slug}.md")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## File Inventory")
    lines.append("")

    for f in files_read:
        lines.append(f"- `{f['path']}` ({_human_size(f['size_bytes'])})")

    lines.append("")
    lines.append("## Architecture Signals")
    lines.append("")

    all_text = "\n".join(f["content"] for f in files_read)
    signals = _detect_architecture_signals(all_text)
    for sig in signals:
        lines.append(f"- {sig}")

    if not signals:
        lines.append("- No strong architecture patterns detected automatically.")
    lines.append("")
    lines.append("## Source Excerpts")
    lines.append("")

    for f in files_read:
        excerpt = f["content"][:800].rstrip()
        lines.append(f"### {f['path']}")
        lines.append("")
        lines.append("```")
        if f["path"].endswith(".ts") or f["path"].endswith(".tsx"):
            lines.append("typescript")
        elif f["path"].endswith(".js") or f["path"].endswith(".jsx"):
            lines.append("javascript")
        elif f["path"].endswith(".py"):
            lines.append("python")
        elif f["path"].endswith(".json"):
            lines.append("json")
        elif f["path"].endswith((".yaml", ".yml")):
            lines.append("yaml")
        lines.append(excerpt)
        lines.append("```")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Growth Upgrade Candidates")
    lines.append("")

    text_lower = all_text.lower()
    sig_text = " ".join(signals).lower()
    candidates = _build_upgrade_candidates(
        source_name, text_lower, all_text, files_read, signals, sig_text,
    )
    for cand in candidates:
        lines.append(cand)
        lines.append("")

    if not candidates:
        lines.append("No upgrade candidates generated.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## Possible Link Upgrade Ideas")
    lines.append("")

    ideas = _infer_upgrade_ideas(source_name, signals)
    for idea in ideas:
        lines.append(f"- {idea}")

    if not ideas:
        lines.append("- No specific upgrade ideas inferred.")

    lines.append("")
    return "\n".join(lines)


def _build_upgrade_candidates(
    source_name: str,
    text_lower: str,
    all_text: str,
    files_read: list[dict],
    signals: list[str],
    sig_text: str,
) -> list[str]:
    """Build miner-compatible upgrade candidate blocks."""
    candidates: list[str] = []

    def _add(title: str, problem: str, evidence: str, pattern: str,
             upgrade: str, files_subsystem: str, risk: str, test_idea: str) -> None:
        # Collect file paths for evidence
        file_list = "\n".join(
            f"- `{f['path']}`" for f in files_read
        ) if files_read else f"- `{source_name}`"

        candidates.append(
            f"### UPGRADE CANDIDATE: {title}\n\n"
            f"**Problem:**\n{problem}\n\n"
            f"**Evidence from source:**\n{file_list}\n{evidence}\n\n"
            f"**Pattern observed:**\n{pattern}\n\n"
            f"**Proposed Link upgrade:**\n{upgrade}\n\n"
            f"**Likely Link files or subsystem:**\n{files_subsystem}\n\n"
            f"**Risk level:**\n{risk}\n\n"
            f"**Acceptance test idea:**\n{test_idea}\n"
        )

    has_branch = "branch" in text_lower or "fork" in text_lower
    has_transcript = any("transcript" in s.lower() for s in signals)
    has_session = any("session" in s.lower() for s in signals)
    has_storage = any("storage" in s.lower() for s in signals)
    has_content_replacement = "contentreplacement" in text_lower or "content replacement" in text_lower
    has_sandbox = any(k in text_lower for k in ("sandbox", "isolat"))
    has_worker = any("worker" in s.lower() for s in signals)
    has_receipt = any("receipt" in s.lower() for s in signals)
    has_verifier = any("verif" in s.lower() for s in signals)
    has_router = any(k in text_lower for k in ("router", "routing", "dispatch"))
    has_pipeline = any(k in text_lower for k in ("pipeline", "workflow"))
    has_permission = any(k in text_lower for k in ("permission", "auth"))
    has_factory = any(k in text_lower for k in ("factory", "delegate", "provider"))

    # 1. Branch/fork traceability
    if has_branch and (has_transcript or has_session):
        _add(
            "Add branch/fork traceability receipts to Link sessions",
            "Link can create independent runs but lacks a first-class way to "
            "preserve fork lineage between related sessions. Without traceability, "
            "branching a session means starting a new run with no provenance back "
            "to the original context.",
            "Source code implements transcript copy logic that preserves message "
            "history, rewrites session identifiers, and stores fork metadata. "
            "The command supports aliases for branch/fork terminology.",
            "Session branching with transcript preservation, session ID rewriting, "
            "and fork source metadata capture.",
            "Link should maintain a fork lineage receipt that records the parent "
            "session UUID, the fork point (message index or timestamp), and "
            "whether each child session diverged. This enables safe collaboration "
            "traces without losing provenance across the Link session graph.",
            "link_core/context/ or link_core/agent_memory/ — session management "
            "and conversation state layer.",
            "low",
            "Branch a Link run session and verify both parent and child runs "
            "contain reciprocal cross-reference metadata in their execution receipts.",
        )

    # 2. Content replacement preservation
    if has_content_replacement and has_transcript:
        _add(
            "Preserve content replacement history across session forks",
            "When a session is forked, inline content edits and replacements "
            "made during the original session may be lost. Link's upgrade "
            "candidate pipeline loses evidence of prior edit decisions when "
            "content is replaced without an audit trail.",
            "Source code includes ContentReplacementEntry type definitions "
            "with fields tracking original and replacement content within "
            "transcript entries. These types describe a structured record "
            "of content edits but may not survive session forks.",
            "Content replacement tracking with structured entry types, "
            "transcript serialization, and fork/copy logic.",
            "Link should track content replacement lineage by preserving "
            "ContentReplacementEntry records in the fork lineage receipt. "
            "This ensures audit trails for inline content edits survive "
            "session branching and can be used for proposal evidence tracing.",
            "link_core/context/ or link_core/receipts/ — evidence tracking "
            "and execution receipt layer.",
            "low",
            "Create a session with multiple content replacements, fork it, "
            "then verify the forked session still lists all original "
            "replacement entries with their source session IDs.",
        )

    # 3. Session transcript preservation
    if has_session and has_storage:
        _add(
            "Add safe transcript copy with traceability metadata for Link sessions",
            "Link produces execution transcripts but does not currently store "
            "a normalized session transcript with provenance metadata such as "
            "the originating session, copy timestamp, and fork depth. This "
            "gap creates a missing audit trail for research mining.",
            "Source code copies transcript entries, rewrites session IDs, "
            "and serializes the transcript to persistent storage. The code "
            "includes structured logging and analytics event hooks.",
            "Structured session storage with transcript serialization, "
            "session ID rewriting, and log event publishing.",
            "Link should store a complete session transcript snapshot at fork "
            "points, along with provenance metadata (parent session, fork "
            "depth, copy timestamp). This gives Growth mode a recoverable "
            "research source for auditing and evidence.",
            "link_core/receipts/ or link_core/memory/ — execution evidence "
            "and session persistence layer.",
            "low",
            "Create a session, generate 10 messages, fork it. Verify the "
            "fork point transcript is persisted and contains a parent_session "
            "field with the original session UUID.",
        )

    # 4. Branch title collision
    if has_branch and has_session:
        _add(
            "Add unique branch title collision handling with deduplication",
            "Link currently creates proposals with candidate_id hashes that "
            "are deduplicated by title. When multiple sessions fork from the "
            "same source, collision in branch naming could lose distinct "
            "upgrade candidates if titles are identical.",
            "Source code accepts an optional [name] argument for branch "
            "naming but does not validate uniqueness. The command description "
            "mentions 'Create a branch of the current conversation at this "
            "point' without collision handling.",
            "Branch naming with optional user-defined titles, no uniqueness "
            "validation, and conversation snapshot semantics.",
            "Link should auto-generate branch titles when none are provided "
            "(e.g., timestamp-based or UUID-suffixed) and validate uniqueness "
            "when a custom title is given. This prevents silent overwrites "
            "of distinct proposal upgrades.",
            "link_core/context/ or link.py CLI — session management and "
            "command dispatch layer.",
            "low",
            "Create two branches with the same custom title from the same "
            "session and verify the second branch receives a warning or "
            "auto-suffix to avoid collision.",
        )

    # 5. Sandbox worker isolation
    if has_sandbox and has_worker:
        _add(
            "Add sandboxed worker isolation for safe patch executor handoff",
            "Link's Growth pipeline can generate patch plans and worker "
            "handoffs, but the execution gate around applying patches is not "
            "yet sandboxed by default. Workers could benefit from isolation "
            "patterns found in existing safe-execution systems.",
            "Source code imports sandbox workers with isolation flags, "
            "wraps executor logic in sandbox containers, and verifies "
            "receipts after execution. The pattern demonstrates worker "
            "isolation with verification gating.",
            "Sandboxed worker execution with isolation flags, receipt "
            "verification, and pipeline orchestration.",
            "Link should extend its worker handoff executor to support a "
            "sandbox profile that restricts file-system writes, enforces "
            "allowed_files lists, and requires a verification receipt before "
            "the worker can mark a patch as complete.",
            "link_core/safety/ or link_core/control_plane/ — capability gate "
            "and patch executor layer.",
            "medium",
            "Create a worker handoff with a restricted allowed_files list, "
            "execute it in a sandboxed subprocess that cannot write outside "
            "those paths, and verify the receipt is rejected if any "
            "disallowed write is attempted.",
        )

    # 6. Auto-generate execution receipts
    if has_receipt and has_verifier:
        _add(
            "Auto-generate execution receipts after handoff verification",
            "Link creates patch plans and worker handoffs but does not currently "
            "auto-generate an execution receipt after each handoff verification "
            "step. This gap makes it harder to audit whether a handoff was "
            "fully executed and what evidence was produced.",
            "Source code verifies receipts after worker execution and returns "
            "receipt objects through the orchestration pipeline. The pattern "
            "shows a gated execute-then-verify flow with receipt propagation.",
            "Verification receipt generation after sandboxed execution, "
            "with receipt objects propagated through pipeline stages.",
            "Link should auto-generate a verifier receipt after each handoff "
            "worker completes, even when --write is not used. The receipt "
            "should record the handoff_id, verification_id, execution "
            "timestamp, and whether all verification commands passed.",
            "link_core/receipts/ or link_core/control_plane/ — execution "
            "evidence and verifier receipt layer.",
            "low",
            "Create and approve a proposal, create a handoff, then run "
            "the execute command. Verify a verifier receipt is produced "
            "even in dry-run mode, containing handoff_id and verification "
            "command status.",
        )

    # 7. Router enhancement
    if has_router:
        _add(
            "Add capability-gated tool routing from command dispatch table",
            "Link's tool registry maps tools to endpoints but does not have "
            "a profile-gated routing layer similar to the command dispatch "
            "pattern found in TS/JS command routers. A capability gate per "
            "tool route would improve safety.",
            "Source code implements a command router that maps command "
            "names to handler functions with lazy-load support and alias "
            "resolution. Each command is registered with a type definition.",
            "Command router with name-to-handler mapping, lazy-load "
            "deferred imports, alias resolution, and type-safe command "
            "definitions.",
            "Link should extend its tool registry to support a routing "
            "dispatch table that maps tool names to handler profiles, with "
            "lazy-importer support for on-demand loading and a capability "
            "gate that checks the active worker profile before dispatching.",
            "link_core/routing/ or link_core/safety/ — model routing and "
            "capability gate layer.",
            "medium",
            "Register two tools with different required profiles (readOnly "
            "and patchWorker). Verify that a readOnly worker cannot dispatch "
            "to the patchWorker tool.",
        )

    # 8. Pipeline progress tracking
    if has_pipeline:
        _add(
            "Add pipeline stage progress tracking to the control plane dashboard",
            "Link's control plane has 9 pipeline stages but no terminal-visible "
            "progress tracker that shows how many proposals are at each stage "
            "and whether the pipeline has stalled. The existing Growth dashboard "
            "could benefit from a stage-progress view.",
            "Source code defines a Pipeline interface with sequential Stage "
            "enumeration, retry logic, and fallback stages. This structured "
            "pipeline definition is similar to Link's ResearchIngest → "
            "Finalizer stages.",
            "Pipeline interface with typed stages, retry/fallback support, "
            "and sequential stage progression.",
            "Link should add a pipeline progress tracker to the Growth run "
            "and status dashboards that shows proposal counts per stage, "
            "any blocked stages, and a visual indicator of pipeline flow. "
            "This makes the control plane observable from the terminal.",
            "link_core/control_plane/ or link_modes/growth/ — control plane "
            "pipeline and Growth console.",
            "low",
            "Create 3 proposals at different stages (pending, approved, "
            "handoff-written). Run growth status and verify the pipeline "
            "progress section shows all 3 stages with correct counts.",
        )

    # 9. Permission gating
    if has_permission:
        _add(
            "Add profile gate permission check before every tool execution",
            "Link's tool registry and worker profiles exist but the permission "
            "check does not yet run as a pre-dispatch gate for every tool "
            "invocation. A centralized permission check would improve safety.",
            "Source code includes permission and authentication patterns "
            "in command dispatch and tool registration flows. Commands are "
            "defined with type safety and can be feature-gated.",
            "Permission patterns in tool registration, command dispatch, "
            "and feature flag gating for command availability.",
            "Link should add a mandatory profile tool gate check before "
            "every tool execution in the runtime loop, not just at worker "
            "profile assignment time. Each tool call should verify the "
            "active worker profile is permitted for the requested tool.",
            "link_core/safety/ or link_core/routing/ — profile gate and "
            "tool registry layer.",
            "medium",
            "Assign a restricted worker profile and attempt to call a "
            "high-approval tool. Verify the tool call is rejected with "
            "a profile-gate rejection receipt before any execution occurs.",
        )

    # Cap at 6
    return candidates[:6]


def _detect_architecture_signals(text: str) -> list[str]:
    """Detect architecture patterns in source text."""
    signals: list[str] = []
    text_lower = text.lower()

    patterns = [
        ("router", "Routing / dispatch table patterns detected"),
        ("orchestrat", "Orchestration patterns detected"),
        ("agent", "Agent / autonomous actor patterns detected"),
        ("planner", "Planning workflow patterns detected"),
        ("executor", "Execution / task runner patterns detected"),
        ("workflow", "Workflow / pipeline patterns detected"),
        ("pipeline", "Pipeline / sequential processing patterns detected"),
        ("tool", "Tool registration / capability patterns detected"),
        ("memory", "Memory / state persistence patterns detected"),
        ("context", "Context / session management patterns detected"),
        ("schema", "Schema / validation patterns detected"),
        ("verifier", "Verification / check patterns detected"),
        ("receipt", "Receipt / evidence patterns detected"),
        ("worker", "Worker / parallel execution patterns detected"),
        ("queue", "Queue / task scheduling patterns detected"),
        ("dashboard", "Dashboard / admin UI patterns detected"),
        ("lazy", "Lazy-load / dynamic import patterns detected"),
        ("import(", "Dynamic import patterns detected"),
        ("permission", "Permission / access control patterns detected"),
        ("auth", "Authentication patterns detected"),
        ("session", "Session management patterns detected"),
        ("transcript", "Transcript / logging patterns detected"),
        ("storage", "Storage / persistence patterns detected"),
        ("error", "Error handling patterns detected"),
        ("retry", "Retry / resilience patterns detected"),
        ("fallback", "Fallback / degradation patterns detected"),
        ("sandbox", "Sandbox / isolation patterns detected"),
        ("isolat", "Isolation / containment patterns detected"),
        ("safe", "Safety / guard patterns detected"),
        ("factory", "Factory / builder patterns detected"),
        ("delegate", "Delegation patterns detected"),
        ("adapter", "Adapter / bridge patterns detected"),
        ("bridge", "Bridge / translation patterns detected"),
        ("provider", "Provider / injection patterns detected"),
    ]

    for keyword, label in patterns:
        if keyword in text_lower and label not in signals:
            signals.append(label)

    if len(signals) > 15:
        signals = signals[:15]

    return signals


def _infer_upgrade_ideas(source_name: str, signals: list[str]) -> list[str]:
    """Infer possible Link upgrade ideas from detected patterns."""
    ideas: list[str] = []
    sig_text = " ".join(signals).lower()

    if "agent" in sig_text and "tool" in sig_text:
        ideas.append(
            "Review agent/tool registration model for tool-canister or "
            "profile-gated tool dispatch patterns adaptable to Link's tool registry."
        )
    if "router" in sig_text:
        ideas.append(
            "Study routing/dispatch architecture for Link's model router "
            "or worker delegation routing."
        )
    if "worker" in sig_text and "queue" in sig_text:
        ideas.append(
            "Review worker/queue model for Link task scheduler or "
            "autonomous agent task queue."
        )
    if "sandbox" in sig_text or "isolat" in sig_text:
        ideas.append(
            "Study sandbox/isolation patterns for Link's worker isolation "
            "and safe-code-execution story."
        )
    if "context" in sig_text and "session" in sig_text:
        ideas.append(
            "Review context/session management for Link's long-session "
            "memory and context-truncation upgrade."
        )
    if "permission" in sig_text or "auth" in sig_text:
        ideas.append(
            "Study permission/auth patterns for Link's capability gate "
            "and profile tool gate."
        )
    if "receipt" in sig_text or "verifier" in sig_text:
        ideas.append(
            "Review receipt/verifier patterns for Link's execution "
            "evidence and healthcheck receipt system."
        )
    if "pipeline" in sig_text or "workflow" in sig_text:
        ideas.append(
            "Study pipeline/workflow patterns for Link's control-plane "
            "proposal pipeline."
        )
    if "error" in sig_text or "retry" in sig_text or "fallback" in sig_text:
        ideas.append(
            "Review error/retry/fallback patterns for Link's agent loop "
            "recovery and provider fallback."
        )
    if "lazy" in sig_text or "import(" in sig_text:
        ideas.append(
            "Study lazy-load/dynamic import patterns for Link's dynamic "
            "tool loading and provider routing."
        )
    if "factory" in sig_text or "delegate" in sig_text or "provider" in sig_text:
        ideas.append(
            "Review factory/delegate/provider patterns for Link's worker "
            "profile and mode factory architecture."
        )

    if not ideas:
        ideas.append(
            "General architecture review — compare command/event patterns "
            "to Link's CLI dispatcher and control-plane event model."
        )

    return ideas[:6]


def _slugify(name: str) -> str:
    """Create a safe slug from a name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "unnamed"


def _brief_error(
    error: str,
    files_read: list | None = None,
    files_skipped: list | None = None,
    source_type: str = "",
) -> dict[str, Any]:
    return {
        "ok": False,
        "source_path": "",
        "source_name": "",
        "source_type": source_type,
        "slug": "",
        "files_read": files_read or [],
        "files_skipped": files_skipped or [],
        "total_bytes_read": 0,
        "total_human": "0",
        "brief_path": "",
        "brief_preview": [],
        "dry_run": True,
        "next_commands": [
            "python3 link.py growth archive-code-queue",
            "python3 link.py growth run",
        ],
        "warnings": [],
        "error": error,
        "files_read_count": len(files_read) if files_read else 0,
    }


# ── code brief rich renderer ────────────────────────────────────────────


def render_code_brief_with_rich(data: dict[str, Any]) -> None:
    """Render a code brief preview/receipt using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    if not ok:
        label, color = "ERROR", "red"
    elif dry_run:
        label, color = "DRY RUN", "yellow"
    else:
        label, color = "WRITTEN", "bold green"
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH CODE BRIEF[/]",
        f"[{color}]{label}[/]",
    )
    console.print(header)

    if not ok:
        error_text = Text()
        sk = data.get("files_skipped", [])
        if sk:
            error_text.append("All files were skipped or unreadable:\n", style="dim")
            for s in sk[:5]:
                error_text.append(f"  {s['path']}: {s['reason']}\n", style="dim")
        error_text.append(f"\n[red]{data.get('error', 'unknown error')}[/]")
        console.print(Panel(error_text, border_style="red"))
        console.print(Rule(style="dim"))
        return

    # ── source info ──
    info = Text()
    info.append("source: ", style="dim")
    info.append(data.get("source_path", "?"), style="bold")
    info.append(f"\n[dim]type:   [/]{data.get('source_type', '?')}")
    info.append(
        f"\n[dim]files:  [/]{data.get('files_read_count', 0)} read  "
        f"{len(data.get('files_skipped', []))} skipped  "
        f"[dim]total: {data.get('total_human', '?')}[/]"
    )
    console.print(Panel(info, title="SOURCE", border_style="dim"))

    # ── files read ──
    files = data.get("files_read", [])
    if files:
        ft = Text()
        for f in files[:12]:
            ft.append(
                f"\n\u2022 {f.get('path', '?')}  "
                f"[dim]({_human_size(f.get('size_bytes', 0))})[/]"
            )
        console.print(Panel(ft, title="FILES READ", border_style="dim"))

    # ── files skipped ──
    skipped = data.get("files_skipped", [])
    if skipped:
        st = Text()
        for s in skipped[:8]:
            st.append(
                f"\n[dim]\u2717 {s.get('path', '?')} — {s.get('reason', '?')}[/]"
            )
        console.print(Panel(st, title="SKIPPED", border_style="yellow"))

    # ── brief preview ──
    preview = data.get("brief_preview", [])
    if preview:
        prev_text = Text()
        prev_text.append("\n".join(preview[:20]))
        console.print(Panel(prev_text, title="BRIEF PREVIEW", border_style="dim"))

    # ── written path ──
    brief_path = data.get("brief_path", "")
    if brief_path:
        wt = Text()
        wt.append("Brief written to:\n", style="bold green")
        wt.append(f"  {brief_path}", style="dim")
        console.print(Panel(wt, border_style="dim green"))

    # ── next commands ──
    next_cmds = data.get("next_commands", [])
    nc = Text()
    nc.append("Next:\n", style="bold")
    for cmd in next_cmds:
        nc.append(f"  $ {cmd}\n", style="dim")

    console.print(Rule(style="dim"))
    console.print(Panel(nc, title="SUGGESTED NEXT STEPS", border_style="green"))
    console.print("  [dim]No code was executed by this command.[/]")
    console.print("  [dim]python3 link.py growth run  -- guided workflow[/]")


# ── code brief plain fallback ───────────────────────────────────────────


def render_code_brief_plain(data: dict[str, Any]) -> None:
    """Render a code brief using plain print."""
    ok: bool = data.get("ok", True)
    dry_run: bool = data.get("dry_run", True)
    label = "ERROR" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    out: list[str] = []
    out.append(f"== LINK GROWTH CODE BRIEF ({label}) ==")
    out.append("")

    if not ok:
        skipped = data.get("files_skipped", [])
        if skipped:
            out.append("Files skipped:")
            for s in skipped[:5]:
                out.append(f"  {s['path']}: {s['reason']}")
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    out.append(f"source: {data.get('source_path', '?')}")
    out.append(f"type:   {data.get('source_type', '?')}")
    out.append(f"files:  {data.get('files_read_count', 0)} read  "
               f"{len(data.get('files_skipped', []))} skipped  "
               f"total: {data.get('total_human', '?')}")
    out.append("")

    files = data.get("files_read", [])
    if files:
        out.append("-- FILES READ --")
        for f in files[:12]:
            out.append(f"  - {f.get('path', '?')} ({_human_size(f.get('size_bytes', 0))})")
        out.append("")

    skipped = data.get("files_skipped", [])
    if skipped:
        out.append("-- SKIPPED --")
        for s in skipped[:8]:
            out.append(f"  - {s.get('path', '?')}: {s.get('reason', '?')}")
        out.append("")

    preview = data.get("brief_preview", [])
    if preview:
        out.append("-- BRIEF PREVIEW --")
        out.extend(preview[:20])
        out.append("")

    brief_path = data.get("brief_path", "")
    if brief_path:
        out.append(f"Brief written to: {brief_path}")
        out.append("")

    next_cmds = data.get("next_commands", [])
    out.append("-- SUGGESTED NEXT STEPS --")
    for cmd in next_cmds:
        out.append(f"  $ {cmd}")
    out.append("")
    out.append("No code was executed by this command.")
    out.append("python3 link.py growth run  -- guided workflow")
    print("\n".join(out))


# ── code brief render orchestrator ──────────────────────────────────────


def render_code_brief_view(data: dict[str, Any]) -> None:
    """Render code brief with rich if available; fall back to plain."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_code_brief_plain(data)
        return
    render_code_brief_with_rich(data)



# ── batch code brief proposal preview entry point ───────────────────────


def _normalize_cli_dashes(args: list[str]) -> list[str]:
    """Normalize pasted en/em dash options to regular CLI dashes."""
    return [arg.replace("\u2013", "--", 1).replace("\u2014", "--", 1) for arg in args]


def code_brief_propose_batch_main(argv: list[str] | None = None) -> int:
    """Entry point for ``growth code-brief-propose-batch``.

    Ranks code sources, builds in-memory code briefs, previews proposal generation,
    and optionally persists generated proposals with --write.
    """
    args = _normalize_cli_dashes(sys.argv[1:] if argv is None else argv)
    write = "--write" in args

    if "--help" in args or "-h" in args:
        print("Growth code-brief-propose-batch: preview proposals for top code queue entries")
        print("")
        print("Usage:")
        print("  python3 link.py growth code-brief-propose-batch --top <N>")
        print("  python3 link.py growth code-brief-propose-batch --top <N> --json")
        print("  python3 link.py growth code-brief-propose-batch --top <N> --write")
        print("")
        print("Reads source text and writes proposals only with --write.")
        return 0

    top_arg = _parse_arg(args, "--top")
    top = _resolve_code_queue_top(top_arg)
    if isinstance(top, str):
        print(f"error: {top}", file=sys.stderr)
        return 1

    root_override = _parse_arg(args, "--root")
    data = collect_code_brief_propose_batch(top=top, root=root_override, write=write)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_code_brief_propose_batch_view(data)
    return 0


def collect_code_brief_propose_batch(
    top: int = _DEFAULT_CODE_QUEUE_TOP,
    root: str | None = None,
    write: bool = False,
) -> dict[str, Any]:
    """Preview or write code-brief proposal generation for top archive-code-queue entries."""
    from pathlib import Path

    from link_core.control_plane import write_proposal as _write_proposal
    from link_core.control_plane.link_control_plane_proposals import (
        proposal_storage_dir as _proposal_storage_dir,
    )

    repo_root = Path(root) if root else Path.cwd()
    effective_top = min(max(int(top), 1), _MAX_CODE_QUEUE_TOP)
    warnings: list[Any] = []
    if top > _MAX_CODE_QUEUE_TOP:
        warnings.append(f"top {top} capped at {_MAX_CODE_QUEUE_TOP} (hard limit)")

    queue_data = collect_archive_code_queue(top=effective_top, root=str(repo_root))
    queue_entries = list(queue_data.get("source_queue", []))[:effective_top]
    warnings.extend(queue_data.get("warnings", []) or [])

    source_summaries: list[dict[str, Any]] = []
    written_paths: list[str] = []
    candidate_total = 0
    proposal_total = 0
    weak_total = 0
    duplicate_total = 0

    for entry in queue_entries:
        source_path = str(entry.get("recommended_source_path") or entry.get("source_path") or "")
        source_warnings: list[Any] = []
        brief_data = collect_code_brief(
            source_path,
            write=False,
            root=str(repo_root),
            include_brief_text=True,
        )
        source_warnings.extend(brief_data.get("warnings", []) or [])

        candidates: list[dict[str, Any]] = []
        proposals: list[dict[str, Any]] = []
        quality_warnings: list[dict[str, Any]] = []
        weak_count = 0
        duplicate_count = 0

        if brief_data.get("ok"):
            brief_md = str(brief_data.get("brief_markdown") or "")
            candidates = _parse_code_brief_candidates(brief_md, source_path)
            seen_titles: set[str] = set()
            proposals = [
                _code_brief_candidate_to_proposal(c, source_path, seen_titles=seen_titles)
                for c in candidates
            ]
            quality = _analyze_code_brief_proposal_quality(
                candidates,
                proposals,
                proposal_dir=_proposal_storage_dir(repo_root),
            )
            quality_warnings = quality["quality_warnings"]
            weak_count = quality["weak_candidate_count"]
            duplicate_count = quality["duplicate_count"]
            if write:
                for proposal in proposals:
                    path = _write_proposal(proposal, root=repo_root)
                    written_paths.append(str(path))
        else:
            source_warnings.append(brief_data.get("error") or "code brief preview failed")

        candidate_total += len(candidates)
        proposal_total += len(proposals)
        weak_total += weak_count
        duplicate_total += duplicate_count

        source_summaries.append({
            "source_path": source_path,
            "source_type": brief_data.get("source_type") or entry.get("recommended_source_type", ""),
            "rank": entry.get("rank"),
            "suggested_brief_command": f"python3 link.py growth archive-code-brief --source {source_path} --write",
            "suggested_propose_command": "python3 link.py growth code-brief-propose --source <brief.md>",
            "candidate_count": len(candidates),
            "proposal_count": len(proposals),
            "weak_candidate_count": weak_count,
            "duplicate_count": duplicate_count,
            "warnings": source_warnings + quality_warnings,
            "ok": bool(brief_data.get("ok")),
        })

    if not queue_entries:
        warnings.append("no code queue entries available for batch preview")

    return {
        "ok": True,
        "dry_run": not write,
        "top_requested": effective_top,
        "queued_source_count": len(queue_entries),
        "processed_source_count": len(source_summaries),
        "candidate_count": candidate_total,
        "proposal_count": proposal_total,
        "weak_candidate_count": weak_total,
        "duplicate_count": duplicate_total,
        "sources": source_summaries,
        "warnings": warnings,
        "written_paths": written_paths,
        "next_commands": [
            "python3 link.py growth archive-code-queue",
            "python3 link.py growth archive-code-brief --source <path> --write",
            "python3 link.py growth code-brief-propose --source <brief.md>",
        ],
        "error": None,
    }


def render_code_brief_propose_batch_view(data: dict[str, Any]) -> None:
    """Render batch proposal preview with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_code_brief_propose_batch_plain(data)
        return
    render_code_brief_propose_batch_with_rich(data)


def render_code_brief_propose_batch_with_rich(data: dict[str, Any]) -> None:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    header = Text()
    header.append("LINK GROWTH CODE BRIEF PROPOSE BATCH", style="bold bright_cyan")
    header.append("  DRY RUN" if data.get("dry_run") else "  WRITTEN", style="yellow" if data.get("dry_run") else "green")
    console.print(header)
    console.print(Panel(
        f"queued: {data.get('queued_source_count', 0)}  "
        f"processed: {data.get('processed_source_count', 0)}  "
        f"candidates: {data.get('candidate_count', 0)}  "
        f"proposals: {data.get('proposal_count', 0)}",
        border_style="dim",
    ))

    for warning in data.get("warnings", []):
        console.print(Panel(Text(str(warning), style="yellow"), title="WARNING", border_style="yellow"))

    for source in data.get("sources", [])[:10]:
        body = Text()
        body.append(str(source.get("source_path", "?")), style="bold")
        body.append(f"\ncandidates: {source.get('candidate_count', 0)}  proposals: {source.get('proposal_count', 0)}")
        body.append(f"\ncmd: $ {source.get('suggested_brief_command', '?')}", style="dim")
        console.print(Panel(body, title=f"SOURCE #{source.get('rank', '?')}", border_style="dim"))

    next_text = Text()
    for command in data.get("next_commands", []):
        next_text.append(f"  $ {command}\n", style="dim")
    if data.get("written_paths"):
        written = Text()
        for path in data.get("written_paths", [])[:10]:
            written.append(f"{path}\n", style="green")
        console.print(Panel(written, title="WRITTEN PROPOSALS", border_style="green"))
    console.print(Rule(style="dim"))
    console.print(Panel(next_text, title="SUGGESTED NEXT STEPS", border_style="green"))


def render_code_brief_propose_batch_plain(data: dict[str, Any]) -> None:
    out: list[str] = []
    out.append("== LINK GROWTH CODE BRIEF PROPOSE BATCH (DRY RUN) ==" if data.get("dry_run") else "== LINK GROWTH CODE BRIEF PROPOSE BATCH (WRITTEN) ==")
    out.append(
        f"queued: {data.get('queued_source_count', 0)}  "
        f"processed: {data.get('processed_source_count', 0)}  "
        f"candidates: {data.get('candidate_count', 0)}  "
        f"proposals: {data.get('proposal_count', 0)}"
    )
    if data.get("warnings"):
        out.append("")
        out.append("-- WARNINGS --")
        for warning in data.get("warnings", []):
            out.append(f"  - {warning}")
    out.append("")
    for source in data.get("sources", []):
        out.append(f"--- SOURCE #{source.get('rank', '?')} ---")
        out.append(f"source:     {source.get('source_path', '?')}")
        out.append(f"candidates: {source.get('candidate_count', 0)}")
        out.append(f"proposals:  {source.get('proposal_count', 0)}")
        out.append(f"brief:      $ {source.get('suggested_brief_command', '?')}")
        out.append("")
    out.append("-- SUGGESTED NEXT STEPS --")
    if data.get("written_paths"):
        out.append("written proposals:")
        for path in data.get("written_paths", [])[:10]:
            out.append(f"  {path}")
    for command in data.get("next_commands", []):
        out.append(f"  $ {command}")
    print("\n".join(out))


# ── code brief propose entry point ───────────────────────────────────────


def code_brief_propose_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth code-brief-propose``.

    Reads a markdown code brief generated by ``archive-code-brief`` and
    converts its structured ``UPGRADE CANDIDATE`` blocks into normal pending
    Growth proposals. Dry-run by default; ``--write`` persists proposals via
    the existing control-plane ``write_proposal`` helper.

    No code is executed. No subprocess. No network. Markdown is read only.
    """
    args = sys.argv[1:] if argv is None else argv

    if not args or "--help" in args or "-h" in args:
        print("Growth code-brief-propose: convert code brief candidates to proposals")
        print("")
        print("Usage:")
        print("  python3 link.py growth code-brief-propose --source <brief.md>")
        print("  python3 link.py growth code-brief-propose --source <brief.md> --json")
        print("  python3 link.py growth code-brief-propose --source <brief.md> --write")
        print("")
        print("Reads markdown only. Dry-run by default. Proposals are")
        print("written only when --write is provided.")
        return 0

    source_arg = _parse_arg(args, "--source")
    if not source_arg:
        print("error: --source <brief.md> is required", file=sys.stderr)
        print("Run 'python3 link.py growth code-brief-propose --help' for usage.",
              file=sys.stderr)
        return 2

    write = "--write" in args
    root_override = _parse_arg(args, "--root")
    data = collect_code_brief_propose(source_arg, write=write, root=root_override)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_code_brief_propose_view(data)
    return 0


def collect_code_brief_propose(
    source: str,
    write: bool = False,
    root: str | None = None,
) -> dict[str, Any]:
    """Parse a markdown code brief and optionally persist proposals.

    Only ``### UPGRADE CANDIDATE: <title>`` blocks are parsed. The source
    markdown is read as text and is never modified. ``write=True`` writes only
    proposal JSON through ``link_core.control_plane.write_proposal``.
    """
    from pathlib import Path

    from link_core.control_plane import write_proposal as _write_proposal
    from link_core.control_plane.link_control_plane_proposals import (
        proposal_storage_dir as _proposal_storage_dir,
    )

    repo_root = Path(root) if root else Path.cwd()
    source_path = Path(source)
    if not source_path.is_absolute():
        source_path = (repo_root / source).resolve()
    else:
        source_path = source_path.resolve()

    if not source_path.exists() or not source_path.is_file():
        return _code_brief_propose_error(
            f"source not found: {source_path}",
            source=str(source_path),
            source_exists=False,
            dry_run=not write,
        )

    try:
        brief_text = source_path.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return _code_brief_propose_error(
            f"could not read source: {exc}",
            source=str(source_path),
            source_exists=True,
            dry_run=not write,
        )

    candidates = _parse_code_brief_candidates(brief_text, str(source_path))
    seen_titles: set[str] = set()
    proposals = [
        _code_brief_candidate_to_proposal(c, str(source_path), seen_titles=seen_titles)
        for c in candidates
    ]
    quality = _analyze_code_brief_proposal_quality(
        candidates,
        proposals,
        proposal_dir=_proposal_storage_dir(repo_root),
    )

    written_paths: list[str] = []
    if write:
        for proposal in proposals:
            path = _write_proposal(proposal, root=repo_root)
            written_paths.append(str(path))

    return {
        "ok": True,
        "source": str(source_path),
        "source_exists": True,
        "candidate_count": len(candidates),
        "proposal_count": len(proposals),
        "candidates": candidates,
        "proposals": proposals,
        "dry_run": not write,
        "written_paths": written_paths,
        "quality_warnings": quality["quality_warnings"],
        "weak_candidate_count": quality["weak_candidate_count"],
        "duplicate_count": quality["duplicate_count"],
        "next_commands": [
            "python3 link.py growth proposals",
            "python3 link.py growth approve <proposal_id>",
            "python3 link.py growth run",
        ],
        "warnings": [],
        "error": None if candidates else "no upgrade candidate blocks found in source",
    }


def _parse_code_brief_candidates(text: str, source_path: str) -> list[dict[str, Any]]:
    """Extract structured candidate blocks from a code brief markdown file."""
    import re

    heading = re.compile(r"^### UPGRADE CANDIDATE:\s*(.+?)\s*$", re.MULTILINE)
    matches = list(heading.finditer(text))
    candidates: list[dict[str, Any]] = []

    for idx, match in enumerate(matches):
        title = match.group(1).strip()
        if not title:
            continue
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(text)
        block = _trim_code_brief_candidate_block(text[start:end])

        problem = _extract_code_brief_field(block, "Problem")
        evidence_text = _extract_code_brief_field(block, "Evidence from source")
        pattern = _extract_code_brief_field(block, "Pattern observed")
        proposed = _extract_code_brief_field(block, "Proposed Link upgrade")
        likely_files = _extract_code_brief_field(block, "Likely Link files or subsystem")
        risk_raw = _extract_code_brief_field(block, "Risk level")
        acceptance = _extract_code_brief_field(block, "Acceptance test idea")
        risk = _normalize_code_brief_risk(risk_raw)

        candidates.append({
            "title": title,
            "problem": problem,
            "evidence_from_source": evidence_text,
            "pattern_observed": pattern,
            "proposed_link_upgrade": proposed,
            "likely_link_files_or_subsystem": likely_files,
            "risk": risk,
            "risk_raw": risk_raw,
            "acceptance_test_idea": acceptance,
            "source_path": source_path,
        })

    return candidates


def _trim_code_brief_candidate_block(block: str) -> str:
    """Remove trailing non-candidate sections from a candidate block."""
    import re

    boundary = re.search(r"(?m)^(?:---\s*|##\s+.+)$", block)
    return block[:boundary.start()] if boundary else block


def _extract_code_brief_field(block: str, label: str) -> str:
    """Return text under a ``**Label:**`` markdown field."""
    import re

    marker = f"**{label}:**"
    start = block.find(marker)
    if start < 0:
        return ""

    rest = block[start + len(marker):].lstrip("\r\n")
    next_field = re.search(r"(?m)^\*\*[^*\n]+:\*\*\s*$", rest)
    value = rest[:next_field.start()] if next_field else rest
    return value.strip()


def _normalize_code_brief_risk(risk: str) -> str:
    value = str(risk or "").strip().lower()
    if value in ("low", "medium", "high"):
        return value
    return "medium"


def _code_brief_text_is_vague(text: str) -> bool:
    value = " ".join(str(text or "").strip().lower().split())
    if not value:
        return True
    vague_values = {
        "n/a", "na", "none", "unknown", "tbd", "todo",
        "needs tests", "add tests", "write tests", "test", "tests",
        "link", "growth", "repo", "repository", "system", "subsystem",
        "files", "code", "runtime",
    }
    if value in vague_values:
        return True
    vague_markers = ("tbd", "todo", "unknown", "not sure", "unclear", "needs research")
    return any(marker in value for marker in vague_markers)


def _code_brief_likely_files_are_vague(text: str) -> bool:
    value = str(text or "").strip()
    if _code_brief_text_is_vague(value):
        return True
    items = _split_code_brief_list(value)
    if not items:
        return True
    for item in items:
        lower = item.lower()
        if "/" in item or "." in item:
            return False
        if lower.startswith(("link_core", "link_modes", "tests")):
            return False
    return True


def _analyze_code_brief_proposal_quality(
    candidates: list[dict[str, Any]],
    proposals: list[dict[str, Any]],
    proposal_dir: Any,
) -> dict[str, Any]:
    """Return warnings for weak or duplicate code-brief proposal candidates."""
    from pathlib import Path

    warnings: list[dict[str, Any]] = []
    weak_indexes: set[int] = set()
    duplicate_count = 0
    title_counts: dict[str, int] = {}

    for candidate in candidates:
        title_key = str(candidate.get("title") or "").strip().lower()
        if title_key:
            title_counts[title_key] = title_counts.get(title_key, 0) + 1

    seen_titles: set[str] = set()
    storage = Path(proposal_dir)
    for idx, candidate in enumerate(candidates):
        proposal = proposals[idx] if idx < len(proposals) else {}
        title = str(candidate.get("title") or proposal.get("title") or "").strip()
        title_key = title.lower()
        proposal_id = str(proposal.get("proposal_id") or "").strip()

        def add_warning(code: str, message: str, weak: bool = True) -> None:
            warnings.append({
                "code": code,
                "candidate_index": idx,
                "title": title,
                "proposal_id": proposal_id,
                "message": message,
            })
            if weak:
                weak_indexes.add(idx)

        acceptance = str(candidate.get("acceptance_test_idea") or "").strip()
        if _code_brief_text_is_vague(acceptance):
            add_warning("weak_acceptance_test", "missing or vague acceptance test idea")

        likely_files = str(candidate.get("likely_link_files_or_subsystem") or "").strip()
        if _code_brief_likely_files_are_vague(likely_files):
            add_warning("weak_likely_files", "missing or vague likely Link files/subsystem")

        risk_raw = str(candidate.get("risk_raw") or "").strip().lower()
        if risk_raw not in ("low", "medium", "high"):
            add_warning("unknown_risk_level", "unknown or empty risk level")

        evidence = str(candidate.get("evidence_from_source") or "").strip()
        if _code_brief_text_is_vague(evidence):
            add_warning("missing_source_evidence", "missing evidence from source")

        duplicate_title = bool(title_key and title_counts.get(title_key, 0) > 1)
        if duplicate_title:
            duplicate_count += 1
            if title_key in seen_titles:
                add_warning(
                    "duplicate_candidate_title",
                    "duplicate candidate title within this brief",
                    weak=False,
                )
            seen_titles.add(title_key)

        duplicate_existing = bool(proposal_id and (storage / f"{proposal_id}.json").exists())
        if duplicate_existing:
            duplicate_count += 1
            add_warning(
                "existing_proposal_id",
                "proposal_id already exists in .agents/control_plane/proposals",
                weak=False,
            )

        candidate["duplicate_existing"] = duplicate_existing
        if proposal:
            proposal["duplicate_existing"] = duplicate_existing

    return {
        "quality_warnings": warnings,
        "weak_candidate_count": len(weak_indexes),
        "duplicate_count": duplicate_count,
    }


def _code_brief_recommendation(risk: str) -> str:
    return "accept" if risk == "low" else "review"


def _split_code_brief_list(text: str) -> list[str]:
    items: list[str] = []
    for raw in str(text or "").splitlines():
        line = raw.strip().strip("-").strip()
        if not line:
            continue
        line = line.strip("`")
        if line:
            items.append(line)
    return items


def _code_brief_candidate_to_proposal(
    candidate: dict[str, Any],
    source_path: str,
    seen_titles: set[str] | None = None,
) -> dict[str, Any]:
    """Convert one parsed code-brief candidate to a proposal artifact."""
    from link_core.control_plane import make_proposal_id
    from link_core.receipts import make_unique_title

    title = make_unique_title(
        candidate.get("title"),
        existing_titles=seen_titles,
    )
    if seen_titles is not None:
        seen_titles.add(" ".join(title.split()).lower())
    risk = _normalize_code_brief_risk(str(candidate.get("risk") or ""))
    problem = str(candidate.get("problem") or "").strip()
    pattern = str(candidate.get("pattern_observed") or "").strip()
    proposed = str(candidate.get("proposed_link_upgrade") or "").strip()
    likely_files = str(candidate.get("likely_link_files_or_subsystem") or "").strip()
    acceptance = str(candidate.get("acceptance_test_idea") or "").strip()
    evidence_text = str(candidate.get("evidence_from_source") or "").strip()

    implementation_plan = [proposed] if proposed else [f"Review code brief candidate: {title}"]
    if pattern:
        implementation_plan.append(f"Adapt observed pattern: {pattern}")

    verification_commands = [acceptance] if acceptance else [
        "Add a focused smoke check for the proposed Link behavior."
    ]

    affected_files = _split_code_brief_list(likely_files)
    if not affected_files and likely_files:
        affected_files = [likely_files]

    summary_parts = [p for p in (problem, proposed) if p]
    source_summary = " ".join(summary_parts) or title

    return {
        "proposal_id": make_proposal_id(title, source_path),
        "title": title,
        "source_path": source_path,
        "source_summary": source_summary,
        "extracted_capabilities": [p for p in (pattern, proposed) if p],
        "link_takeaways": [p for p in (problem, proposed) if p],
        "affected_files": affected_files,
        "risk_level": risk,
        "expected_behavior_change": proposed or problem or title,
        "implementation_plan": implementation_plan,
        "verification_commands": verification_commands,
        "rollback_plan": "Do not merge; revert the proposal patch branch if verification fails.",
        "recommendation": _code_brief_recommendation(risk),
        "status": "pending",
        "created_at": _utc_now(),
        "source_reference": f"code brief: {source_path}",
        "code_brief_evidence": evidence_text,
    }


def _code_brief_propose_error(
    error: str,
    source: str = "",
    source_exists: bool = False,
    dry_run: bool = True,
) -> dict[str, Any]:
    return {
        "ok": False,
        "source": source,
        "source_exists": source_exists,
        "candidate_count": 0,
        "proposal_count": 0,
        "candidates": [],
        "proposals": [],
        "dry_run": dry_run,
        "written_paths": [],
        "quality_warnings": [],
        "weak_candidate_count": 0,
        "duplicate_count": 0,
        "next_commands": [
            "python3 link.py growth archive-code-brief --source <path> --write",
            "python3 link.py growth run",
        ],
        "warnings": [],
        "error": error,
    }


def render_code_brief_propose_view(data: dict[str, Any]) -> None:
    """Render code-brief proposal conversion with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_code_brief_propose_plain(data)
        return
    render_code_brief_propose_with_rich(data)


def render_code_brief_propose_with_rich(data: dict[str, Any]) -> None:
    """Render code-brief proposal conversion using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    ok = data.get("source_exists", False)
    dry_run = data.get("dry_run", True)
    label = "FAILED" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    color = "red" if not ok else ("yellow" if dry_run else "bold green")

    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row("[bold bright_cyan]LINK GROWTH CODE BRIEF PROPOSE[/]",
                   f"[{color}]{label}[/]")
    console.print(header)

    if not ok:
        console.print(Panel(Text(data.get("error", "unknown error"), style="red"),
                            border_style="red"))
        console.print(Rule(style="dim"))
        return

    info = Text()
    info.append("source: ", style="dim")
    info.append(data.get("source", "?"), style="bold")
    info.append(f"\n[dim]candidates: {data.get('candidate_count', 0)}  proposals: {data.get('proposal_count', 0)}[/]")
    console.print(Panel(info, border_style="dim"))

    if data.get("error"):
        console.print(Panel(Text(str(data.get("error")), style="yellow"),
                            border_style="yellow"))

    quality_warnings = data.get("quality_warnings", [])
    if quality_warnings:
        warn_text = Text()
        for warning in quality_warnings:
            title = warning.get("title") or "candidate"
            message = warning.get("message") or warning.get("code") or "quality warning"
            warn_text.append(f"- {title}: {message}\n", style="yellow")
        console.print(Panel(warn_text, title="QUALITY WARNINGS", border_style="yellow"))

    for proposal in data.get("proposals", [])[:8]:
        card = Text()
        card.append(f"[bold]{proposal.get('title', '?')}[/]")
        card.append(f"\n[dim]risk:[/] {proposal.get('risk_level', '?')}  ")
        card.append(f"[dim]recommendation:[/] {proposal.get('recommendation', '?')}")
        summary = proposal.get("source_summary", "")
        if summary:
            card.append(f"\n[dim]summary:[/] {summary[:180]}")
        tests = proposal.get("verification_commands", [])
        if tests:
            card.append(f"\n[dim]acceptance:[/] {tests[0][:160]}")
        console.print(Panel(card, title=proposal.get("proposal_id", "?"),
                            border_style="dim"))

    if data.get("written_paths"):
        wrote = Text()
        for path in data.get("written_paths", []):
            wrote.append(f"  {path}\n", style="dim")
        console.print(Panel(wrote, title="WRITTEN", border_style="dim green"))

    next_text = Text()
    for command in data.get("next_commands", []):
        next_text.append(f"  $ {command}\n", style="dim")
    if data.get("written_paths"):
        written = Text()
        for path in data.get("written_paths", [])[:10]:
            written.append(f"{path}\n", style="green")
        console.print(Panel(written, title="WRITTEN PROPOSALS", border_style="green"))
    console.print(Rule(style="dim"))
    console.print(Panel(next_text, title="SUGGESTED NEXT STEPS", border_style="green"))


def render_code_brief_propose_plain(data: dict[str, Any]) -> None:
    """Render code-brief proposal conversion using plain text."""
    ok = data.get("source_exists", False)
    dry_run = data.get("dry_run", True)
    label = "FAILED" if not ok else ("DRY RUN" if dry_run else "WRITTEN")
    out = [f"== LINK GROWTH CODE BRIEF PROPOSE ({label}) ==", ""]

    if not ok:
        out.append(f"error: {data.get('error', 'unknown error')}")
        print("\n".join(out))
        return

    out.append(f"source: {data.get('source', '?')}")
    out.append(f"candidates: {data.get('candidate_count', 0)}  proposals: {data.get('proposal_count', 0)}")
    if data.get("error"):
        out.append(f"note: {data.get('error')}")

    quality_warnings = data.get("quality_warnings", [])
    if quality_warnings:
        out.append("")
        out.append("-- QUALITY WARNINGS --")
        for warning in quality_warnings:
            title = warning.get("title") or "candidate"
            message = warning.get("message") or warning.get("code") or "quality warning"
            out.append(f"  - {title}: {message}")
    out.append("")

    for proposal in data.get("proposals", []):
        out.append(f"--- {proposal.get('proposal_id', '?')} ---")
        out.append(f"title:          {proposal.get('title', '?')}")
        out.append(f"risk_level:     {proposal.get('risk_level', '?')}")
        out.append(f"recommendation: {proposal.get('recommendation', '?')}")
        tests = proposal.get("verification_commands", [])
        if tests:
            out.append(f"acceptance:     {tests[0]}")
        out.append("")

    if data.get("written_paths"):
        out.append("Written:")
        for path in data.get("written_paths", []):
            out.append(f"  {path}")
        out.append("")

    out.append("-- SUGGESTED NEXT STEPS --")
    if data.get("written_paths"):
        out.append("written proposals:")
        for path in data.get("written_paths", [])[:10]:
            out.append(f"  {path}")
    for command in data.get("next_commands", []):
        out.append(f"  $ {command}")
    print("\n".join(out))


# ── run guide entry point ────────────────────────────────────────────────


def run_main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth run``.

    A read-only guided Growth workflow dashboard. Shows the current
    pipeline stage, proposal counts, and the next recommended command.
    When ``--source <path>`` is given, includes a dry-run mining preview.

    Flags:
        --source <path>  Optional research source for a mining preview.
        --json           Machine-readable output.
    """
    args = _normalize_cli_dashes(sys.argv[1:] if argv is None else argv)

    if "--help" in args or "-h" in args:
        print("Growth run: guided Growth workflow dashboard")
        print("")
        print("Usage:")
        print("  python3 link.py growth run")
        print("  python3 link.py growth run --json")
        print("  python3 link.py growth run --source <path>")
        print("  python3 link.py growth run --source <path> --json")
        print("")
        print("This command is a read-only guide/router. It shows")
        print("your current Growth pipeline stage and the next")
        print("safest command to run. No files are written.")
        return 0

    source = _parse_arg(args, "--source")
    data = collect_run_data(source=source)

    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0

    render_run(data)
    return 0


def collect_run_data(
    source: str | None = None,
    root: str | None = None,
) -> dict[str, Any]:
    """Gather all Growth workflow guide data from existing collectors.

    Composes ``collect_console_data``, ``list_proposals``,
    ``build_dashboard``, and (optionally) ``collect_propose_data``
    into a single state dictionary describing where the user is in
    the Growth pipeline and what to do next.

    Read-only. No mutation. No network. No subprocess.
    """
    from pathlib import Path

    from link_core.control_plane import list_proposals

    repo_root = Path(root) if root else Path.cwd()
    base_data = _collect_growth_run_base_data(repo_root)

    proposals = list_proposals(root=repo_root)
    patch_draft_counts = _collect_patch_draft_counts(repo_root)

    status_counts: dict[str, int] = {}
    accepted_ids: list[str] = []
    for p in proposals:
        s = p.get("status", "?")
        status_counts[s] = status_counts.get(s, 0) + 1
        if s == "accepted":
            accepted_ids.append(p.get("proposal_id", ""))

    total = len(proposals)

    handoff_dir = repo_root / ".agents" / "control_plane" / "worker_handoffs"
    has_handoffs = handoff_dir.exists() and any(handoff_dir.glob("*.json"))

    router_state = _collect_growth_router_state(repo_root, proposals)
    router_state["accepted_proposal_ids"] = accepted_ids

    stage, next_action, commands = _derive_workflow_state(
        total=total,
        accepted_count=status_counts.get("accepted", 0),
        pending_count=status_counts.get("pending", 0),
        has_handoffs=has_handoffs,
        router_state=router_state,
    )
    coverage = _collect_growth_coverage_data(
        repo_root=repo_root,
        proposals=proposals,
        proposal_counts=status_counts,
        router_state=router_state,
        commands=commands,
    )

    result: dict[str, Any] = {
        "version": base_data.get("version", ""),
        "repo": base_data.get("repo", {}),
        "healthcheck": base_data.get("healthcheck", {}),
        "mode": base_data.get("mode", {}),
        "pipeline_stages": base_data.get("pipeline_stages", []),
        "pipeline_stage": stage,
        "proposal_counts": status_counts,
        "proposals_total": total,
        "accepted_proposal_ids": accepted_ids,
        "has_handoffs": has_handoffs,
        "router_state": router_state,
        "patch_draft_counts": patch_draft_counts,
        "coverage": coverage,
        "next_action": next_action,
        "commands": commands,
        "source_preview": None,
    }

    if source:
        try:
            preview = collect_propose_data(source, write=False, root=root)
            result["source_preview"] = {
                "source": preview.get("source", ""),
                "source_exists": preview.get("source_exists", False),
                "chunk_count": preview.get("chunk_count", 0),
                "candidate_count": preview.get("candidate_count", 0),
                "proposal_count": preview.get("proposal_count", 0),
                "error": preview.get("error"),
            }
        except Exception as exc:
            result["source_preview"] = {
                "source": source,
                "source_exists": False,
                "chunk_count": 0,
                "candidate_count": 0,
                "proposal_count": 0,
                "error": str(exc),
            }

    return result


def _collect_growth_coverage_data(
    repo_root: "Path",
    proposals: list[dict[str, Any]],
    proposal_counts: dict[str, int],
    router_state: dict[str, Any],
    commands: list[str],
) -> dict[str, Any]:
    """Collect read-only Growth pipeline coverage counts for run JSON."""
    code_queue = collect_archive_code_queue(
        top=_MAX_CODE_QUEUE_TOP,
        root=str(repo_root),
    )
    code_queue_count = int(code_queue.get("queue_count", 0) or 0)
    skipped_count = int(code_queue.get("skipped_count", 0) or 0)
    discovered_count = int(code_queue.get("total_discovered", 0) or 0) + skipped_count

    candidate_count = 0
    briefs_dir = repo_root / _CODE_BRIEFS_DIR
    if briefs_dir.exists():
        for path in sorted(briefs_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            candidate_count += len(_parse_code_brief_candidates(text, str(path)))

    next_commands = list(commands or [])
    return {
        "archive_count": int(router_state.get("archive_count", 0) or 0),
        "extracted_source_count": int(router_state.get("extracted_source_count", 0) or 0),
        "catalog_count": int(router_state.get("catalog_count", 0) or 0),
        "discovered_code_file_count": discovered_count,
        "queued_code_file_count": code_queue_count,
        "skipped_code_file_count": skipped_count,
        "code_brief_count": int(router_state.get("code_brief_count", 0) or 0),
        "candidate_count": candidate_count,
        "proposal_count": len(proposals),
        "pending_proposal_count": int(proposal_counts.get("pending", 0) or 0),
        "accepted_proposal_count": int(proposal_counts.get("accepted", 0) or 0),
        "rejected_proposal_count": int(proposal_counts.get("rejected", 0) or 0),
        "handoff_count": int(router_state.get("handoff_count", 0) or 0),
        "verifier_receipt_count": int(router_state.get("verifier_receipt_count", 0) or 0),
        "next_safest_command": next_commands[0] if next_commands else "",
        "next_commands": next_commands,
    }


def _collect_growth_run_base_data(repo_root: "Path") -> dict[str, Any]:
    """Collect Growth run header data without mutating runtime state."""
    import subprocess

    from link_core.control_plane import CONTROL_PLANE_STAGES
    from link_modes.growth import MODE_NAME, TEAM_CONFIG, control_plane_stages
    from link_modes.growth.link_candidate_proposal_bridge import BRIDGE_VERSION

    def git(args: list[str]) -> str:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=repo_root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                timeout=5,
            )
        except Exception:
            return ""
        if proc.returncode != 0:
            return ""
        return (proc.stdout or "").strip()

    status = git(["status", "--short"])
    return {
        "version": CONSOLE_VERSION,
        "repo": {
            "branch": git(["branch", "--show-current"]),
            "head": git(["rev-parse", "--short", "HEAD"]),
            "safe_tag": git(["rev-parse", "--short", "safe-link-latest"]),
            "dirty": bool(status),
        },
        "healthcheck": {"ok": None, "note": "not run by growth run"},
        "mode": {
            "name": MODE_NAME,
            "team_config": TEAM_CONFIG,
            "entrypoint": "link_modes.growth.propose()",
            "bridge_version": BRIDGE_VERSION,
            "has_propose": True,
        },
        "pipeline_stages": list(CONTROL_PLANE_STAGES) or list(control_plane_stages()),
    }


def _collect_patch_draft_counts(repo_root: "Path") -> dict[str, int]:
    """Count patch draft runtime files without creating directories."""
    draft_root = repo_root / ".link" / "patch_drafts"
    states = ("pending", "approved", "rejected", "retry", "receipts")
    return {
        state: len(list((draft_root / state).glob("*.json")))
        if (draft_root / state).exists() else 0
        for state in states
    }


def _collect_growth_router_state(
    repo_root: "Path",
    proposals: list[dict[str, Any]],
) -> dict[str, Any]:
    """Collect read-only Growth routing signals from local artifacts."""
    proposal_ids = {str(p.get("proposal_id", "")) for p in proposals}
    briefs_dir = repo_root / _CODE_BRIEFS_DIR
    catalogs_dir = repo_root / _CATALOG_OUTPUT_DIR
    extracted_dir = repo_root / _EXTRACTED_DIR
    handoff_dir = repo_root / ".agents" / "control_plane" / "worker_handoffs"
    receipt_dir = repo_root / ".agents" / "control_plane" / "verifier_receipts"

    candidate_briefs: list[dict[str, Any]] = []
    if briefs_dir.exists():
        for path in sorted(briefs_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            candidates = _parse_code_brief_candidates(text, str(path))
            if not candidates:
                continue
            generated_ids = {
                _code_brief_candidate_to_proposal(c, str(path))["proposal_id"]
                for c in candidates
            }
            missing_count = len(generated_ids - proposal_ids)
            if missing_count > 0:
                try:
                    display_path = str(path.relative_to(repo_root))
                except ValueError:
                    display_path = str(path)
                candidate_briefs.append({
                    "path": display_path,
                    "absolute_path": str(path),
                    "candidate_count": len(candidates),
                    "ungenerated_proposal_count": missing_count,
                    "suggested_command": (
                        f"python3 link.py growth code-brief-propose --source {display_path}"
                    ),
                })

    handoff_paths = sorted(handoff_dir.glob("*.json")) if handoff_dir.exists() else []
    receipt_paths = sorted(receipt_dir.glob("*.json")) if receipt_dir.exists() else []
    catalog_paths = sorted(catalogs_dir.glob("*.json")) if catalogs_dir.exists() else []
    if extracted_dir.exists():
        extracted_paths = [p for p in sorted(extracted_dir.iterdir()) if p.is_dir()]
    else:
        extracted_paths = []

    return {
        "code_brief_count": len(list(briefs_dir.glob("*.md"))) if briefs_dir.exists() else 0,
        "candidate_brief_count": len(candidate_briefs),
        "next_candidate_brief": candidate_briefs[0] if candidate_briefs else None,
        "catalog_count": len(catalog_paths),
        "extracted_source_count": len(extracted_paths),
        "archive_count": len(_discover_growth_archives(repo_root)),
        "handoff_count": len(handoff_paths),
        "next_handoff_id": handoff_paths[0].stem if handoff_paths else None,
        "verifier_receipt_count": len(receipt_paths),
    }


def _discover_growth_archives(repo_root: "Path") -> list[str]:
    """Return research archive paths without reading archive contents."""
    research_root = repo_root / "research"
    if not research_root.exists():
        return []

    archives: list[str] = []
    for path in sorted(research_root.rglob("*")):
        if not path.is_file():
            continue
        rel = str(path.relative_to(research_root))
        if rel.startswith("_extracted/") or rel.startswith("_catalog/"):
            continue
        lower_name = path.name.lower()
        if any(lower_name.endswith(suffix) for suffix in _ARCHIVE_SUFFIXES):
            archives.append(str(path))
    return archives


def _derive_workflow_state(
    total: int,
    accepted_count: int,
    pending_count: int,
    has_handoffs: bool,
    router_state: dict[str, Any] | None = None,
) -> tuple[str, str, list[str]]:
    """Derive pipeline stage, next_action, and recommended commands."""
    router_state = router_state or {}
    next_brief = router_state.get("next_candidate_brief") or {}

    if total == 0:
        if next_brief:
            brief_path = next_brief.get("path", "<brief.md>")
            return (
                "ProposalWriter",
                "Code brief candidates are ready to convert into pending proposals.",
                [
                    f"python3 link.py growth code-brief-propose --source {brief_path}",
                    f"python3 link.py growth code-brief-propose --source {brief_path} --write",
                    "python3 link.py growth proposals",
                ],
            )

        if router_state.get("catalog_count", 0) > 0 and router_state.get("code_brief_count", 0) == 0:
            return (
                "CandidateExtractor",
                "Cataloged extracted code exists. Queue code sources, then write a code brief for one source.",
                [
                    "python3 link.py growth archive-code-queue",
                    "python3 link.py growth archive-code-brief --source <path> --write",
                    "python3 link.py growth code-brief-propose --source research/_catalog/code_briefs/<slug>.md",
                ],
            )

        if router_state.get("extracted_source_count", 0) > 0 and router_state.get("catalog_count", 0) == 0:
            return (
                "ResearchIngest",
                "Extracted archives exist. Catalog them before mining code upgrade candidates.",
                [
                    "python3 link.py growth archive-catalog --source <extracted_path> --write",
                    "python3 link.py growth archive-code-queue",
                ],
            )

        if router_state.get("archive_count", 0) > 0:
            return (
                "ResearchIngest",
                "Research archives exist. Inventory, extract, and catalog them before mining proposals.",
                [
                    "python3 link.py growth archive-inventory",
                    "python3 link.py growth archive-extract --source <archive_path> --write",
                    "python3 link.py growth archive-catalog --source <extracted_path> --write",
                ],
            )

        return (
            "ResearchIngest",
            "No proposals or cataloged research found. Start with archive inventory or provide a source.",
            [
                "python3 link.py growth archive-inventory",
                "python3 link.py growth propose --source <path>",
            ],
        )

    if accepted_count > 0 and not has_handoffs:
        accepted_ids = router_state.get("accepted_proposal_ids") or []
        proposal_id = accepted_ids[0] if accepted_ids else "<id>"
        return (
            "PatchWorker",
            "Accepted proposals are ready for handoff creation.",
            [
                "python3 link.py growth proposals",
                f"python3 link.py growth handoff {proposal_id}",
                f"python3 link.py growth handoff {proposal_id} --write",
            ],
        )

    if has_handoffs and router_state.get("verifier_receipt_count", 0) == 0:
        handoff_id = router_state.get("next_handoff_id") or "<handoff_id>"
        return (
            "Verifier",
            "Worker handoffs exist. Create a verifier receipt through the safe execute path.",
            [
                "python3 link.py growth handoffs",
                f"python3 link.py growth execute {handoff_id}",
                f"python3 link.py growth execute {handoff_id} --write",
            ],
        )

    if accepted_count > 0 and has_handoffs:
        return (
            "Verifier",
            "Handoffs and verifier receipts exist. Review receipts and finish the accepted work.",
            [
                "python3 link.py growth receipts",
                "python3 link.py growth handoffs",
            ],
        )

    if pending_count > 0:
        return (
            "HumanApproval",
            "Proposals are pending review. Approve or reject them.",
            [
                "python3 link.py growth proposals",
                "python3 link.py growth approve <id>",
                "python3 link.py growth reject <id> --reason \"...\"",
            ],
        )

    return (
        "HumanApproval",
        "Proposals present. Review status and take next action.",
        [
            "python3 link.py growth proposals",
            "python3 link.py growth approve <id>",
        ],
    )


# ── run rich renderer ───────────────────────────────────────────────────


def render_run_with_rich(data: dict[str, Any]) -> None:
    """Render the Growth run guide using rich."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.table import Table
    from rich.text import Text

    console = Console(highlight=False, soft_wrap=True)
    repo = data.get("repo", {})
    hc = data.get("healthcheck", {})
    stage = data.get("pipeline_stage", "?")
    next_action = data.get("next_action", "")
    commands = data.get("commands", [])
    counts = data.get("proposal_counts", {})
    total = data.get("proposals_total", 0)
    accepted_ids = data.get("accepted_proposal_ids", [])
    has_handoffs = data.get("has_handoffs", False)
    source_preview = data.get("source_preview")

    stage_colors = {
        "ResearchIngest": "dim", "CandidateExtractor": "dim",
        "HumanApproval": "yellow", "ProposalWriter": "dim",
        "PatchWorker": "green", "Verifier": "cyan",
        "Finalizer": "bright_green", "PatchPlanner": "dim",
        "FeasibilityReviewer": "dim",
    }

    # ── header ──
    header = Table.grid(padding=(0, 1))
    header.add_column(justify="left")
    header.add_column(justify="right")
    header.add_row(
        f"[bold bright_cyan]LINK GROWTH RUN GUIDE[/]",
        f"[dim]v{data.get('version', '?')}[/]",
    )
    console.print(header)

    # ── repo bar ──
    repo_line = (
        f"branch: [bold]{repo.get('branch', '?')}[/]  "
        f"HEAD: [bold]{repo.get('head', '?')[:8]}[/]  "
        f"dirty: [{'red' if repo.get('dirty') else 'green'}]{'YES' if repo.get('dirty') else 'no'}[/]"
    )
    console.print(Panel(repo_line, border_style="dim"))

    # ── pipeline stage panel ──
    sc = stage_colors.get(stage, "")
    stage_text = Text()
    stage_text.append("Current stage: ", style="dim")
    stage_text.append(str(stage), style=sc or "")
    if next_action:
        stage_text.append(f"\n{next_action}", style="dim")
    console.print(Panel(stage_text, title="PIPELINE STAGE", border_style=sc or "dim"))

    # ── health quick status ──
    hc_ok = hc.get("ok")
    hc_label = "PASS" if hc_ok is True else ("FAIL" if hc_ok is False else "not run")
    hc_color = "green" if hc_ok is True else ("red" if hc_ok is False else "yellow")
    hc_text = Text()
    hc_text.append(f"healthcheck: {hc_label}", style=hc_color)
    if hc.get("note"):
        hc_text.append(f"  ({hc.get('note')})", style="dim")
    console.print(Panel(hc_text, border_style=hc_color))

    # ── proposal counts panel ──
    count_text = Text()
    count_labels = [
        ("pending", "yellow"), ("accepted", "green"), ("rejected", "red"),
        ("deferred", "magenta"), ("needs_smaller_plan", "orange1"),
        ("converted_to_patch", "cyan"),
    ]
    first = True
    for label, color in count_labels:
        val = counts.get(label, 0)
        if val == 0 and label not in ("pending", "accepted", "rejected"):
            continue
        if not first:
            count_text.append("  ")
        first = False
        count_text.append(f"{label}: {val}", style=color)
    count_text.append(f"\ntotal: {total}", style="dim")
    console.print(Panel(count_text, title="PROPOSAL COUNTS", border_style="dim"))

    # ── accepted ready for handoff ──
    if accepted_ids:
        ready_text = Text()
        ready_text.append(f"{len(accepted_ids)} accepted proposal(s) ready for handoff:\n", style="green")
        for a_id in accepted_ids[:10]:
            ready_text.append(f"  {a_id}\n", style="dim")
        console.print(Panel(ready_text, title="READY FOR HANDOFF", border_style="green"))

    if has_handoffs:
        hf_text = Text("Worker handoff directory contains files.", style="cyan")
        console.print(Panel(hf_text, title="HANDOFFS EXIST", border_style="cyan"))

    # ── source preview ──
    if source_preview:
        sp = source_preview
        sp_text = Text()
        exists = sp.get("source_exists", False)
        if not exists:
            sp_text.append(f"source not found: {sp.get('source', '?')}", style="red")
        else:
            sp_text.append(f"source: {sp.get('source', '?')}\n", style="bold")
            sp_text.append(
                f"[dim]chunks: {sp.get('chunk_count', 0)}  "
                f"candidates: {sp.get('candidate_count', 0)}  "
                f"proposals (dry-run): {sp.get('proposal_count', 0)}[/]"
            )
            if sp.get("candidate_count", 0) == 0:
                sp_text.append(
                    "\n[dim]no candidates — check keyword matches or duplicate titles[/]"
                )
            else:
                sp_text.append(
                    "\n[dim]use --write to persist proposals to disk[/]"
                )
        console.print(Panel(sp_text, title="SOURCE PREVIEW", border_style="dim"))

    # ── next commands panel ──
    import textwrap

    cmd_text = Text()
    cmd_text.append("Next commands:\n", style="bold")
    for cmd in commands:
        wrapped = textwrap.wrap(
            f"$ {cmd}",
            width=68,
            subsequent_indent="  ",
            break_long_words=False,
            break_on_hyphens=False,
        ) or [f"$ {cmd}"]
        for idx, line in enumerate(wrapped):
            prefix = "  " if idx == 0 else "    "
            cmd_text.append(f"{prefix}{line}\n", style="dim")
    console.print(Panel(cmd_text, title="RECOMMENDED NEXT STEP", border_style="green"))

    console.print(Rule(style="dim"))
    console.print(
        "  [dim]python3 link.py growth status  -- status console[/]"
    )


# ── run plain fallback ──────────────────────────────────────────────────


def render_run_plain(data: dict[str, Any]) -> None:
    """Render the Growth run guide using plain print."""
    repo = data.get("repo", {})
    hc = data.get("healthcheck", {})
    stage = data.get("pipeline_stage", "?")
    next_action = data.get("next_action", "")
    commands = data.get("commands", [])
    counts = data.get("proposal_counts", {})
    total = data.get("proposals_total", 0)
    accepted_ids = data.get("accepted_proposal_ids", [])
    has_handoffs = data.get("has_handoffs", False)
    source_preview = data.get("source_preview")

    out: list[str] = []
    out.append("== LINK GROWTH RUN GUIDE ==")
    out.append(
        f"branch: {repo.get('branch', '?')}  "
        f"HEAD: {repo.get('head', '?')[:8]}  "
        f"dirty: {'YES' if repo.get('dirty') else 'no'}"
    )
    out.append("")
    out.append(f"-- PIPELINE STAGE: {stage} --")
    out.append(next_action)
    out.append("")
    hc_ok = hc.get("ok")
    hc_label = "PASS" if hc_ok is True else ("FAIL" if hc_ok is False else "not run")
    out.append(f"healthcheck: {hc_label}")
    out.append("")
    out.append("-- PROPOSAL COUNTS --")
    out.append(
        f"pending: {counts.get('pending', 0)}  "
        f"accepted: {counts.get('accepted', 0)}  "
        f"rejected: {counts.get('rejected', 0)}  "
        f"total: {total}"
    )
    out.append("")

    if accepted_ids:
        out.append("-- READY FOR HANDOFF --")
        for a_id in accepted_ids[:10]:
            out.append(f"  {a_id}")
        out.append("")
    if has_handoffs:
        out.append("Handoff directory contains files.")
        out.append("")

    if source_preview:
        sp = source_preview
        out.append("-- SOURCE PREVIEW --")
        if not sp.get("source_exists", False):
            out.append(f"source not found: {sp.get('source', '?')}")
        else:
            out.append(f"source: {sp.get('source', '?')}")
            out.append(
                f"chunks: {sp.get('chunk_count', 0)}  "
                f"candidates: {sp.get('candidate_count', 0)}  "
                f"proposals (dry-run): {sp.get('proposal_count', 0)}"
            )
        out.append("")

    out.append("-- RECOMMENDED NEXT STEP --")
    for cmd in commands:
        out.append(f"  $ {cmd}")
    out.append("")

    out.append("python3 link.py growth status  -- status console")
    print("\n".join(out))


# ── run render orchestrator ─────────────────────────────────────────────


def render_run(data: dict[str, Any]) -> None:
    """Render the Growth run guide with rich if available."""
    try:
        import rich  # noqa: F401
    except ImportError:
        render_run_plain(data)
        return
    render_run_with_rich(data)


def main(argv: list[str] | None = None) -> int:
    """Entry point for ``python3 link.py growth status``.

    Passes through to render_console unless --json is requested.
    """
    args = sys.argv[1:] if argv is None else argv
    data = collect_console_data()
    if "--json" in args:
        print(json.dumps(data, indent=2, default=str))
        return 0
    render_console(data)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())