"""Application service (facade). UI talks only to this class; business rules stay private."""
import logging
import pandas as pd
from app.config import Settings
from app.domain.models import VitalEvent, MedicationEvent
from app.infrastructure.cache import RedisCache
from app.infrastructure.outbox import Outbox
from app.infrastructure.postgres import PostgresRepository
from app.services.insights import InsightEngine

log = logging.getLogger("eldercare")
_KIND_TABLE = {"vital": "vitals", "med": "med_log"}


class CareService:
    def __init__(self, repo: PostgresRepository, cache: RedisCache, outbox: Outbox,
                 engine: InsightEngine, cfg: Settings):
        self.__repo, self.__cache, self.__outbox = repo, cache, outbox
        self.__engine, self.__cfg = engine, cfg

    # ---------- public API ----------
    def status(self) -> dict:
        return {"postgres": self.__repo.ping(), "redis": self.__cache.alive(),
                "pending_sync": self.__outbox.pending_count()}

    def dashboard(self) -> dict:
        cached = self.__cache.get("dash:v1")
        if cached:
            return cached
        risk = self.__engine.daily_risk(self.__repo.vitals_window(14))
        payload = {
            "total": self.__repo.count_residents(),
            "red": int((risk["level"] == "Red").sum()) if len(risk) else 0,
            "amber": int((risk["level"] == "Amber").sum()) if len(risk) else 0,
            "top": risk.head(25)[["resident_id", "risk_score", "level", "reasons"]]
                       .astype({"level": str}).to_dict("records") if len(risk) else [],
        }
        self.__cache.set("dash:v1", payload)
        return payload

    def residents(self, search: str = "", page: int = 0, size: int = 50) -> pd.DataFrame:
        key = f"res:{search}:{page}:{size}"
        hit = self.__cache.get(key)
        if hit is not None:
            return pd.DataFrame(hit)
        df = self.__repo.list_residents(search, page * size, size)
        self.__cache.set(key, df.to_dict("records"), ttl=300)
        return df

    def resident_detail(self, rid: int) -> dict:
        vitals, meds = self.__repo.resident_history(rid)
        return {"vitals": vitals, "meds": meds, "insights": self.__engine.patterns(vitals)}

    def record_vital(self, ev: VitalEvent, online: bool = True) -> str:
        self.__validate_vital(ev)
        return self.__enqueue("vital", ev.event_id, ev.to_dict(), online)

    def log_medication(self, ev: MedicationEvent, online: bool = True) -> str:
        if ev.status not in ("GIVEN", "REFUSED", "MISSED"):
            raise ValueError("Invalid medication status")
        return self.__enqueue("med", ev.event_id, ev.to_dict(), online)

    def sync(self) -> int:
        """Push offline events to PostgreSQL in batches (idempotent). Returns rows synced."""
        total = 0
        while True:
            batch = self.__outbox.pending(self.__cfg.sync_batch)
            if not batch:
                break
            try:
                for kind, table in _KIND_TABLE.items():
                    rows = [p for _, k, p in batch if k == kind]
                    if rows:
                        self.__repo.bulk_insert(table, rows)
                self.__outbox.mark_synced([e for e, _, _ in batch])
                total += len(batch)
            except Exception as exc:   # network down: keep events queued
                log.warning("sync deferred: %s", exc)
                break
        if total:
            self.__cache.invalidate("dash:", "res:")
        return total

    # ---------- private business logic (name-mangled) ----------
    def __enqueue(self, kind: str, event_id: str, payload: dict, online: bool) -> str:
        self.__outbox.add(kind, event_id, payload)        # always local first
        if online:
            self.sync()
        return "synced" if self.__outbox.pending_count() == 0 else "queued offline"

    @staticmethod
    def __validate_vital(ev: VitalEvent) -> None:
        if not (30 <= ev.hr <= 220 and 30.0 <= ev.temp <= 43.0 and 50 <= ev.spo2 <= 100
                and 1 <= ev.mood <= 5 and 0 <= ev.sleep_hrs <= 24):
            raise ValueError("Vital signs out of plausible range")
