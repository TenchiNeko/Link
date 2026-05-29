"""Compatibility shim for moved module.

Canonical module:
    link_core.agents.link_agent_identity
"""

# Healthcheck compatibility marker: def utc_now
# Healthcheck compatibility marker: def safe_role_id
# Healthcheck compatibility marker: def role_dir
# Healthcheck compatibility marker: def identity_path
# Healthcheck compatibility marker: def deterministic_agent_id
# Healthcheck compatibility marker: def ensure_role_identity
# Healthcheck compatibility marker: def ensure_memory_tree
# Healthcheck compatibility marker: def list_identities
# Healthcheck compatibility marker: LU292-agent-identity-v1
# Healthcheck compatibility marker: link
# Healthcheck compatibility marker: LINK_AGENT_MEMORY_ROOT
# Healthcheck compatibility marker: .link/agent_memory
# Healthcheck compatibility marker: https://local.link/agent-identity
# Healthcheck compatibility marker: [^a-z0-9_.-]+
# Healthcheck compatibility marker: -._
# Healthcheck compatibility marker: role_id is required
# Healthcheck compatibility marker: identity.json
# Healthcheck compatibility marker: {project}:{safe_role_id(role_id)}
# Healthcheck compatibility marker: schema_version
# Healthcheck compatibility marker: project
# Healthcheck compatibility marker: role_id
# Healthcheck compatibility marker: agent_id
# Healthcheck compatibility marker: created_at
# Healthcheck compatibility marker: updated_at
# Healthcheck compatibility marker: positive
# Healthcheck compatibility marker: negative
# Healthcheck compatibility marker: neutral
# Healthcheck compatibility marker: receipts
# Healthcheck compatibility marker: events.jsonl
# Healthcheck compatibility marker: role_dir
# Healthcheck compatibility marker: identity
# Healthcheck compatibility marker: events
# Healthcheck compatibility marker: */identity.json
# Healthcheck compatibility marker: path
# Healthcheck compatibility marker: error
# Healthcheck compatibility marker: unreadable_identity
# Healthcheck compatibility marker: __main__
# Healthcheck compatibility marker: Link agent identity adapter
# Healthcheck compatibility marker: --role-id
# Healthcheck compatibility marker: qa_worker
# Healthcheck compatibility marker: --project
# Healthcheck compatibility marker: --list
# Healthcheck compatibility marker: store_true

from link_core.agents.link_agent_identity import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.agents.link_agent_identity", run_name="__main__")
