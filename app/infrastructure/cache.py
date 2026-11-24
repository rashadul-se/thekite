"""Redis cache. Fails silently so the app keeps working offline."""
import json
import redis


class RedisCache:
    def __init__(self, url: str, ttl: int):
        self._ttl = ttl
        self._r = redis.Redis.from_url(url, socket_connect_timeout=1, socket_timeout=1,
                                       decode_responses=True)

    def get(self, key: str):
        try:
            raw = self._r.get(key)
            return json.loads(raw) if raw else None
        except redis.RedisError:
            return None

    def set(self, key: str, value, ttl: int | None = None) -> None:
        try:
            self._r.setex(key, ttl or self._ttl, json.dumps(value, default=str))
        except redis.RedisError:
            pass

    def invalidate(self, *prefixes: str) -> None:
        try:
            for p in prefixes:
                for k in self._r.scan_iter(f"{p}*", count=500):
                    self._r.delete(k)
        except redis.RedisError:
            pass

    def alive(self) -> bool:
        try:
            return bool(self._r.ping())
        except redis.RedisError:
            return False
