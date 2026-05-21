from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_RE = re.compile(r"^[a-zA-Z0-9_-]+$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sanitize_project_name(project: str) -> str:
    project = project.strip()
    if not PROJECT_RE.match(project):
        raise ValueError("Project names may only use letters, numbers, underscores, and dashes.")
    return project


@dataclass
class WorkOrder:
    id: str
    project: str
    goal: str
    department: str
    role: str
    status: str = "planned"
    approval_required: bool = True
    approved: bool = False
    created_at: str = field(default_factory=utc_now)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "WorkOrder":
        return cls(**data)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "WorkOrder":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
