import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import db, export

st.set_page_config(page_title="Export", page_icon="📤", layout="wide")
db.init_db()

st.title("📤 Share the Competitive Landscape")
st.caption(
    "Export a clean one-pager for a manager update or interview talking point — "
    "your positioning read on the market, not a raw data dump."
)

products = db.get_products()
observations = db.get_observations()

if products.empty:
    st.info("Nothing to export yet — log some observations first.")
    st.stop()

profiles_by_product = {pid: db.get_profile(pid) for pid in products["product_id"]}
retailers_by_product = {}
for pid in products["product_id"]:
    obs = observations[observations["product_id"] == pid]
    retailers_by_product[pid] = ", ".join(sorted(set(obs["retailer_name"]))) if not obs.empty else ""

st.subheader("Preview")
preview_rows = [
    {
        "brand_name": row.brand_name,
        "category": row.category,
        "target_segment": profiles_by_product[row.product_id]["target_segment"],
        "price_tier": profiles_by_product[row.product_id]["price_tier"],
        "key_message": profiles_by_product[row.product_id]["key_message"],
    }
    for row in products.itertuples()
]
st.dataframe(preview_rows, use_container_width=True, hide_index=True)

if st.button("Generate one-pager PDF", type="primary"):
    pdf_bytes = export.build_one_pager(products, observations, profiles_by_product, retailers_by_product)
    st.session_state["one_pager_pdf"] = pdf_bytes
    st.success("One-pager generated.")

if "one_pager_pdf" in st.session_state:
    st.download_button(
        "⬇️ Download PDF",
        data=st.session_state["one_pager_pdf"],
        file_name="competitive-landscape-summary.pdf",
        mime="application/pdf",
    )
