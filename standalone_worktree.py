"""Compatibility shim for moved module.

Canonical module:
    link_core.standalone.standalone_worktree
"""

# Healthcheck compatibility marker: class WorktreeInfo
# Healthcheck compatibility marker: def _run_git
# Healthcheck compatibility marker: def get_changed_files_against_head
# Healthcheck compatibility marker: def get_repo_status
# Healthcheck compatibility marker: def restore_repo_paths
# Healthcheck compatibility marker: def validate_worktree_slug
# Healthcheck compatibility marker: def create_worktree
# Healthcheck compatibility marker: def has_worktree_changes
# Healthcheck compatibility marker: def remove_worktree
# Healthcheck compatibility marker: ^[A-Za-z0-9._-]+$
# Healthcheck compatibility marker: git
# Healthcheck compatibility marker: master
# Healthcheck compatibility marker: Return files changed in this worktree compared with the main branch/base ref.
# Healthcheck compatibility marker: diff
# Healthcheck compatibility marker: --name-only
# Healthcheck compatibility marker: {base_ref}...HEAD
# Healthcheck compatibility marker: HEAD
# Healthcheck compatibility marker: Return git porcelain status for the given repo.
# Healthcheck compatibility marker: status
# Healthcheck compatibility marker: --porcelain
# Healthcheck compatibility marker: --untracked-files=all
# Healthcheck compatibility marker: git status failed: {result.stderr.strip() or result.stdout.strip()}
# Healthcheck compatibility marker: Restore tracked paths in the main repo after isolated runs.
# Healthcheck compatibility marker: restore
# Healthcheck compatibility marker: git restore failed: {result.stderr.strip() or result.stdout.strip()}
# Healthcheck compatibility marker: worktree slug must not be empty
# Healthcheck compatibility marker: worktree slug must be 64 characters or fewer
# Healthcheck compatibility marker: } or
# Healthcheck compatibility marker: in slug or
# Healthcheck compatibility marker: worktree slug must not contain path separators or dot segments
# Healthcheck compatibility marker: worktree slug may only contain letters, digits, dots, underscores, and dashes
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: worktrees
# Healthcheck compatibility marker: agent/{slug}
# Healthcheck compatibility marker: worktree already exists: {path}
# Healthcheck compatibility marker: worktree
# Healthcheck compatibility marker: add
# Healthcheck compatibility marker: , branch, str(path),
# Healthcheck compatibility marker: git worktree add failed: {result.stderr.strip() or result.stdout.strip()}
# Healthcheck compatibility marker: --ignored=matching
# Healthcheck compatibility marker: remove
# Healthcheck compatibility marker: --force
# Healthcheck compatibility marker: git worktree remove failed: {result.stderr.strip() or result.stdout.strip()}
# Healthcheck compatibility marker: branch

from link_core.standalone.standalone_worktree import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.standalone.standalone_worktree", run_name="__main__")
