import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent))

import streamlit as st

from src import db

st.set_page_config(page_title="Competitive Intelligence Tracker", page_icon="🧭", layout="wide")
db.init_db()

st.title("🧭 Competitive Intelligence & Positioning Tracker")
st.caption(
    "Log competitor moves as you see them, build a positioning profile per product, "
    "and turn it into a comparison view you can share."
)

products = db.get_products()
observations = db.get_observations()
pending = db.get_observations(only_pending=True)

col1, col2, col3 = st.columns(3)
col1.metric("Products tracked", len(products))
col2.metric("Observations logged", len(observations))
col3.metric("Pending review", len(pending))

if len(pending):
    st.warning(
        f"{len(pending)} auto-detected change(s) from the on-demand web check are waiting for your review. "
        "Go to **On-Demand Check** to confirm or discard them."
    )

st.divider()

if products.empty:
    st.info("No products tracked yet. Start on **Log Observation** to add your first competitor product.")
else:
    st.subheader("Recent observations")
    st.dataframe(
        observations.head(10)[
            ["observed_date", "brand_name", "category", "retailer_name", "move_type", "move_detail", "your_read"]
        ],
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.markdown(
    "**Pages:** Log Observation · Positioning Profiles · Comparison View · On-Demand Check · Export"
)
