"""Synthetic sales demo database for the SQL Analyst (PRD §5.5, §10; TRD §10).

Creates a separate database (`DEMO_DB_NAME`, default knowflow_demo) with schema `sales` and a
login role that can only SELECT from it:
- customers, products, orders, order_items, payments, seeded deterministically (fixed RNG seed),
  with the edge cases the PRD asks for: refunds, cancelled and pending orders, customers with the
  same name, NULL emails/cities, and dates spread over the 12 months before seeding so
  "last month" questions have data.
- Role `DEMO_DB_READER_USER`: LOGIN, no superuser/createdb/createrole, CONNECT + USAGE + SELECT
  only, `default_transaction_read_only = on`, statement and lock timeouts. All data is synthetic.

Run: ./scripts/dev.ps1 seed-demo   (or: python -m app.modules.sql_assistant.demo)
Re-running drops and recreates the demo schema; it never touches the application database.
"""

import random
import re
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

from app.core.config import Settings, get_settings

SCHEMA = "sales"
SEED = 20261107

DDL = f"""
DROP SCHEMA IF EXISTS {SCHEMA} CASCADE;
CREATE SCHEMA {SCHEMA};
CREATE TABLE {SCHEMA}.customers (
    id integer PRIMARY KEY,
    name text NOT NULL,
    email text,
    city text,
    country text NOT NULL,
    segment text NOT NULL CHECK (segment IN ('consumer', 'small_business', 'enterprise')),
    created_at date NOT NULL
);
CREATE TABLE {SCHEMA}.products (
    id integer PRIMARY KEY,
    name text NOT NULL,
    category text NOT NULL,
    unit_price numeric(10, 2) NOT NULL CHECK (unit_price > 0)
);
CREATE TABLE {SCHEMA}.orders (
    id integer PRIMARY KEY,
    customer_id integer NOT NULL REFERENCES {SCHEMA}.customers (id),
    order_date date NOT NULL,
    status text NOT NULL CHECK (status IN ('paid', 'refunded', 'cancelled', 'pending')),
    total_amount numeric(12, 2) NOT NULL
);
CREATE TABLE {SCHEMA}.order_items (
    id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES {SCHEMA}.orders (id),
    product_id integer NOT NULL REFERENCES {SCHEMA}.products (id),
    quantity integer NOT NULL CHECK (quantity > 0),
    unit_price numeric(10, 2) NOT NULL
);
CREATE TABLE {SCHEMA}.payments (
    id integer PRIMARY KEY,
    order_id integer NOT NULL REFERENCES {SCHEMA}.orders (id),
    paid_at date NOT NULL,
    amount numeric(12, 2) NOT NULL,
    method text NOT NULL CHECK (method IN ('card', 'bank_transfer', 'invoice')),
    kind text NOT NULL CHECK (kind IN ('payment', 'refund'))
);
COMMENT ON TABLE {SCHEMA}.customers IS
    'Synthetic customers. Several share a name; email and city may be NULL.';
COMMENT ON TABLE {SCHEMA}.orders IS
    'One row per order. total_amount is the order value before refunds.';
COMMENT ON COLUMN {SCHEMA}.orders.status IS
    'paid, refunded (fully refunded), cancelled (never paid) or pending (not yet paid).';
COMMENT ON TABLE {SCHEMA}.payments IS
    'Money movements. kind=payment is positive, kind=refund is negative.';
COMMENT ON COLUMN {SCHEMA}.payments.amount IS
    'Positive for payments, negative for refunds (EUR).';
COMMENT ON TABLE {SCHEMA}.order_items IS 'Products on each order with the unit price charged.';
COMMENT ON TABLE {SCHEMA}.products IS 'Synthetic product catalogue (EUR prices).';
"""

