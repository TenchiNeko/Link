"""Simple local budget tracker for long autonomous runs."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path
import json
import time

@dataclass
class UsageEvent:
    ts: float
    phase: str
    model: str
    prompt_chars: int
    output_chars: int
    seconds: float
    ok: bool

class UsageBudget:
    def __init__(self, path: Path, max_seconds: int | None = None, max_chars: int | None = None):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.max_seconds = max_seconds
        self.max_chars = max_chars
        self.events: list[UsageEvent] = []

    def record(self, phase: str, model: str, prompt: str, output: str, seconds: float, ok: bool) -> None:
        ev = UsageEvent(time.time(), phase, model, len(prompt or ""), len(output or ""), seconds, ok)
        self.events.append(ev)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(ev)) + "\n")

    @property
    def total_seconds(self) -> float:
        return sum(e.seconds for e in self.events)

    @property
    def total_chars(self) -> int:
        return sum(e.prompt_chars + e.output_chars for e in self.events)

    def should_stop(self) -> tuple[bool, str]:
        if self.max_seconds is not None and self.total_seconds >= self.max_seconds:
            return True, f"time budget exceeded: {self.total_seconds:.1f}s >= {self.max_seconds}s"
        if self.max_chars is not None and self.total_chars >= self.max_chars:
            return True, f"char budget exceeded: {self.total_chars} >= {self.max_chars}"
        return False, ""
