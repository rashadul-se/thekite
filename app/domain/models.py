"""Domain layer: plain immutable data, no I/O."""
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _id() -> str:
    return uuid.uuid4().hex


@dataclass(frozen=True)
class VitalEvent:
    resident_id: int
    hr: int
    temp: float
    spo2: int
    sleep_hrs: float
    steps: int
    mood: int          # 1 (low) .. 5 (great)
    fluids_ml: int
    ts: str = field(default_factory=_now)
    event_id: str = field(default_factory=_id)   # idempotency key for sync

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class MedicationEvent:
    resident_id: int
    drug: str
    status: str        # GIVEN | REFUSED | MISSED
    ts: str = field(default_factory=_now)
    event_id: str = field(default_factory=_id)

    def to_dict(self) -> dict:
        return asdict(self)
