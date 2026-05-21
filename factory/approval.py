from __future__ import annotations

from pathlib import Path


def approval_path(factory_root: Path, project: str, work_order_id: str) -> Path:
    return factory_root / "approvals" / project / f"{work_order_id}.approved"


def is_approved(factory_root: Path, project: str, work_order_id: str) -> bool:
    return approval_path(factory_root, project, work_order_id).exists()


def require_approval(factory_root: Path, project: str, work_order_id: str) -> None:
    path = approval_path(factory_root, project, work_order_id)
    if not path.exists():
        raise PermissionError(
            f"Human approval required before execution. Create this file to approve: {path}"
        )
