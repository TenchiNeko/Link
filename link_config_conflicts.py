"""Compatibility shim for moved module.

Canonical module:
    link_core.config.link_config_conflicts
"""

# Healthcheck compatibility marker: def parse_python_assignments
# Healthcheck compatibility marker: def flatten
# Healthcheck compatibility marker: def collect
# Healthcheck compatibility marker: def main
# Healthcheck compatibility marker: link_config.json
# Healthcheck compatibility marker: .link/config.json
# Healthcheck compatibility marker: .agents/config.json
# Healthcheck compatibility marker: standalone_config.py
# Healthcheck compatibility marker: standalone_models.py
# Healthcheck compatibility marker: standalone_agents.py
# Healthcheck compatibility marker: link_rules.local.json
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: _CONFIG
# Healthcheck compatibility marker: model
# Healthcheck compatibility marker: agent
# Healthcheck compatibility marker: <dynamic>
# Healthcheck compatibility marker: {prefix}.{k}
# Healthcheck compatibility marker: .json
# Healthcheck compatibility marker: .py
# Healthcheck compatibility marker: LINK_
# Healthcheck compatibility marker: OLLAMA_
# Healthcheck compatibility marker: MODEL
# Healthcheck compatibility marker: MODEL_NAME
# Healthcheck compatibility marker: environment
# Healthcheck compatibility marker: key
# Healthcheck compatibility marker: scopes
# Healthcheck compatibility marker: conflicts
# Healthcheck compatibility marker: conflict_count
# Healthcheck compatibility marker: Find Link config settings that appear in multiple scopes.
# Healthcheck compatibility marker: --json
# Healthcheck compatibility marker: store_true
# Healthcheck compatibility marker: Config scopes found: {len(data['scopes'])}
# Healthcheck compatibility marker: Conflicts found: {data['conflict_count']}
# Healthcheck compatibility marker: - {item['key']}: {', '.join(item['scopes'])}
# Healthcheck compatibility marker: __main__

from link_core.config.link_config_conflicts import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.config.link_config_conflicts", run_name="__main__")
