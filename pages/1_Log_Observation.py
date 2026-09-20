import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import db
from src.ui_helpers import select_or_add_product, select_or_add_retailer

st.set_page_config(page_title="Log Observation", page_icon="📝", layout="wide")
db.init_db()

st.title("📝 Log an Observation")

c1, c2 = st.columns(2)
with c1:
    product_id = select_or_add_product("log")
with c2:
    retailer_id = select_or_add_retailer("log")

with st.form("observation_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    date_observed = c1.date_input("Date observed", value=date.today())
    move_type = c2.selectbox("Move type", db.MOVE_TYPES)

    move_detail = st.text_area("Move detail — what exactly happened", height=90)
    your_read = st.text_area("Your read — why, and who they're targeting", height=90)

    submitted = st.form_submit_button("Log observation", type="primary")

    if submitted:
        errors = []
        if not product_id:
            errors.append("Pick or add a product above first.")
        if not retailer_id:
            errors.append("Pick or add a retailer / channel above first.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            db.add_observation(
                product_id=product_id,
                retailer_id=retailer_id,
                observed_date=date_observed,
                move_type=move_type,
                move_detail=move_detail,
                your_read=your_read,
                source="manual",
                is_reviewed=True,
            )
            st.success("Observation logged.")
            st.rerun()

st.divider()
st.subheader("Recent observations")

obs = db.get_observations()
if obs.empty:
    st.caption("Nothing logged yet.")
else:
    for row in obs.head(25).itertuples():
        with st.expander(
            f"{row.observed_date} — {row.brand_name} ({row.category}) @ {row.retailer_name} ({row.move_type})"
        ):
            st.write(f"**Move detail:** {row.move_detail or '_none_'}")
            st.write(f"**Your read:** {row.your_read or '_none_'}")
            bcol, dcol = st.columns([1, 5])
            if bcol.button("Delete", key=f"del_{row.observation_id}"):
                db.delete_observation(row.observation_id)
                st.rerun()
