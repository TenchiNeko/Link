"""Compatibility shim for moved control-plane report CLI.

Canonical module:
    link_core.control_plane.link_control_plane_report_cli
"""

from link_core.control_plane.link_control_plane_report_cli import *  # noqa: F401,F403


if __name__ == "__main__":
    from link_core.control_plane.link_control_plane_report_cli import main

    raise SystemExit(main())
