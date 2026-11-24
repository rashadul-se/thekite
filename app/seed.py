"""Generates 1000 residents with 14 days of vitals (vectorised, bulk-loaded)."""
import uuid
import numpy as np
import pandas as pd
from app.domain.models import VitalEvent  # noqa: F401  (documents the schema)

CONDS = ["Hypertension", "Diabetes", "Dementia", "Arthritis", "Heart disease", "None"]
DIETS = ["Regular", "Diabetic", "Soft", "Low-salt", "Vegetarian"]


def seed(repo, n: int = 1000, days: int = 14) -> None:
    rng = np.random.default_rng(42)
    repo.insert_residents([
        (f"Resident {i:04d}", int(rng.integers(65, 98)), f"R{100 + i // 4}-{i % 4}",
         rng.choice(CONDS), rng.choice(DIETS)) for i in range(1, n + 1)])
    ids = np.repeat(np.arange(1, n + 1), days)
    day = np.tile(np.arange(days)[::-1], n)
    ts = pd.Timestamp.now(tz="UTC").floor("D") - pd.to_timedelta(day, unit="D") + pd.Timedelta(hours=8)
    N = n * days
    sleep = rng.normal(7, 1, N).clip(3, 10)
    steps = rng.normal(2500, 700, N).clip(200, None)
    mood = np.clip(np.round(2 + sleep / 3 + rng.normal(0, 0.7, N)), 1, 5)   # embedded pattern
    rows = [dict(event_id=uuid.uuid4().hex, resident_id=int(r), ts=t.isoformat(),
                 hr=int(h), temp=round(float(tp), 1), spo2=int(s), sleep_hrs=round(float(sl), 1),
                 steps=int(st), mood=int(m), fluids_ml=int(f))
            for r, t, h, tp, s, sl, st, m, f in zip(
                ids, ts, rng.normal(74, 9, N), rng.normal(36.7, 0.35, N), rng.normal(96, 1.8, N).clip(85, 100),
                sleep, steps, mood, rng.normal(1500, 350, N).clip(300, None))]
    for i in range(0, N, 5000):
        repo.bulk_insert("vitals", rows[i:i + 5000])
