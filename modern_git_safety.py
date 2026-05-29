"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_git_safety
"""

# Healthcheck compatibility marker: class GitRiskLevel
# Healthcheck compatibility marker: class GitSafetyAssessment
# Healthcheck compatibility marker: def _has_shell_write_or_pipe
# Healthcheck compatibility marker: def classify_git_command
# Healthcheck compatibility marker: def classify_worktree_path
# Healthcheck compatibility marker: allow
# Healthcheck compatibility marker: caution
# Healthcheck compatibility marker: deny
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: diff
# Healthcheck compatibility marker: log
# Healthcheck compatibility marker: show
# Healthcheck compatibility marker: rev-parse
# Healthcheck compatibility marker: branch
# Healthcheck compatibility marker: tag
# Healthcheck compatibility marker: remote
# Healthcheck compatibility marker: ls-files
# Healthcheck compatibility marker: add
# Healthcheck compatibility marker: commit
# Healthcheck compatibility marker: checkout
# Healthcheck compatibility marker: switch
# Healthcheck compatibility marker: merge
# Healthcheck compatibility marker: rebase
# Healthcheck compatibility marker: reset
# Healthcheck compatibility marker: clean
# Healthcheck compatibility marker: stash
# Healthcheck compatibility marker: pull
# Healthcheck compatibility marker: fetch
# Healthcheck compatibility marker: push
# Healthcheck compatibility marker: worktree
# Healthcheck compatibility marker: restore
# Healthcheck compatibility marker: \bgit\s+reset\b.*\s--hard\b
# Healthcheck compatibility marker: git reset --hard can destroy local work
# Healthcheck compatibility marker: \bgit\s+clean\b.*-[a-zA-Z]*f[a-zA-Z]*d
# Healthcheck compatibility marker: git clean -fd can delete untracked files
# Healthcheck compatibility marker: \bgit\s+clean\b.*-[a-zA-Z]*x
# Healthcheck compatibility marker: git clean -x can delete ignored files
# Healthcheck compatibility marker: \bgit\s+push\b.*(--force|-f)\b
# Healthcheck compatibility marker: force push can rewrite remote history
# Healthcheck compatibility marker: \bgit\s+branch\s+-D\b
# Healthcheck compatibility marker: force deleting branches is destructive
# Healthcheck compatibility marker: \bgit\s+worktree\s+remove\b.*(--force|-f)\b
# Healthcheck compatibility marker: force removing worktrees can destroy work
# Healthcheck compatibility marker: \bgit\s+checkout\s+--\s+\.
# Healthcheck compatibility marker: checkout -- . can discard local changes
# Healthcheck compatibility marker: \bgit\s+restore\s+\.
# Healthcheck compatibility marker: restore . can discard local changes
# Healthcheck compatibility marker: (\||>>?|2>|&>)
# Healthcheck compatibility marker: empty command
# Healthcheck compatibility marker: could not parse command safely
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: not a git command
# Healthcheck compatibility marker: git with no subcommand only prints help
# Healthcheck compatibility marker: --git-dir
# Healthcheck compatibility marker: --work-tree
# Healthcheck compatibility marker: git path override needs review
# Healthcheck compatibility marker: git command includes shell pipe/redirection
# Healthcheck compatibility marker: --delete
# Healthcheck compatibility marker: branch deletion needs review
# Healthcheck compatibility marker: read-only git branch inspection
# Healthcheck compatibility marker: --force
# Healthcheck compatibility marker: git tag mutation needs review
# Healthcheck compatibility marker: read-only git tag inspection
# Healthcheck compatibility marker: read-only git {op}
# Healthcheck compatibility marker: git {op} may modify repo state
# Healthcheck compatibility marker: unknown git subcommand: {op}
# Healthcheck compatibility marker: path is outside Link repo root
# Healthcheck compatibility marker: .git
# Healthcheck compatibility marker: path is inside .git metadata
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: path is inside Link agent generated state
# Healthcheck compatibility marker: research
# Healthcheck compatibility marker: path is research/reference material
# Healthcheck compatibility marker: path is inside Link repo

from link_core.modern.modern_git_safety import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_git_safety", run_name="__main__")
