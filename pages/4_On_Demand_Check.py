import sys
from datetime import date
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import streamlit as st

from src import db, emailer, scraper
from src.ui_helpers import select_or_add_retailer

st.set_page_config(page_title="On-Demand Check", page_icon="🔎", layout="wide")
db.init_db()

st.title("🔎 On-Demand Web Check")
st.caption(
    "Maintain a short list of known competitor URLs (their own site, or a Shopee/momo/PChome listing). "
    "Nothing runs on a schedule — checks only happen when you click the button below."
)

product_labels = db.get_product_labels()

# ------------------------------------------------------------- add a URL
with st.expander("➕ Add a monitored URL", expanded=product_labels == {}):
    if not product_labels:
        st.info("Add a product first via **Log Observation**.")
    else:
        product_id = st.selectbox(
            "Product", list(product_labels.keys()), format_func=lambda pid: product_labels[pid], key="addurl_product"
        )
        retailer_id = select_or_add_retailer("addurl", allow_none=True)
        with st.form("add_url_form", clear_on_submit=True):
            url = st.text_input("URL")
            needs_js = st.checkbox(
                "Needs JS rendering (site content loads dynamically — requires Playwright installed)"
            )
            with st.expander("Advanced: CSS selectors (optional, improves accuracy on tricky sites)"):
                title_selector = st.text_input("Title selector", placeholder="e.g. h1.product-title")
                price_selector = st.text_input("Price selector", placeholder="e.g. span.price")
                description_selector = st.text_input("Description selector", placeholder="e.g. div.product-desc")

            if st.form_submit_button("Add URL", type="primary"):
                if not url:
                    st.error("URL is required.")
                else:
                    db.add_monitored_url(
                        product_id, url, retailer_id, needs_js,
                        title_selector, price_selector, description_selector,
                    )
                    st.success("URL added.")
                    st.rerun()

st.divider()

# ------------------------------------------------------------- monitored list + check now
urls_df = db.get_monitored_urls()

if urls_df.empty:
    st.info("No monitored URLs yet.")
else:
    st.subheader("Monitored URLs")
    display_df = urls_df.copy()
    display_df["retailer_name"] = display_df["retailer_name"].fillna("(none)")
    st.dataframe(
        display_df[["brand_name", "category", "retailer_name", "url", "needs_js", "last_price", "last_checked_at"]],
        use_container_width=True,
        hide_index=True,
    )

    del_id = st.selectbox(
        "Remove a URL",
        [None] + list(urls_df["id"]),
        format_func=lambda i: "—" if i is None else urls_df.set_index("id").loc[i, "url"],
    )
    if del_id and st.button("Remove selected URL"):
        db.delete_monitored_url(int(del_id))
        st.rerun()

    st.divider()

    if st.button("🔄 Check now", type="primary"):
        results = []
        with st.spinner(f"Checking {len(urls_df)} URL(s)..."):
            for row in urls_df.itertuples():
                selectors = {
                    "title_selector": row.title_selector,
                    "price_selector": row.price_selector,
                    "description_selector": row.description_selector,
                }
                product_label = f"{row.brand_name} ({row.category})"
                try:
                    snapshot = scraper.fetch_snapshot(row.url, bool(row.needs_js), selectors)
                except scraper.FetchError as exc:
                    results.append({"url": row.url, "status": "error", "detail": str(exc)})
                    continue

                old = {"title": row.last_title, "price": row.last_price, "description": row.last_description}
                changes = scraper.diff_snapshot(old, snapshot)
                db.update_snapshot(row.id, snapshot["title"], snapshot["price"], snapshot["description"])

                if changes:
                    move_type = scraper.infer_move_type(changes)
                    detail_lines = [f"{c['field'].title()}: '{c['old']}' -> '{c['new']}'" for c in changes]
                    if row.retailer_id:
                        obs_retailer_id = row.retailer_id
                    else:
                        obs_retailer_id = db.add_retailer("(from URL check)", "Independent account", "Unknown")
                    db.add_observation(
                        product_id=row.product_id,
                        retailer_id=obs_retailer_id,
                        observed_date=date.today(),
                        move_type=move_type,
                        move_detail="Auto-detected change on check:\n" + "\n".join(detail_lines),
                        your_read="",
                        source="auto",
                        is_reviewed=False,
                    )
                    email_note = ""
                    try:
                        emailer.send_change_notification(product_label, row.url, changes)
                    except emailer.EmailNotConfigured:
                        email_note = " (email not sent — SMTP not configured in .env)"
                    except Exception as exc:  # SMTP delivery failure shouldn't block the check
                        email_note = f" (email failed: {exc})"
                    results.append(
                        {"url": row.url, "status": "changed", "detail": ", ".join(c["field"] for c in changes) + email_note}
                    )
                else:
                    results.append({"url": row.url, "status": "no change", "detail": ""})

        for r in results:
            if r["status"] == "changed":
                st.success(f"Change detected — {r['url']}: {r['detail']}")
            elif r["status"] == "error":
                st.error(f"{r['url']}: {r['detail']}")
            else:
                st.write(f"No change — {r['url']}")

st.divider()

# ------------------------------------------------------------- pending review
st.subheader("⏳ Pending review (auto-detected)")
pending = db.get_observations(only_pending=True)

if pending.empty:
    st.caption("Nothing waiting for review.")
else:
    for row in pending.itertuples():
        with st.expander(
            f"{row.observed_date} — {row.brand_name} ({row.category}) @ {row.retailer_name} ({row.move_type})"
        ):
            move_detail = st.text_area("Move detail", value=row.move_detail, key=f"detail_{row.observation_id}")
            your_read = st.text_area("Your read", value=row.your_read, key=f"read_{row.observation_id}")
            c1, c2 = st.columns(2)
            if c1.button("Confirm", key=f"confirm_{row.observation_id}", type="primary"):
                db.update_observation(
                    row.observation_id, move_detail=move_detail, your_read=your_read, is_reviewed=True
                )
                st.rerun()
            if c2.button("Discard", key=f"discard_{row.observation_id}"):
                db.delete_observation(row.observation_id)
                st.rerun()
