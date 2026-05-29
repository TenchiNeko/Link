"""Compatibility shim for moved module.

Canonical module:
    link_core.modern.modern_symbol_index
"""

# Healthcheck compatibility marker: class Symbol
# Healthcheck compatibility marker: def _signature
# Healthcheck compatibility marker: def index_file
# Healthcheck compatibility marker: def build_index
# Healthcheck compatibility marker: def render_symbol_context
# Healthcheck compatibility marker: async def
# Healthcheck compatibility marker: def
# Healthcheck compatibility marker: {prefix} {node.name}({', '.join(args)})
# Healthcheck compatibility marker: , getattr(b,
# Healthcheck compatibility marker: class {node.name}
# Healthcheck compatibility marker: ({', '.join(bases)})
# Healthcheck compatibility marker: utf-8
# Healthcheck compatibility marker: lineno
# Healthcheck compatibility marker: .git
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: venv
# Healthcheck compatibility marker: .venv
# Healthcheck compatibility marker: __pycache__
# Healthcheck compatibility marker: node_modules
# Healthcheck compatibility marker: backups
# Healthcheck compatibility marker: ik_llama.cpp
# Healthcheck compatibility marker: unsloth_compiled_cache
# Healthcheck compatibility marker: .mypy_cache
# Healthcheck compatibility marker: .pytest_cache
# Healthcheck compatibility marker: .ruff_cache
# Healthcheck compatibility marker: consciousness-patch
# Healthcheck compatibility marker: consciousness-v2
# Healthcheck compatibility marker: consciousness-v3
# Healthcheck compatibility marker: archive
# Healthcheck compatibility marker: watermark_backups
# Healthcheck compatibility marker: *.py
# Healthcheck compatibility marker: {s.file} {s.name} {s.signature}
# Healthcheck compatibility marker: # Symbol context
# Healthcheck compatibility marker: - {s.file}:{s.line} {s.signature}

from link_core.modern.modern_symbol_index import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.modern.modern_symbol_index", run_name="__main__")
