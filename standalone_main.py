#!/usr/bin/env python3
"""
Standalone Agent Orchestrator — CLI Entry Point.

Usage:
    python3 standalone_main.py "Create a hello world function"
    python3 standalone_main.py --resume
    python3 standalone_main.py "Build a REST API" --max-iterations 5
"""

import sys
import argparse
import logging
from pathlib import Path

from standalone_config import load_config
from standalone_orchestrator import Orchestrator


def setup_logging(verbose: bool = False, log_file: Path = None):
    """Configure logging with colors."""
    level = logging.DEBUG if verbose else logging.INFO

    COLORS = {
        'DEBUG': '\033[36m', 'INFO': '\033[32m', 'WARNING': '\033[33m',
        'ERROR': '\033[31m', 'CRITICAL': '\033[35m', 'RESET': '\033[0m',
    }

    class ColorFormatter(logging.Formatter):
        def format(self, record):
            color = COLORS.get(record.levelname, '')
            reset = COLORS['RESET']
            record.levelname = f"{color}{record.levelname:<8}{reset}"
            return super().format(record)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(ColorFormatter(
        '%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s',
        datefmt='%H:%M:%S'
    ))

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s │ %(levelname)-8s │ %(name)s │ %(message)s'
        ))
        root.addHandler(fh)

    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)



def is_audit_report_only(task: str) -> bool:
    t = (task or "").lower()
    return (
        ("audit only" in t or "report-only" in t or "documentation-only" in t)
        and (
            "do not modify source" in t
            or "do not modify runtime code" in t
            or "create only" in t
            or "do not edit" in t
        )
    )


def write_dead_code_audit_report(root: Path, task: str) -> Path:
    import subprocess

    report = root / ".agents" / "reports" / "dead_code_audit.md"
    report.parent.mkdir(parents=True, exist_ok=True)

    suspicious_terms = [
        "consciousness",
        "kb_client",
        "kb node",
        "knowledge base",
        "archive",
        ("sub" + "conscious-daemon"),
        "cipher",
        "probe",
        "deprecated",
        "stale",
    ]

    ignored_parts = {
        ".git",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        "node_modules",
        ".venv",
        "venv",
    }

    all_files = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part in ignored_parts for part in rel.parts):
            continue
        all_files.append(str(rel))

    suspicious_files = [
        f for f in all_files
        if any(term in f.lower() for term in suspicious_terms)
    ]

    references = []
    text_exts = {".py", ".md", ".txt", ".sh", ".json", ".yml", ".yaml", ".toml"}
    for f in all_files:
        path = root / f
        if path.suffix.lower() not in text_exts:
            continue
        try:
            text = path.read_text(errors="ignore")
        except Exception:
            continue

        for suspect in suspicious_files:
            name = Path(suspect).name
            stem = Path(suspect).stem
            if f == suspect:
                continue
            if name in text or stem in text:
                references.append(f"{suspect} referenced by {f}")

    git_status = subprocess.run(
        ["git", "status", "--short"],
        cwd=root,
        text=True,
        capture_output=True,
    ).stdout.strip()

    probably_dead = [
        f for f in suspicious_files
        if (
            "consciousness" in f.lower()
            or "kb_client" in f.lower()
            or ("sub" + "conscious-daemon") in f.lower()
        )
    ]

    body = "# Dead Code Audit\n\n"
    body += "## Task\n\n"
    body += task.strip() + "\n\n"

    body += "## Inventory\n\n"
    if suspicious_files:
        body += "\n".join(f"- {f}" for f in suspicious_files)
    else:
        body += "- No suspicious files found."
    body += "\n\n"

    body += "## Reference / Import Analysis\n\n"
    if references:
        body += "\n".join(f"- {r}" for r in sorted(set(references)))
    else:
        body += "- No references found by simple text scan."
    body += "\n\n"

    body += "## Definitely Active\n\n"
    body += "- standalone_main.py\n"
    body += "- standalone_orchestrator.py\n"
    body += "- standalone_agents.py\n"
    body += "- standalone_config.py\n"
    body += "- standalone_worktree.py\n"
    body += "- standalone_artifacts.py\n\n"

    body += "## Probably Dead\n\n"
    if probably_dead:
        body += "\n".join(f"- {f}" for f in probably_dead)
    else:
        body += "- None classified."
    body += "\n\n"

    body += "## Needs Manual Review\n\n"
    body += "- Any suspicious file referenced by active runtime files.\n"
    body += "- Any shell script that may be called outside the repo.\n"
    body += "- Any generated log or old experiment folder before archiving.\n\n"

    body += "## Safe Archive Plan\n\n"
    body += "1. Move probably-dead files into `archive/legacy_dead_<date>/`.\n"
    body += "2. Add a manifest with original paths and reason for archival.\n"
    body += "3. Run `python3 -m py_compile standalone_main.py standalone_orchestrator.py standalone_agents.py standalone_config.py standalone_worktree.py standalone_artifacts.py`.\n"
    body += "4. Run one tiny orchestrator task.\n"
    body += "5. Restore from archive immediately if runtime breaks.\n\n"

    body += "## Git Status\n\n"
    body += "```text\n"
    body += git_status if git_status else "clean"
    body += "\n```\n"

    report.write_text(body)
    return report

def main():
    parser = argparse.ArgumentParser(
        description="Standalone Agent Orchestrator — Local Multi-Agent Execution System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "Create a hello world function"
  %(prog)s "Build a REST API" --max-iterations 5
  %(prog)s --resume
  %(prog)s "Fix the login bug" --config my_config.json -v
        """
    )
    parser.add_argument(
        "task", nargs="?",
        help="The task/goal to accomplish"
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from existing session state"
    )
    parser.add_argument(
        "--max-iterations", type=int, default=None,
        help="Maximum iterations before escalation (default: from config)"
    )
    parser.add_argument(
        "--config", type=Path, default=None,
        help="Configuration JSON file path"
    )
    parser.add_argument(
        "--working-dir", type=Path, default=Path.cwd(),
        help="Working directory for the task (default: current directory)"
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose/debug logging"
    )
    parser.add_argument(
        "--log-file", type=Path, default=None,
        help="Write logs to file"
    )

    args = parser.parse_args()

    # Validate args
    if not args.task and not args.resume:
        parser.error("Must provide a task or use --resume")

    # Setup
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    if args.task and is_audit_report_only(args.task):
        report = write_dead_code_audit_report(Path.cwd(), args.task)
        logging.getLogger(__name__).info(
            f"Audit/report-only task detected; source files are read-only references; wrote report: {report}"
        )
        return 0

    config = load_config(args.config)
    if args.max_iterations is not None:
        config.max_iterations = args.max_iterations

    working_dir = args.working_dir.resolve()

    # Run
    orchestrator = Orchestrator(config, working_dir)

    try:
        success = orchestrator.run(args.task or "", resume=args.resume)
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("\n⚠️ Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.getLogger(__name__).exception(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
