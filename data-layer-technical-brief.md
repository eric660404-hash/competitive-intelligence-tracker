# Technical Brief: Data Layer Design (for future chat layer)

## Goal
Design a shared data layer across the Promo ROI Calculator, Competitive Intelligence & Positioning Tracker, and the future North Taipei survey segmentation tool — so a later chat/RAG layer can query across all of them without inconsistent naming or duplicated entities.

## Design Principles
1. **Share core entities across tools — don't let each tool build its own.** All three tools reference "brand/product" and "retailer/channel." These must use the same ID system, or a chat layer querying across tools will fail to match records.
2. **Structured fields + free-text fields coexist.** Numeric data (price, ROI, %) goes in structured fields for direct querying/calculation. Judgment/insight ("your read," rationale) goes in free-text fields, meant to be read directly by an AI model later.
3. **Every record should answer who, where, when, why.** This is what the future chat layer will filter on.
4. **v1 uses plain database queries — no embeddings/vector search yet.** At small data volumes, SQL filtering is sufficient. Upgrade to embeddings only once volume grows enough that keyword/ID filtering stops being precise enough.

---

## Shared Core Tables

### `retailers` (channel master table)
- `retailer_id` (primary key)
- `name` (e.g., "Pharmacy Chain A")
- `type` (pharmacy chain / distributor / independent account)
- `region` (e.g., North Taipei)

### `brands_products` (product master table, own brand + competitors)
- `product_id` (primary key)
- `brand_name`
- `is_own_brand` (true/false)
- `category` (infant formula / growing-up formula / supplement)

These two master tables are the anchor — all three tools must reference the same retailer list and product list rather than each maintaining their own.

---

## Per-Tool Tables (all reference the master tables above)

### Promo ROI Calculator → `promo_scenarios`
- `scenario_id`
- `product_id` (FK)
- `retailer_id` (FK)
- `mechanic_type`, `depth`, `duration`, `baseline_sales`, `margin`, `trade_spend`
- `expected_lift`, `breakeven_lift`, `net_margin_impact` (calculated outputs)
- `notes` (free text — the "why" behind this scenario: rationale for the mechanic/depth choice, competitive response, retailer ask, seasonal timing; per principle 3, meant to be read directly by an AI model later, same role as `your_read` in `observations`)
- `created_date`

### Competitive Intelligence Tracker → `observations`
- `observation_id`
- `product_id` (FK)
- `retailer_id` (FK)
- `observed_date`
- `move_type` (price change / new launch / new claim / packaging change / promo mechanic)
- `move_detail` (free text)
- `your_read` (free text — important for the chat layer, since this captures reasoning/judgment)

### Competitive Intelligence Tracker → `positioning_profiles` (one per competitor product, updated as observations accumulate)
- `product_id` (FK)
- `target_segment`, `key_message`, `price_tier`
- `last_updated`

### North Taipei Survey (future) → `survey_responses` + `segments`
- Individual response records plus resulting persona/segment assignments, each tagged with `retailer_id` (which retailer the respondent was surveyed at)

---

## Why This Enables the Future Chat Layer

When a future question like "what should Chain B's next promo be?" comes in, the chat layer's logic would be:

```sql
SELECT * FROM promo_scenarios WHERE retailer_id = 'Chain_B'
SELECT * FROM observations WHERE retailer_id = 'Chain_B'
SELECT * FROM positioning_profiles WHERE product_id IN (competitors relevant to Chain B)
SELECT * FROM segments WHERE retailer_id = 'Chain_B'
```

Because every table shares the same `retailer_id` and `product_id`, these queries can run together and feed directly into an AI prompt. If each tool used a different naming convention for the same retailer (e.g., "B chain" vs. "Chain-B"), the chat layer would fail to match records — this is the most common failure point to avoid.

## Action Items Now (don't wait for the chat-layer phase)
1. Define `retailers` and `brands_products` as the two master tables first; every tool should look up or create IDs against these rather than inventing its own names
2. Every table should store a `created_date` or `observed_date` for later time-based filtering/sorting
3. Free-text fields (`your_read`, `move_detail`, `notes`) can stay as normal prose — no special formatting needed, since these will eventually be read directly by an AI model