FIRST = [
    "Ana",
    "Ben",
    "Chen",
    "Dara",
    "Eli",
    "Femi",
    "Gita",
    "Hugo",
    "Ines",
    "Jon",
    "Kai",
    "Lena",
    "Mo",
    "Nora",
    "Omar",
    "Pia",
    "Quinn",
    "Ravi",
    "Sara",
    "Tom",
]
LAST = [
    "Berg",
    "Costa",
    "Dubois",
    "Eriksen",
    "Fischer",
    "Garcia",
    "Haas",
    "Ito",
    "Jansen",
    "Kowalski",
]
COMPANIES = [
    "Acme Tools",
    "Blue Harbor",
    "Cobalt Labs",
    "Delta Freight",
    "Evergreen Foods",
    "Fjord Studio",
    "Granite Works",
    "Helix Health",
]
CITIES = ["Berlin", "Lisbon", "Paris", "Amsterdam", "Vienna", "Madrid", "Oslo", None]
COUNTRIES = {
    "Berlin": "DE",
    "Lisbon": "PT",
    "Paris": "FR",
    "Amsterdam": "NL",
    "Vienna": "AT",
    "Madrid": "ES",
    "Oslo": "NO",
    None: "DE",
}
PRODUCTS = [
    ("Ergo Chair", "furniture", "289.00"),
    ("Standing Desk", "furniture", "549.00"),
    ("Monitor 27in", "electronics", "319.00"),
    ("Laptop Stand", "accessories", "49.00"),
    ("USB-C Dock", "electronics", "179.00"),
    ("Noise-Cancelling Headset", "electronics", "229.00"),
    ("Webcam HD", "electronics", "89.00"),
    ("Desk Lamp", "accessories", "39.00"),
    ("Cable Kit", "accessories", "19.00"),
    ("Whiteboard", "office", "129.00"),
    ("Notebook Pack", "office", "12.50"),
    ("Coffee Beans 1kg", "pantry", "24.00"),
    ("Keyboard", "electronics", "99.00"),
    ("Mouse", "electronics", "45.00"),
    ("Footrest", "furniture", "59.00"),
    ("Plant Pot", "office", "22.00"),
]


def _identifier(value: str) -> str:
    if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", value):
        raise ValueError(f"Unsafe identifier: {value!r}")
    return value


