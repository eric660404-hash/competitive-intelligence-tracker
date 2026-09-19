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

brands = sorted(products["brand"].unique())
retailers = db.get_distinct_retailers()

c1, c2, c3, c4 = st.columns(4)
brand_filter = c1.multiselect("Brand", brands)
retailer_filter = c2.multiselect("Retailer", retailers)
date_from = c3.date_input("From", value=None)
date_to = c4.date_input("To", value=None)

filtered_obs = db.get_observations(
    brand=brand_filter[0] if len(brand_filter) == 1 else None,
    retailer=retailer_filter[0] if len(retailer_filter) == 1 else None,
    date_from=date_from or None,
    date_to=date_to or None,
)
# multi-value brand/retailer filters applied client-side since db helper takes single values
if brand_filter:
    filtered_obs = filtered_obs[filtered_obs["brand"].isin(brand_filter)]
if retailer_filter:
    filtered_obs = filtered_obs[filtered_obs["retailer"].isin(retailer_filter)]

relevant_product_ids = set(filtered_obs["product_id"]) if not observations.empty else set(products["id"])
if brand_filter or retailer_filter or date_from or date_to:
    view_products = products[products["id"].isin(relevant_product_ids)]
else:
    view_products = products

rows = []
for row in view_products.itertuples():
    product_obs = observations[observations["product_id"] == row.id]
    retailers_found = ", ".join(sorted(set(product_obs["retailer"]))) if not product_obs.empty else ""
    last_move = product_obs["date_observed"].max() if not product_obs.empty else ""
    rows.append(
        {
            "Brand": row.brand,
            "Product": row.product_name,
            "Target segment": row.target_segment,
            "Key message": row.key_message,
            "Price tier": row.price_tier,
            "Retailers found in": retailers_found,
            "# Observations": len(product_obs),
            "Last move date": last_move,
        }
    )

comparison_df = pd.DataFrame(rows)
st.dataframe(comparison_df, use_container_width=True, hide_index=True)

st.caption(f"{len(comparison_df)} product(s) shown.")
