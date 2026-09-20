"""Shared Streamlit widgets for picking or adding a retailer/product against
the shared master tables (src/db.py), so every page uses the same retailer_id/
product_id instead of a free-typed label."""

import streamlit as st

from src import db


def select_or_add_retailer(key_prefix, allow_none=False):
    labels = db.get_retailer_labels()
    options = (["(none)"] if allow_none else []) + list(labels.keys())
    retailer_id = st.selectbox(
        "Retailer / channel",
        options=options,
        format_func=lambda rid: "(none)" if rid == "(none)" else labels[rid],
        key=f"{key_prefix}_retailer_id",
    )
    with st.popover("+ New retailer"):
        new_name = st.text_input("Name", placeholder="e.g. Costco, Shopee, PChome", key=f"{key_prefix}_new_retailer_name")
        new_type = st.selectbox("Type", db.RETAILER_TYPES, key=f"{key_prefix}_new_retailer_type")
        new_region = st.text_input("Region", value="North Taipei", key=f"{key_prefix}_new_retailer_region")
        if st.button("Add retailer", key=f"{key_prefix}_add_retailer"):
            if new_name.strip():
                db.add_retailer(new_name, new_type, new_region)
                st.rerun()
    return None if retailer_id == "(none)" else retailer_id


def select_or_add_product(key_prefix):
    labels = db.get_product_labels()
    options = ["+ New product"] + list(labels.keys())
    choice = st.selectbox(
        "Product",
        options=options,
        format_func=lambda pid: "+ New product" if pid == "+ New product" else labels[pid],
        key=f"{key_prefix}_product_choice",
    )

    if choice != "+ New product":
        return choice

    with st.container(border=True):
        st.caption("New product — creates an entry in the shared brands_products master table.")
        new_brand = st.text_input(
            "Brand / product name",
            placeholder="e.g. CompetitorX UltraPremium 900g",
            key=f"{key_prefix}_new_product_brand",
        )
        new_category = st.selectbox("Category", db.PRODUCT_CATEGORIES, key=f"{key_prefix}_new_product_category")
        new_is_own = st.checkbox("Own brand", value=False, key=f"{key_prefix}_new_product_own")
        if st.button("Add product", key=f"{key_prefix}_add_product"):
            if new_brand.strip():
                new_id = db.add_product(new_brand, new_is_own, new_category)
                st.session_state[f"{key_prefix}_product_choice"] = new_id
                st.rerun()
            else:
                st.error("Brand / product name is required.")
        return None
