import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from src import db

st.set_page_config(page_title="Comparison View", page_icon="📊", layout="wide")
db.init_db()

st.title("📊 Comparison View")
st.caption("All tracked competitor products, side by side, across the positioning framework.")

products = db.get_products()
observations = db.get_observations()

if products.empty:
    st.info("No products tracked yet.")
    st.stop()

brands = sorted(products["brand_name"].unique())
retailers = sorted(observations["retailer_name"].unique()) if not observations.empty else []

c1, c2, c3, c4 = st.columns(4)
brand_filter = c1.multiselect("Brand / product", brands)
retailer_filter = c2.multiselect("Retailer", retailers)
date_from = c3.date_input("From", value=None)
date_to = c4.date_input("To", value=None)

filtered_obs = observations.copy()
if retailer_filter:
    filtered_obs = filtered_obs[filtered_obs["retailer_name"].isin(retailer_filter)]
if date_from:
    filtered_obs = filtered_obs[filtered_obs["observed_date"] >= str(date_from)]
if date_to:
    filtered_obs = filtered_obs[filtered_obs["observed_date"] <= str(date_to)]

view_products = products
if brand_filter:
    view_products = view_products[view_products["brand_name"].isin(brand_filter)]
if retailer_filter or date_from or date_to:
    relevant_product_ids = set(filtered_obs["product_id"])
    view_products = view_products[view_products["product_id"].isin(relevant_product_ids)]

rows = []
for row in view_products.itertuples():
    product_obs = observations[observations["product_id"] == row.product_id]
    if retailer_filter or date_from or date_to:
        product_obs = filtered_obs[filtered_obs["product_id"] == row.product_id]
    profile = db.get_profile(row.product_id)
    retailers_found = ", ".join(sorted(set(product_obs["retailer_name"]))) if not product_obs.empty else ""
    last_move = product_obs["observed_date"].max() if not product_obs.empty else ""
    rows.append(
        {
            "Brand / product": row.brand_name,
            "Category": row.category,
            "Target segment": profile["target_segment"],
            "Key message": profile["key_message"],
            "Price tier": profile["price_tier"],
            "Retailers found in": retailers_found,
            "# Observations": len(product_obs),
            "Last move date": last_move,
        }
    )

comparison_df = pd.DataFrame(rows)
st.dataframe(comparison_df, use_container_width=True, hide_index=True)

st.caption(f"{len(comparison_df)} product(s) shown.")
