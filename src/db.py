"""SQLite persistence layer for the Competitive Intelligence Tracker.

Schema follows data-layer-technical-brief.md. `retailers` and `brands_products`
are the shared master tables — every entry looks up or creates an id against
these instead of free-typing a retailer/brand name, and their id generation
(`_slugify`) is kept byte-for-byte identical to promo-roi-calculator's
data_layer.py so the same name produces the same retailer_id/product_id in
both tools, even though each tool keeps its own local database file.
"""

import re
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tracker.db"

RETAILER_TYPES = ["Pharmacy chain", "Distributor", "Independent account"]
PRODUCT_CATEGORIES = ["Infant formula", "Growing-up formula", "Supplement"]

MOVE_TYPES = [
    "New launch",
    "Price change",
    "New claim/message",
    "Packaging change",
    "Promo mechanic",
]


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS retailers (
            retailer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            region TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS brands_products (
            product_id TEXT PRIMARY KEY,
            brand_name TEXT NOT NULL,
            is_own_brand INTEGER NOT NULL,
            category TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS positioning_profiles (
            product_id TEXT PRIMARY KEY REFERENCES brands_products(product_id) ON DELETE CASCADE,
            target_segment TEXT DEFAULT '',
            key_message TEXT DEFAULT '',
            price_tier TEXT DEFAULT '',
            profile_notes TEXT DEFAULT '',
            last_updated TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observations (
            observation_id TEXT PRIMARY KEY,
            product_id TEXT NOT NULL REFERENCES brands_products(product_id) ON DELETE CASCADE,
            retailer_id TEXT NOT NULL REFERENCES retailers(retailer_id),
            observed_date TEXT NOT NULL,
            move_type TEXT NOT NULL,
            move_detail TEXT DEFAULT '',
            your_read TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            is_reviewed INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS monitored_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id TEXT NOT NULL REFERENCES brands_products(product_id) ON DELETE CASCADE,
            retailer_id TEXT REFERENCES retailers(retailer_id),
            url TEXT NOT NULL,
            needs_js INTEGER NOT NULL DEFAULT 0,
            title_selector TEXT DEFAULT '',
            price_selector TEXT DEFAULT '',
            description_selector TEXT DEFAULT '',
            last_title TEXT DEFAULT '',
            last_price TEXT DEFAULT '',
            last_description TEXT DEFAULT '',
            last_checked_at TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )
    conn.commit()
    conn.close()


def _now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_")
    return slug or uuid.uuid4().hex[:8]


# -------------------------------------------------------------- retailers

def get_retailers() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM retailers ORDER BY name", conn)
    conn.close()
    return df


def get_retailer_labels() -> dict:
    df = get_retailers()
    return {r.retailer_id: r.name for r in df.itertuples()}


def add_retailer(name, type_, region) -> str:
    """Insert into the shared retailers master table; returns its retailer_id.

    Uses the same slug as promo-roi-calculator's data_layer.add_retailer, so
    entering the same name in either tool yields the same retailer_id.
    """
    retailer_id = _slugify(name)
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO retailers (retailer_id, name, type, region) VALUES (?, ?, ?, ?)",
        (retailer_id, name.strip(), type_, region),
    )
    conn.commit()
    conn.close()
    return retailer_id


# ---------------------------------------------------------- brands_products

def get_products() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM brands_products ORDER BY brand_name", conn)
    conn.close()
    return df


def get_product(product_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM brands_products WHERE product_id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_labels() -> dict:
    """Return {product_id: 'Brand/product (category)'} for select boxes."""
    df = get_products()
    return {r.product_id: f"{r.brand_name} ({r.category})" for r in df.itertuples()}


def add_product(brand_name, is_own_brand, category) -> str:
    """Insert into the shared brands_products master table; returns its product_id.

    Uses the same slug as promo-roi-calculator's data_layer.add_product. `brand_name`
    can be as specific as needed (e.g. "CompetitorX UltraPremium 900g") to distinguish
    competing SKUs, matching whatever granularity the other tools' entries use.
    """
    product_id = _slugify(f"{brand_name}_{category}")
    conn = get_connection()
    conn.execute(
        "INSERT OR IGNORE INTO brands_products (product_id, brand_name, is_own_brand, category) VALUES (?, ?, ?, ?)",
        (product_id, brand_name.strip(), int(is_own_brand), category),
    )
    conn.commit()
    conn.close()
    return product_id


def delete_product(product_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM brands_products WHERE product_id = ?", (product_id,))
    conn.commit()
    conn.close()


# ------------------------------------------------------- positioning_profiles

def get_profile(product_id: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM positioning_profiles WHERE product_id = ?", (product_id,)
    ).fetchone()
    conn.close()
    if row:
        return dict(row)
    return {
        "product_id": product_id,
        "target_segment": "",
        "key_message": "",
        "price_tier": "",
        "profile_notes": "",
        "last_updated": "",
    }


def save_profile(product_id, target_segment="", key_message="", price_tier="", profile_notes="") -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO positioning_profiles (product_id, target_segment, key_message, price_tier, profile_notes, last_updated)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(product_id) DO UPDATE SET
            target_segment = excluded.target_segment,
            key_message = excluded.key_message,
            price_tier = excluded.price_tier,
            profile_notes = excluded.profile_notes,
            last_updated = excluded.last_updated
        """,
        (product_id, target_segment, key_message, price_tier, profile_notes, _now()),
    )
    conn.commit()
    conn.close()


# ------------------------------------------------------------ observations

def add_observation(
    product_id,
    retailer_id,
    observed_date,
    move_type,
    move_detail="",
    your_read="",
    source="manual",
    is_reviewed=True,
) -> str:
    if isinstance(observed_date, date):
        observed_date = observed_date.isoformat()
    observation_id = uuid.uuid4().hex[:12]
    conn = get_connection()
    conn.execute(
        """INSERT INTO observations
           (observation_id, product_id, retailer_id, observed_date, move_type, move_detail,
            your_read, source, is_reviewed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            observation_id,
            product_id,
            retailer_id,
            observed_date,
            move_type,
            move_detail,
            your_read,
            source,
            1 if is_reviewed else 0,
            _now(),
        ),
    )
    conn.commit()
    conn.close()
    return observation_id


def update_observation(observation_id: str, **fields) -> None:
    if not fields:
        return
    if "is_reviewed" in fields:
        fields["is_reviewed"] = 1 if fields["is_reviewed"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [observation_id]
    conn = get_connection()
    conn.execute(f"UPDATE observations SET {set_clause} WHERE observation_id = ?", values)
    conn.commit()
    conn.close()


def delete_observation(observation_id: str) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM observations WHERE observation_id = ?", (observation_id,))
    conn.commit()
    conn.close()


def get_observations(product_id=None, only_pending=False) -> pd.DataFrame:
    query = """
        SELECT o.*, p.brand_name, p.category, r.name AS retailer_name
        FROM observations o
        JOIN brands_products p ON p.product_id = o.product_id
        JOIN retailers r ON r.retailer_id = o.retailer_id
        WHERE 1=1
    """
    params = []
    if product_id:
        query += " AND o.product_id = ?"
        params.append(product_id)
    if only_pending:
        query += " AND o.is_reviewed = 0"
    query += " ORDER BY o.observed_date DESC, o.created_at DESC"

    conn = get_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ----------------------------------------------------------- monitored urls

def add_monitored_url(product_id, url, retailer_id=None, needs_js=False,
                       title_selector="", price_selector="", description_selector="") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO monitored_urls
           (product_id, url, retailer_id, needs_js, title_selector, price_selector,
            description_selector, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, url.strip(), retailer_id, 1 if needs_js else 0,
         title_selector, price_selector, description_selector, _now()),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def delete_monitored_url(url_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM monitored_urls WHERE id = ?", (url_id,))
    conn.commit()
    conn.close()


def get_monitored_urls(product_id=None) -> pd.DataFrame:
    query = """
        SELECT m.*, p.brand_name, p.category, r.name AS retailer_name
        FROM monitored_urls m
        JOIN brands_products p ON p.product_id = m.product_id
        LEFT JOIN retailers r ON r.retailer_id = m.retailer_id
        WHERE 1=1
    """
    params = []
    if product_id:
        query += " AND m.product_id = ?"
        params.append(product_id)
    query += " ORDER BY p.brand_name"
    conn = get_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def update_snapshot(url_id: int, title: str, price: str, description: str) -> None:
    conn = get_connection()
    conn.execute(
        """UPDATE monitored_urls
           SET last_title = ?, last_price = ?, last_description = ?, last_checked_at = ?
           WHERE id = ?""",
        (title, price, description, _now(), url_id),
    )
    conn.commit()
    conn.close()
