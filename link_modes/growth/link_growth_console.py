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
            "dry_run": not write,
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
    args = sys.argv[1:] if argv is None else argv

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
    from link_modes.growth.link_self_learning_dashboard import (
        build_dashboard,
    )

    repo_root = Path(root) if root else Path.cwd()
    console_data = collect_console_data()

    proposals = list_proposals(root=repo_root)
    sd = build_dashboard(root=repo_root)

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

    stage, next_action, commands = _derive_workflow_state(
        total=total,
        accepted_count=status_counts.get("accepted", 0),
        pending_count=status_counts.get("pending", 0),
        has_handoffs=has_handoffs,
    )

    result: dict[str, Any] = {
        "version": console_data.get("version", ""),
        "repo": console_data.get("repo", {}),
        "healthcheck": console_data.get("healthcheck", {}),
        "mode": console_data.get("mode", {}),
        "pipeline_stages": console_data.get("pipeline", {}).get(
            "canonical_stages",
            console_data.get("pipeline", {}).get("stages", []),
        ),
        "pipeline_stage": stage,
        "proposal_counts": status_counts,
        "proposals_total": total,
        "accepted_proposal_ids": accepted_ids,
        "has_handoffs": has_handoffs,
        "patch_draft_counts": sd.get("patch_draft_counts", {}),
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


def _derive_workflow_state(
    total: int,
    accepted_count: int,
    pending_count: int,
    has_handoffs: bool,
) -> tuple[str, str, list[str]]:
    """Derive pipeline stage, next_action, and recommended commands."""
    if total == 0:
        return (
            "ResearchIngest",
            "No proposals found. Mine research into proposals.",
            [
                "python3 link.py growth propose --source <path>",
                "python3 link.py growth propose --source <path> --write",
            ],
        )

    if accepted_count > 0 and not has_handoffs:
        return (
            "PatchWorker",
            "Accepted proposals are ready for handoff creation.",
            [
                "python3 link.py growth proposals",
                "python3 link.py growth handoff <id>",
                "python3 link.py growth handoff <id> --write",
            ],
        )

    if accepted_count > 0 and has_handoffs:
        return (
            "Verifier",
            "Handoffs exist. Verify and execute worker handoffs.",
            [
                "python3 link.py growth proposals",
                "python3 link.py growth handoff <id> --write",
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
    stage_text.append(f"[{sc}]{stage}[/]")
    if next_action:
        stage_text.append(f"\n[dim]{next_action}[/]")
    console.print(Panel(stage_text, title="PIPELINE STAGE", border_style=sc or "dim"))

    # ── health quick status ──
    hc_ok = hc.get("ok", False)
    hc_color = "green" if hc_ok else "red"
    status_line = f"healthcheck: [{hc_color}]{'PASS' if hc_ok else 'FAIL'}[/]  "
    hc_text = Text()
    hc_text.append(f"healthcheck: [{hc_color}]{'PASS' if hc_ok else 'FAIL'}[/]")
    console.print(Panel(hc_text, border_style=hc_color if hc_ok else "red"))

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
        count_text.append(f"[{color}]{label}: {val}[/]")
    count_text.append(f"\n[dim]total: {total}[/]")
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
    cmd_text = Text()
    cmd_text.append("Next commands:\n", style="bold")
    for cmd in commands:
        cmd_text.append(f"  $ {cmd}\n", style="dim")
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
    hc_ok = hc.get("ok", False)
    out.append(f"healthcheck: {'PASS' if hc_ok else 'FAIL'}")
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