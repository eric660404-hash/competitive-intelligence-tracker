"""SQLite persistence layer for the Competitive Intelligence Tracker."""

import sqlite3
from datetime import datetime, date
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "tracker.db"

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
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            brand TEXT NOT NULL,
            product_name TEXT NOT NULL,
            target_segment TEXT DEFAULT '',
            key_message TEXT DEFAULT '',
            price_tier TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            retailer TEXT NOT NULL,
            date_observed TEXT NOT NULL,
            move_type TEXT NOT NULL,
            move_detail TEXT DEFAULT '',
            insight_read TEXT DEFAULT '',
            source TEXT DEFAULT 'manual',
            is_reviewed INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS monitored_urls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            url TEXT NOT NULL,
            retailer TEXT DEFAULT '',
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


# ---------------------------------------------------------------- products

def add_product(brand, product_name, target_segment="", key_message="", price_tier="", notes="") -> int:
    conn = get_connection()
    now = _now()
    cur = conn.execute(
        """INSERT INTO products
           (brand, product_name, target_segment, key_message, price_tier, notes, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (brand.strip(), product_name.strip(), target_segment, key_message, price_tier, notes, now, now),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_product(product_id: int, **fields) -> None:
    if not fields:
        return
    fields["updated_at"] = _now()
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [product_id]
    conn = get_connection()
    conn.execute(f"UPDATE products SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_product(product_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()


def get_products() -> pd.DataFrame:
    conn = get_connection()
    df = pd.read_sql_query("SELECT * FROM products ORDER BY brand, product_name", conn)
    conn.close()
    return df


def get_product(product_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_product_labels() -> dict:
    """Return {product_id: 'Brand - Product name'} for select boxes."""
    df = get_products()
    return {int(r.id): f"{r.brand} - {r.product_name}" for r in df.itertuples()}


# ------------------------------------------------------------ observations

def add_observation(
    product_id,
    retailer,
    date_observed,
    move_type,
    move_detail="",
    insight_read="",
    source="manual",
    is_reviewed=True,
) -> int:
    if isinstance(date_observed, date):
        date_observed = date_observed.isoformat()
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO observations
           (product_id, retailer, date_observed, move_type, move_detail, insight_read,
            source, is_reviewed, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            product_id,
            retailer.strip(),
            date_observed,
            move_type,
            move_detail,
            insight_read,
            source,
            1 if is_reviewed else 0,
            _now(),
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    conn.close()
    return new_id


def update_observation(observation_id: int, **fields) -> None:
    if not fields:
        return
    if "is_reviewed" in fields:
        fields["is_reviewed"] = 1 if fields["is_reviewed"] else 0
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    values = list(fields.values()) + [observation_id]
    conn = get_connection()
    conn.execute(f"UPDATE observations SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_observation(observation_id: int) -> None:
    conn = get_connection()
    conn.execute("DELETE FROM observations WHERE id = ?", (observation_id,))
    conn.commit()
    conn.close()


def get_observations(product_id=None, retailer=None, brand=None, date_from=None, date_to=None,
                      only_pending=False) -> pd.DataFrame:
    query = """
        SELECT o.*, p.brand, p.product_name
        FROM observations o
        JOIN products p ON p.id = o.product_id
        WHERE 1=1
    """
    params = []
    if product_id:
        query += " AND o.product_id = ?"
        params.append(product_id)
    if retailer:
        query += " AND o.retailer = ?"
        params.append(retailer)
    if brand:
        query += " AND p.brand = ?"
        params.append(brand)
    if date_from:
        query += " AND o.date_observed >= ?"
        params.append(str(date_from))
    if date_to:
        query += " AND o.date_observed <= ?"
        params.append(str(date_to))
    if only_pending:
        query += " AND o.is_reviewed = 0"
    query += " ORDER BY o.date_observed DESC, o.id DESC"

    conn = get_connection()
    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


def get_distinct_retailers() -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT retailer FROM observations WHERE retailer != '' "
        "UNION SELECT DISTINCT retailer FROM monitored_urls WHERE retailer != '' ORDER BY 1"
    ).fetchall()
    conn.close()
    return [r[0] for r in rows]


# ----------------------------------------------------------- monitored urls

def add_monitored_url(product_id, url, retailer="", needs_js=False,
                       title_selector="", price_selector="", description_selector="") -> int:
    conn = get_connection()
    cur = conn.execute(
        """INSERT INTO monitored_urls
           (product_id, url, retailer, needs_js, title_selector, price_selector,
            description_selector, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (product_id, url.strip(), retailer.strip(), 1 if needs_js else 0,
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
        SELECT m.*, p.brand, p.product_name
        FROM monitored_urls m
        JOIN products p ON p.id = m.product_id
        WHERE 1=1
    """
    params = []
    if product_id:
        query += " AND m.product_id = ?"
        params.append(product_id)
    query += " ORDER BY p.brand, p.product_name"
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
