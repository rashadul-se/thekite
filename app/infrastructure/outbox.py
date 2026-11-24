"""Local SQLite outbox: guarantees writes succeed with no network (offline-first)."""
import json
import sqlite3
import threading


class Outbox:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._c = sqlite3.connect(path, check_same_thread=False)
        self._c.execute("""CREATE TABLE IF NOT EXISTS outbox(
            event_id TEXT PRIMARY KEY, kind TEXT NOT NULL, payload TEXT NOT NULL,
            synced INTEGER DEFAULT 0)""")
        self._c.commit()

    def add(self, kind: str, event_id: str, payload: dict) -> None:
        with self._lock:
            self._c.execute("INSERT OR IGNORE INTO outbox(event_id,kind,payload) VALUES(?,?,?)",
                            (event_id, kind, json.dumps(payload)))
            self._c.commit()

    def pending(self, limit: int) -> list[tuple[str, str, dict]]:
        with self._lock:
            rows = self._c.execute(
                "SELECT event_id,kind,payload FROM outbox WHERE synced=0 LIMIT ?", (limit,)).fetchall()
        return [(e, k, json.loads(p)) for e, k, p in rows]

    def mark_synced(self, ids: list[str]) -> None:
        if not ids:
            return
        with self._lock:
            self._c.executemany("UPDATE outbox SET synced=1 WHERE event_id=?", [(i,) for i in ids])
            self._c.commit()

    def pending_count(self) -> int:
        with self._lock:
            return self._c.execute("SELECT COUNT(*) FROM outbox WHERE synced=0").fetchone()[0]
