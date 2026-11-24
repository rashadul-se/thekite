"""Presentation layer only. No SQL, no business rules."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pandas as pd
import streamlit as st
from app.container import build_service
from app.domain.models import VitalEvent, MedicationEvent

st.set_page_config(page_title="Elder Care Centre", page_icon="🏨", layout="wide")


@st.cache_resource(show_spinner="Connecting...")
def svc():
    return build_service()          # one shared service/pool for all sessions


care = svc()
st.sidebar.title("🏨 Care Concierge")
page = st.sidebar.radio("Go to", ["Dashboard", "Residents", "Record care", "Sync"])
offline = st.sidebar.toggle("Work offline", value=False)
s = care.status()
st.sidebar.caption(f"Postgres: {'🟢' if s['postgres'] else '🔴'}  Redis: {'🟢' if s['redis'] else '🔴'}  "
                   f"Pending: {s['pending_sync']}")

if page == "Dashboard":
    d = care.dashboard()
    a, b, c = st.columns(3)
    a.metric("Residents", d["total"]); b.metric("Red alerts", d["red"]); c.metric("Amber", d["amber"])
    st.subheader("Nurse priority list")
    st.dataframe(pd.DataFrame(d["top"]), use_container_width=True, hide_index=True)

elif page == "Residents":
    q = st.text_input("Search name or room")
    pg = st.number_input("Page", 0, 19, 0)
    df = care.residents(q, int(pg))
    st.dataframe(df, use_container_width=True, hide_index=True)
    rid = st.number_input("Open resident id", 1, 1000, 1)
    if st.button("View profile"):
        det = care.resident_detail(int(rid))
        for line in det["insights"]:
            st.info(line)
        if not det["vitals"].empty:
            st.line_chart(det["vitals"].set_index("ts")[["sleep_hrs", "mood", "temp"]])
        st.dataframe(det["meds"], use_container_width=True, hide_index=True)

elif page == "Record care":
    with st.form("vital"):
        rid = st.number_input("Resident id", 1, 1000, 1)
        c1, c2, c3, c4 = st.columns(4)
        hr = c1.number_input("HR", 30, 220, 75); temp = c2.number_input("Temp C", 30.0, 43.0, 36.7)
        spo2 = c3.number_input("SpO2", 50, 100, 96); mood = c4.slider("Mood", 1, 5, 3)
        sleep = c1.number_input("Sleep h", 0.0, 24.0, 7.0); steps = c2.number_input("Steps", 0, 30000, 2500)
        fl = c3.number_input("Fluids ml", 0, 5000, 1500)
        if st.form_submit_button("Save vitals"):
            try:
                st.success(care.record_vital(VitalEvent(int(rid), hr, temp, spo2, sleep, steps, mood, fl),
                                             online=not offline))
            except ValueError as e:
                st.error(str(e))
    with st.form("med"):
        mrid = st.number_input("Resident id ", 1, 1000, 1)
        drug = st.text_input("Drug", "Metformin 500mg")
        status = st.selectbox("Status", ["GIVEN", "REFUSED", "MISSED"])
        if st.form_submit_button("Log medication"):
            st.success(care.log_medication(MedicationEvent(int(mrid), drug, status), online=not offline))

else:
    st.write(f"Pending offline events: **{s['pending_sync']}**")
    if st.button("Sync now", disabled=offline):
        st.success(f"Synced {care.sync()} events")
