"""Insight engine: vectorised baseline-vs-today analysis for all residents at once."""
import numpy as np
import pandas as pd

_RULES = {  # flag -> (description, weight)
    "fever": ("Temp >= 37.8C", 3),
    "low_spo2": ("SpO2 < 92%", 4),
    "sleep_drop": ("Sleep down 2h+ vs own baseline", 2),
    "activity_drop": ("Steps down 40%+ vs baseline", 2),
    "low_mood": ("Mood <= 2", 1),
    "dehydration": ("Fluids < 1000 ml", 2),
}


class InsightEngine:
    """Pure logic, no I/O. AI suggests; clinicians decide."""

    @staticmethod
    def daily_risk(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame()
        df = df.assign(day=df["ts"].dt.date)
        latest = df["day"].max()
        today = df[df["day"] == latest].groupby("resident_id").last()
        base = df[df["day"] < latest].groupby("resident_id")[["sleep_hrs", "steps"]].mean().add_suffix("_base")
        t = today.join(base)
        t["fever"] = t["temp"] >= 37.8
        t["low_spo2"] = t["spo2"] < 92
        t["sleep_drop"] = (t["sleep_hrs_base"] - t["sleep_hrs"]) >= 2
        t["activity_drop"] = t["steps"] < 0.6 * t["steps_base"]
        t["low_mood"] = t["mood"] <= 2
        t["dehydration"] = t["fluids_ml"] < 1000
        t["risk_score"] = sum(t[f].astype(int) * w for f, (_, w) in _RULES.items())
        t["reasons"] = t[list(_RULES)].apply(
            lambda r: ", ".join(_RULES[k][0] for k in _RULES if r[k]), axis=1)
        t["level"] = pd.cut(t["risk_score"], [-1, 1, 3, 99], labels=["Green", "Amber", "Red"])
        return t.reset_index().sort_values("risk_score", ascending=False)

    @staticmethod
    def patterns(hist: pd.DataFrame) -> list[str]:
        """Hypotheses for one resident, to be tested over 7-14 days."""
        out = []
        if len(hist) < 5:
            return ["Not enough data yet (need 5+ days)."]
        h = hist.sort_values("ts").reset_index(drop=True)
        h["next_mood"] = h["mood"].shift(-1)
        for a, b, text in (("sleep_hrs", "next_mood", "Poor sleep -> lower mood next day"),
                           ("steps", "mood", "More activity -> better mood"),
                           ("fluids_ml", "temp", "Low fluids -> higher temperature")):
            c = h[a].corr(h[b])
            if pd.notna(c) and abs(c) >= 0.4:
                direction = "supported" if (c > 0) == (b != "temp") else "inverse"
                out.append(f"Hypothesis: {text} (r={c:.2f}, {direction}). Test 7-14 days, adjust plan.")
        slope = np.polyfit(range(len(h)), h["sleep_hrs"], 1)[0]
        if slope < -0.1:
            out.append("Trend: sleep declining; review evening routine and medication timing.")
        return out or ["No strong pattern detected."]
