import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import db

st.set_page_config(page_title="Positioning Profiles", page_icon="📇", layout="wide")
db.init_db()

st.title("📇 Positioning Profiles")
st.caption("A structured profile per competitor product, built up from your logged observations.")

product_labels = db.get_product_labels()
if not product_labels:
    st.info("No products yet. Log an observation first to create one.")
    st.stop()

product_id = st.selectbox(
    "Product",
    list(product_labels.keys()),
    format_func=lambda pid: product_labels[pid],
)

product = db.get_product(product_id)
profile = db.get_profile(product_id)
obs = db.get_observations(product_id=product_id)
retailers_found = sorted(set(obs["retailer_name"])) if not obs.empty else []

st.subheader(f"{product['brand_name']} ({product['category']})")

with st.form("profile_form"):
    c1, c2 = st.columns(2)
    target_segment = c1.text_input("Target segment", value=profile["target_segment"])
    price_tier = c2.text_input("Price tier", value=profile["price_tier"])
    key_message = st.text_input("Key message / claim", value=profile["key_message"])
    profile_notes = st.text_area("Notes", value=profile["profile_notes"], height=80)

    st.text_input("Retailer(s) it's found in (auto-derived from observations)",
                   value=", ".join(retailers_found) if retailers_found else "—", disabled=True)

    if st.form_submit_button("Save profile", type="primary"):
        db.save_profile(
            product_id,
            target_segment=target_segment,
            key_message=key_message,
            price_tier=price_tier,
            profile_notes=profile_notes,
        )
        st.success("Profile saved.")
        st.rerun()

st.divider()
st.subheader("Insight history")

if obs.empty:
    st.caption("No observations logged for this product yet.")
else:
    for row in obs.itertuples():
        st.markdown(
            f"**{row.observed_date}** · {row.retailer_name} · _{row.move_type}_"
            + ("  ⏳ pending review" if not row.is_reviewed else "")
        )
        if row.move_detail:
            st.write(f"What happened: {row.move_detail}")
        if row.your_read:
            st.write(f"Read: {row.your_read}")
        st.markdown("---")

st.divider()
if st.button("Delete this product and all its observations", type="secondary"):
    db.delete_product(product_id)
    st.success("Product deleted.")
    st.rerun()
