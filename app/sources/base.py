from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass
class NormalizedJob:
    source_job_id: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    requirements: str = ""
    remote: str = ""
    employment_type: str = ""
    salary: str = ""
    published_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class SourceAdapter(Protocol):
    def fetch(self, config: dict[str, Any]) -> list[NormalizedJob]: ...
