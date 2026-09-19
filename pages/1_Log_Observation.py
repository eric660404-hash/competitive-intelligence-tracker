import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import db

st.set_page_config(page_title="Log Observation", page_icon="📝", layout="wide")
db.init_db()

st.title("📝 Log an Observation")

product_labels = db.get_product_labels()
options = ["+ New product"] + [f"{pid}::{label}" for pid, label in product_labels.items()]

choice = st.selectbox("Product", options, index=len(options) - 1 if len(options) > 1 else 0)

new_product = choice == "+ New product"
product_id = None

with st.form("observation_form", clear_on_submit=True):
    if new_product:
        c1, c2 = st.columns(2)
        brand = c1.text_input("Brand *")
        product_name = c2.text_input("Product name *")
        st.caption("You can fill in target segment / key message / price tier later on Positioning Profiles.")
    else:
        product_id = int(choice.split("::")[0])
        brand, product_name = None, None

    c1, c2, c3 = st.columns(3)
    retailer = c1.text_input("Retailer / channel *", placeholder="e.g., Costco, Shopee, PChome")
    date_observed = c2.date_input("Date observed", value=date.today())
    move_type = c3.selectbox("Move type", db.MOVE_TYPES)

    move_detail = st.text_area("Move detail — what exactly happened", height=90)
    insight_read = st.text_area("Your read — why, and who they're targeting", height=90)

    submitted = st.form_submit_button("Log observation", type="primary")

    if submitted:
        errors = []
        if new_product and (not brand or not product_name):
            errors.append("Brand and product name are required for a new product.")
        if not retailer:
            errors.append("Retailer / channel is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            if new_product:
                product_id = db.add_product(brand, product_name)
            db.add_observation(
                product_id=product_id,
                retailer=retailer,
                date_observed=date_observed,
                move_type=move_type,
                move_detail=move_detail,
                insight_read=insight_read,
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
        with st.expander(f"{row.date_observed} — {row.brand} {row.product_name} @ {row.retailer} ({row.move_type})"):
            st.write(f"**Move detail:** {row.move_detail or '_none_'}")
            st.write(f"**Your read:** {row.insight_read or '_none_'}")
            bcol, dcol = st.columns([1, 5])
            if bcol.button("Delete", key=f"del_{row.id}"):
                db.delete_observation(int(row.id))
                st.rerun()
