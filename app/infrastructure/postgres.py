"""PostgreSQL repository: pooled connections, bulk ops, idempotent inserts."""
from contextlib import contextmanager
import pandas as pd
from psycopg2.pool import ThreadedConnectionPool
from psycopg2.extras import execute_values

SCHEMA = """
CREATE TABLE IF NOT EXISTS residents(
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, age INT, room TEXT, conditions TEXT, diet TEXT);
CREATE TABLE IF NOT EXISTS vitals(
    event_id TEXT PRIMARY KEY, resident_id INT REFERENCES residents(id), ts TIMESTAMPTZ NOT NULL,
    hr INT, temp REAL, spo2 INT, sleep_hrs REAL, steps INT, mood INT, fluids_ml INT);
CREATE INDEX IF NOT EXISTS ix_vitals_res_ts ON vitals(resident_id, ts DESC);
CREATE TABLE IF NOT EXISTS med_log(
    event_id TEXT PRIMARY KEY, resident_id INT REFERENCES residents(id), ts TIMESTAMPTZ NOT NULL,
    drug TEXT, status TEXT);
CREATE INDEX IF NOT EXISTS ix_med_res_ts ON med_log(resident_id, ts DESC);
"""

_COLS = {
    "vitals": ("event_id", "resident_id", "ts", "hr", "temp", "spo2", "sleep_hrs", "steps", "mood", "fluids_ml"),
    "med_log": ("event_id", "resident_id", "ts", "drug", "status"),
}


class PostgresRepository:
    def __init__(self, dsn: str, minconn: int, maxconn: int):
        self._pool = ThreadedConnectionPool(minconn, maxconn, dsn)

    @contextmanager
    def _conn(self):
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    def init_schema(self) -> None:
        with self._conn() as c, c.cursor() as cur:
            cur.execute(SCHEMA)

    def ping(self) -> bool:
        try:
            with self._conn() as c, c.cursor() as cur:
                cur.execute("SELECT 1")
            return True
        except Exception:
            return False

    def count_residents(self) -> int:
        with self._conn() as c, c.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM residents")
            return cur.fetchone()[0]

    def insert_residents(self, rows: list[tuple]) -> None:
        with self._conn() as c, c.cursor() as cur:
            execute_values(cur, "INSERT INTO residents(name,age,room,conditions,diet) VALUES %s", rows)

    def bulk_insert(self, table: str, rows: list[dict]) -> None:
        cols = _COLS[table]          # whitelist: table name never comes from user input
        data = [tuple(r[c] for c in cols) for r in rows]
        with self._conn() as c, c.cursor() as cur:
            execute_values(cur, f"INSERT INTO {table}({','.join(cols)}) VALUES %s "
                                f"ON CONFLICT (event_id) DO NOTHING", data, page_size=1000)

    def list_residents(self, search: str, offset: int, limit: int) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql(
                "SELECT * FROM residents WHERE name ILIKE %s OR room ILIKE %s ORDER BY id OFFSET %s LIMIT %s",
                c, params=(f"%{search}%", f"%{search}%", offset, limit))

    def vitals_window(self, days: int) -> pd.DataFrame:
        with self._conn() as c:
            return pd.read_sql(
                "SELECT resident_id, ts, hr, temp, spo2, sleep_hrs, steps, mood, fluids_ml "
                "FROM vitals WHERE ts > now() - make_interval(days => %s)", c, params=(days,),
                parse_dates=["ts"])

    def resident_history(self, rid: int) -> tuple[pd.DataFrame, pd.DataFrame]:
        with self._conn() as c:
            v = pd.read_sql("SELECT ts,hr,temp,spo2,sleep_hrs,steps,mood,fluids_ml FROM vitals "
                            "WHERE resident_id=%s ORDER BY ts", c, params=(rid,), parse_dates=["ts"])
            m = pd.read_sql("SELECT ts,drug,status FROM med_log WHERE resident_id=%s "
                            "ORDER BY ts DESC LIMIT 50", c, params=(rid,))
        return v, m