def _rows(today: date) -> dict[str, list[tuple[object, ...]]]:
    rng = random.Random(SEED)  # noqa: S311  # deterministic synthetic data, not security
    customers: list[tuple[object, ...]] = []
    for i in range(1, 121):
        if i % 6 == 0:
            name, segment = COMPANIES[(i // 6) % len(COMPANIES)], "small_business"
        elif i % 25 == 0:
            name, segment = COMPANIES[(i // 25) % len(COMPANIES)] + " Group", "enterprise"
        else:
            # A small name pool guarantees duplicate customer names (different ids).
            name, segment = f"{FIRST[i % len(FIRST)]} {LAST[(i * 7) % len(LAST)]}", "consumer"
        city = CITIES[i % len(CITIES)]
        email = None if i % 11 == 0 else f"customer{i}@example.test"
        created = today - timedelta(days=rng.randint(60, 900))
        customers.append((i, name, email, city, COUNTRIES[city], segment, created))

    products: list[tuple[int, str, str, Decimal]] = [
        (i, n, c, Decimal(p)) for i, (n, c, p) in enumerate(PRODUCTS, start=1)
    ]
    orders: list[tuple[object, ...]] = []
    items: list[tuple[object, ...]] = []
    payments: list[tuple[object, ...]] = []
    item_id = pay_id = 1
    for oid in range(1, 901):
        cust = rng.choices(range(1, 121), weights=[3 if c % 6 == 0 else 1 for c in range(1, 121)])[
            0
        ]
        odate = today - timedelta(days=rng.randint(1, 365))
        status = rng.choices(["paid", "refunded", "cancelled", "pending"], [80, 7, 8, 5])[0]
        total = Decimal("0")
        for _ in range(rng.randint(1, 4)):
            pid, _n, _c, price = products[rng.randrange(len(products))]
            qty = rng.randint(1, 5)
            items.append((item_id, oid, pid, qty, price))
            item_id += 1
            total += price * qty
        orders.append((oid, cust, odate, status, total))
        if status in ("paid", "refunded"):
            paid = odate + timedelta(days=rng.randint(0, 5))
            method = rng.choice(["card", "bank_transfer", "invoice"])
            payments.append((pay_id, oid, min(paid, today), total, method, "payment"))
            pay_id += 1
            if status == "refunded":
                refund_day = min(paid + timedelta(days=rng.randint(3, 20)), today)
                payments.append((pay_id, oid, refund_day, -total, method, "refund"))
                pay_id += 1
    return {
        "customers": customers,
        "products": list[tuple[object, ...]](products),
        "orders": orders,
        "order_items": items,
        "payments": payments,
    }


def admin_url(settings: Settings, database: str) -> URL:
    return settings.database_url.set(database=database)


def seed(settings: Settings | None = None, *, today: date | None = None) -> dict[str, int]:
    settings = settings or get_settings()
    db = _identifier(settings.demo_db_name)
    reader = _identifier(settings.demo_reader_user)
    password = settings.demo_db_reader_password.get_secret_value()
    if len(password) < 12:
        raise SystemExit("Set DEMO_DB_READER_PASSWORD (12+ characters) in .env first.")
    today = today or datetime.now(UTC).date()

    server = create_engine(admin_url(settings, "postgres"), isolation_level="AUTOCOMMIT")
    with server.connect() as conn:
        if not conn.scalar(text("SELECT 1 FROM pg_database WHERE datname = :d"), {"d": db}):
            conn.execute(text(f'CREATE DATABASE "{db}"'))
        exists = conn.scalar(text("SELECT 1 FROM pg_roles WHERE rolname = :r"), {"r": reader})
        verb = "ALTER" if exists else "CREATE"
        # Password is passed as a bound literal via format(); never interpolated into SQL text.
        stmt = conn.scalar(
            text(
                f"SELECT format('{verb} ROLE %I LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOINHERIT NOREPLICATION PASSWORD %L', CAST(:r AS text), CAST(:p AS text))"
            ),
            {"r": reader, "p": password},
        )
        conn.execute(text(stmt))
        # PostgreSQL grants CONNECT on every database to PUBLIC by default; the reader must not
        # be able to open the application database at all.
        app_db = _identifier(settings.postgres_db)
        conn.execute(text(f'REVOKE CONNECT, TEMPORARY ON DATABASE "{app_db}" FROM PUBLIC'))
    server.dispose()

    engine = create_engine(admin_url(settings, db))
    counts: dict[str, int] = {}
    with engine.begin() as conn:
        for statement in DDL.split(";\n"):
            if statement.strip():
                conn.execute(text(statement))
        rows = _rows(today)
        cols = {
            "customers": "id, name, email, city, country, segment, created_at",
            "products": "id, name, category, unit_price",
            "orders": "id, customer_id, order_date, status, total_amount",
            "order_items": "id, order_id, product_id, quantity, unit_price",
            "payments": "id, order_id, paid_at, amount, method, kind",
        }
        for table, data in rows.items():
            names = [c.strip() for c in cols[table].split(",")]
            placeholders = ", ".join(f":{n}" for n in names)
            conn.execute(
                # Table and column names come from the constants above; values are bound.
                text(f"INSERT INTO {SCHEMA}.{table} ({cols[table]}) VALUES ({placeholders})"),  # noqa: S608
                [dict(zip(names, r, strict=True)) for r in data],
            )
            counts[table] = len(data)
        conn.execute(text(f'REVOKE ALL ON DATABASE "{db}" FROM PUBLIC'))
        conn.execute(text("REVOKE CREATE ON SCHEMA public FROM PUBLIC"))
        conn.execute(text(f'GRANT CONNECT ON DATABASE "{db}" TO "{reader}"'))
        conn.execute(text(f'GRANT USAGE ON SCHEMA {SCHEMA} TO "{reader}"'))
        conn.execute(text(f'GRANT SELECT ON ALL TABLES IN SCHEMA {SCHEMA} TO "{reader}"'))
        conn.execute(
            text(f'ALTER ROLE "{reader}" IN DATABASE "{db}" SET default_transaction_read_only = on')
        )
        conn.execute(
            text(
                f'ALTER ROLE "{reader}" IN DATABASE "{db}" SET statement_timeout = '
                f"'{int(settings.sql_statement_timeout_ms)}ms'"
            )
        )
        conn.execute(text("ANALYZE"))
    engine.dispose()
    return counts


def main() -> None:
    counts = seed()
    settings = get_settings()
    print(
        f"Seeded {settings.demo_db_name}.{SCHEMA}: "
        + ", ".join(f"{k}={v}" for k, v in counts.items())
    )
    print(f"Read-only role: {settings.demo_reader_user}")


if __name__ == "__main__":
    main()
