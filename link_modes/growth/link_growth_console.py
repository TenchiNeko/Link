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