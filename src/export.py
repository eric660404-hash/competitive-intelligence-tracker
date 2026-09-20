"""Builds the shareable one-pager summarizing the competitive landscape."""

from datetime import date

from fpdf import FPDF

PAGE_WIDTH = 190


class OnePager(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 16)
        self.cell(0, 10, "Competitive Landscape - Positioning Summary", ln=True)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(110, 110, 110)
        self.cell(0, 6, f"Generated {date.today().isoformat()}", ln=True)
        self.set_text_color(0, 0, 0)
        self.ln(2)


def _truncate(text: str, limit: int) -> str:
    text = (text or "").replace("\n", " ").strip()
    return text if len(text) <= limit else text[: limit - 1] + "..."


def build_one_pager(products_df, observations_df, profiles_by_product: dict, retailers_by_product: dict) -> bytes:
    """products_df: one row per tracked product (brands_products master table).
    observations_df: all observations, used to pull the latest 1-2 reads per product.
    profiles_by_product: {product_id: positioning_profiles dict}
    retailers_by_product: {product_id: "Retailer A, Retailer B"}
    """
    pdf = OnePager(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_page()

    # --- Comparison table -------------------------------------------------
    col_widths = [35, 30, 40, 35, 60, 40]
    headers = ["Brand / product", "Category", "Target segment", "Price tier", "Key message", "Retailers"]

    pdf.set_font("Helvetica", "B", 9)
    pdf.set_fill_color(235, 235, 240)
    for w, h in zip(col_widths, headers):
        pdf.cell(w, 8, h, border=1, fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 8)
    for row in products_df.itertuples():
        profile = profiles_by_product.get(row.product_id, {})
        values = [
            _truncate(row.brand_name, 22),
            _truncate(row.category, 18),
            _truncate(profile.get("target_segment", ""), 26),
            _truncate(profile.get("price_tier", ""), 20),
            _truncate(profile.get("key_message", ""), 42),
            _truncate(retailers_by_product.get(row.product_id, ""), 26),
        ]
        for w, v in zip(col_widths, values):
            pdf.cell(w, 7, v, border=1)
        pdf.ln()

    # --- Key reads section --------------------------------------------------
    pdf.ln(6)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 8, "Key reads by product", ln=True)
    pdf.set_font("Helvetica", "", 9)

    for row in products_df.itertuples():
        product_obs = (
            observations_df[observations_df["product_id"] == row.product_id]
            .sort_values("observed_date", ascending=False)
            .head(2)
        )
        if product_obs.empty:
            continue
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"{row.brand_name} ({row.category})", ln=True)
        pdf.set_font("Helvetica", "", 9)
        for obs in product_obs.itertuples():
            read = _truncate(obs.your_read or obs.move_detail, 140)
            line = f"  {obs.observed_date} ({obs.retailer_name}, {obs.move_type}): {read}"
            pdf.multi_cell(0, 5, line)
        pdf.ln(1)

    raw = pdf.output()
    return raw.encode("latin-1") if isinstance(raw, str) else bytes(raw)
