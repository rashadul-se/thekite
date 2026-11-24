"""Central configuration (12-factor: everything comes from env vars)."""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv("DATABASE_URL", "postgresql://care:care@localhost:5432/care")
    redis_url: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    outbox_path: str = os.getenv("OUTBOX_PATH", "/tmp/eldercare_outbox.db")
    pool_min: int = int(os.getenv("DB_POOL_MIN", "1"))
    pool_max: int = int(os.getenv("DB_POOL_MAX", "10"))
    cache_ttl: int = int(os.getenv("CACHE_TTL", "60"))
    sync_batch: int = int(os.getenv("SYNC_BATCH", "500"))
    auto_seed: bool = os.getenv("AUTO_SEED", "true").lower() == "true"
    resident_count: int = int(os.getenv("RESIDENT_COUNT", "1000"))
