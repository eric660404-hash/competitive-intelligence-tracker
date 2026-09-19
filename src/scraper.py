"""On-demand page fetching + snapshot diffing for monitored competitor URLs.

Static pages are fetched with requests/BeautifulSoup. If a URL is flagged
`needs_js`, Playwright renders it first (only if the playwright package and
its browser binaries are installed — this stays optional per the v1 brief).
"""

import re

import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

PRICE_PATTERN = re.compile(r"(NT\$|\$|USD|TWD)\s?[\d,]+(\.\d+)?")


class FetchError(Exception):
    pass


def _extract_from_html(html: str, selectors: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    def by_selector(css_selector):
        if not css_selector:
            return None
        el = soup.select_one(css_selector)
        return el.get_text(strip=True) if el else None

    def meta(*names):
        for name in names:
            tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
            if tag and tag.get("content"):
                return tag["content"].strip()
        return None

    title = (
        by_selector(selectors.get("title_selector"))
        or meta("og:title")
        or (soup.title.get_text(strip=True) if soup.title else "")
    )

    description = (
        by_selector(selectors.get("description_selector"))
        or meta("og:description", "description")
        or ""
    )

    price = by_selector(selectors.get("price_selector")) or meta("product:price:amount", "og:price:amount")
    if not price:
        match = PRICE_PATTERN.search(soup.get_text(" ", strip=True))
        price = match.group(0) if match else ""

    return {"title": title or "", "description": description or "", "price": price or ""}


def fetch_static(url: str) -> str:
    resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20)
    resp.raise_for_status()
    return resp.text


def fetch_rendered(url: str) -> str:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise FetchError(
            "This URL is flagged as needing JS rendering, but Playwright isn't installed. "
            "Run `pip install playwright` and `playwright install chromium`, or uncheck 'needs JS'."
        ) from exc

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=USER_AGENT)
            page.goto(url, timeout=30000, wait_until="networkidle")
            html = page.content()
            browser.close()
            return html
    except Exception as exc:
        raise FetchError(f"Playwright render failed for {url}: {exc}") from exc


def fetch_snapshot(url: str, needs_js: bool = False, selectors: dict | None = None) -> dict:
    """Fetch a URL and extract {title, price, description}."""
    selectors = selectors or {}
    try:
        html = fetch_rendered(url) if needs_js else fetch_static(url)
    except FetchError:
        raise
    except requests.RequestException as exc:
        raise FetchError(f"Could not fetch {url}: {exc}") from exc

    return _extract_from_html(html, selectors)


def diff_snapshot(old: dict, new: dict) -> list:
    """Return a list of {field, old, new} for fields that changed.

    Only compares non-empty old values so the first-ever check never
    reports a "change" against a blank baseline.
    """
    changes = []
    for field in ("title", "price", "description"):
        old_val = (old.get(field) or "").strip()
        new_val = (new.get(field) or "").strip()
        if old_val and new_val and old_val != new_val:
            changes.append({"field": field, "old": old_val, "new": new_val})
    return changes


def infer_move_type(changes: list) -> str:
    fields = {c["field"] for c in changes}
    if "price" in fields:
        return "Price change"
    if "description" in fields:
        return "New claim/message"
    if "title" in fields:
        return "Packaging change"
    return "New claim/message"
