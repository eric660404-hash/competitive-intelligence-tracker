# Competitive Intelligence & Positioning Tracker

**Live demo:** https://competitive-intelligence-tracker.streamlit.app/

Logs competitor moves (launches, price changes, promos, new claims) as they're
observed in-market, and turns them into a structured, comparable positioning
view — so insight is captured in the moment instead of lost, and can be shared
as a one-pager for a manager update or interview talking point.

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# optional, only for URLs flagged "needs JS rendering":
pip install playwright
playwright install chromium

copy .env.example .env        # then fill in SMTP creds for change-detection emails
```

## Run

```bash
streamlit run Home.py
```

## Pages

- **Log Observation** — capture a competitor move: brand/product, retailer,
  date, move type, what happened, and your read on why.
- **Positioning Profiles** — a per-product profile (target segment, key
  message, price tier) that rolls up all your observations into an insight
  history.
- **Comparison View** — all tracked products side by side, filterable by
  brand, retailer, and date range.
- **On-Demand Check** — maintain a list of known competitor URLs; click
  "Check now" to fetch each one, diff it against the last saved snapshot, and
  auto-create a pre-filled (unreviewed) observation plus an email alert when
  something changed. No background/scheduled monitoring in v1.
- **Export** — generate a clean one-pager PDF summarizing the positioning
  table and your most recent reads per product.

## Notes

- Data is stored locally in `data/tracker.db` (SQLite) — nothing leaves your
  machine except the optional change-notification email and the page fetches
  in On-Demand Check.
- If a monitored site renders content with JavaScript, check "needs JS
  rendering" for that URL — this requires the optional `playwright` package.
  Sites without it are checked with plain HTTP + HTML parsing.
- Email notifications require `SMTP_USER`, `SMTP_PASSWORD`, and `NOTIFY_EMAIL`
  in `.env` — the check still runs and logs the observation without them, it
  just skips sending the email.
- **Streamlit Community Cloud caveat:** the hosted demo's filesystem is
  ephemeral — `data/tracker.db` resets whenever the app reboots (a redeploy,
  a code push, or waking from sleep after inactivity). That's fine for a
  portfolio demo; for real day-to-day tracking, run it locally so your data
  persists.
