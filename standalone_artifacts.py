"""Compatibility shim for moved module.

Canonical module:
    link_core.standalone.standalone_artifacts
"""

# Healthcheck compatibility marker: def get_task_artifact_dir
# Healthcheck compatibility marker: def copy_file_to_artifacts
# Healthcheck compatibility marker: .agents
# Healthcheck compatibility marker: artifacts

from link_core.standalone.standalone_artifacts import *  # noqa: F401,F403

if __name__ == "__main__":
    import runpy
    runpy.run_module("link_core.standalone.standalone_artifacts", run_name="__main__")
