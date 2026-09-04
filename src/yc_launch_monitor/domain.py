from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
import hashlib
import json
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class Source(StrEnum):
    YC_DIRECTORY = "yc_directory"
    SPEEDRUN = "speedrun"
    X = "x"
    LINKEDIN = "linkedin"


class SignalStatus(StrEnum):
    CONFIRMED_YC = "confirmed_yc"
    CONFIRMED_SPEEDRUN = "confirmed_speedrun"
    EARLY_SIGNAL = "early_signal"
    NEEDS_REVIEW = "needs_review"


class CollectorHealth(StrEnum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    NOT_CONFIGURED = "not_configured"


@dataclass(slots=True)
class Signal:
    source: Source
    source_id: str
    source_url: str
    company_name: str
    text: str
    founder_name: str = ""
    program: str = ""
    batch_or_cohort: str = ""
    occurred_at: str | None = None
    detected_at: str = field(default_factory=utc_now)
    status: SignalStatus = SignalStatus.NEEDS_REVIEW
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.source.value}:{self.source_id}"

    @property
    def content_hash(self) -> str:
        payload = {
            "source_url": self.source_url,
            "company_name": self.company_name,
            "founder_name": self.founder_name,
            "text": self.text,
            "program": self.program,
            "batch_or_cohort": self.batch_or_cohort,
            "occurred_at": self.occurred_at,
            "status": self.status.value,
            "confidence": round(self.confidence, 4),
            "metadata": self.metadata,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source"] = self.source.value
        result["status"] = self.status.value
        result["key"] = self.key
        return result


@dataclass(slots=True)
class CollectorResult:
    source: Source
    health: CollectorHealth
    signals: list[Signal] = field(default_factory=list)
    diagnostic: str = ""


@dataclass(slots=True)
class RunResult:
    run_id: str
    started_at: str
    completed_at: str
    collected: int
    new_or_changed: int
    delivered: int
    failed_deliveries: int
    source_health: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
