"""Compatibility shim for moved Growth Link module.

Canonical module:
    link_modes.growth.link_research_archive_miner
"""

if __name__ == "__main__":
    from pathlib import Path
    import runpy

    target = Path(__file__).resolve().parent / "link_modes" / "growth" / "link_research_archive_miner.py"
    runpy.run_path(str(target), run_name="__main__")
else:
    from link_modes.growth.link_research_archive_miner import *  # noqa: F401,F403
