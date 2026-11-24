"""Composition root: the only place concrete classes are wired together."""
from app.config import Settings
from app.infrastructure.cache import RedisCache
from app.infrastructure.outbox import Outbox
from app.infrastructure.postgres import PostgresRepository
from app.services.care_service import CareService
from app.services.insights import InsightEngine
from app.seed import seed


def build_service() -> CareService:
    cfg = Settings()
    repo = PostgresRepository(cfg.database_url, cfg.pool_min, cfg.pool_max)
    repo.init_schema()
    if cfg.auto_seed and repo.count_residents() == 0:
        seed(repo, cfg.resident_count)
    return CareService(repo, RedisCache(cfg.redis_url, cfg.cache_ttl),
                       Outbox(cfg.outbox_path), InsightEngine(), cfg)
