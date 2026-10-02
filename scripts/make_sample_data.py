"""Generate the sample data used by the example pipelines in config/examples.

Run from the repository root:

    uv run python scripts/make_sample_data.py

The data is random but seeded, so every run produces the same values.
"""

from __future__ import annotations

import json
import random
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yaml

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "sample"
REGIONS = ["North", "South", "East", "West"]
FIRST_NAMES = ["Ada", "Grace", "Alan", "Edsger", "Barbara", "Donald", "Frances"]
LAST_NAMES = ["Lovelace", "Hopper", "Turing", "Dijkstra", "Liskov", "Knuth", "Allen"]


def main() -> None:
    rng = random.Random(42)
    OUTPUT.mkdir(parents=True, exist_ok=True)

    customers = make_customers(rng)
    products = make_products()
    orders = make_orders(rng, customers, products)

    write_employees()
    customers.to_csv(OUTPUT / "customers.csv", index=False, lineterminator="\n")
    orders.to_parquet(OUTPUT / "orders.parquet", index=False)
    write_products(products)
    write_events(rng, customers, products)
    write_clicks(rng, customers)
    write_regional_sales(rng)
    write_warehouse(customers, products, orders)

    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file():
            print(f"wrote {path.relative_to(OUTPUT.parents[1])}")


def make_customers(rng: random.Random) -> pd.DataFrame:
    rows = []

    for customer_id in range(1, 13):
        signup = date(2025, 1, 1) + timedelta(days=rng.randrange(365))
        rows.append(
            {
                "customer_id": customer_id,
                "name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
                "region": REGIONS[customer_id % len(REGIONS)],
                "segment": rng.choice(["Retail", "Business"]),
                "signup_date": signup.isoformat(),
            }
        )
    return pd.DataFrame(rows)


def make_products() -> list[dict[str, object]]:
    catalogue = [
        ("Desk lamp", "Lighting", 24.99, "black", 1.2),
        ("Floor lamp", "Lighting", 79.0, "white", 4.5),
        ("Office chair", "Furniture", 149.0, "grey", 12.0),
        ("Standing desk", "Furniture", 399.0, "oak", 28.0),
        ("Monitor arm", "Accessories", 59.5, "black", 2.1),
        ("Cable tray", "Accessories", 14.0, "white", 0.6),
        ("Bookshelf", "Furniture", 119.0, "walnut", 18.5),
        ("Notebook set", "Stationery", 9.99, "blue", 0.4),
    ]
    return [
        {
            "product_id": product_id,
            "name": name,
            "category": category,
            "price": price,
            "attributes": {"colour": colour, "weight_kg": weight},
            "tags": [category.lower(), colour],
        }
        for product_id, (name, category, price, colour, weight) in enumerate(
            catalogue, start=1
        )
    ]


def make_orders(
    rng: random.Random,
    customers: pd.DataFrame,
    products: list[dict[str, object]],
) -> pd.DataFrame:
    rows = []

    for order_id in range(1001, 1061):
        product = rng.choice(products)
        rows.append(
            {
                "order_id": order_id,
                "customer_id": int(rng.choice(customers["customer_id"].tolist())),
                "product_id": product["product_id"],
                "quantity": rng.randint(1, 5),
                "unit_price": product["price"],
                "order_date": (
                    date(2026, 9, 1) + timedelta(days=rng.randrange(30))
                ).isoformat(),
                "status": rng.choices(
                    ["shipped", "pending", "cancelled"], weights=[7, 2, 1]
                )[0],
            }
        )
    return pd.DataFrame(rows)


def write_employees() -> None:
    # The original test.csv, kept for the basic example.
    pd.DataFrame(
        {
            "id": [1, 2, 3, 4, 5],
            "name": ["Ada", "Grace", "Linus", "Margaret", "Alan"],
            "department": [
                "Engineering",
                "Engineering",
                "Operations",
                "Research",
                "Research",
            ],
            "salary": pd.array([120000, 115000, None, 130000, 98000], dtype="Int64"),
        }
    ).to_csv(OUTPUT / "employees.csv", index=False, lineterminator="\n")


def write_products(products: list[dict[str, object]]) -> None:
    text = yaml.safe_dump(products, sort_keys=False, allow_unicode=True)
    (OUTPUT / "products.yaml").write_text(text, encoding="utf-8", newline="\n")


def write_events(
    rng: random.Random,
    customers: pd.DataFrame,
    products: list[dict[str, object]],
) -> None:
    folder = OUTPUT / "events"
    folder.mkdir(exist_ok=True)
    event_id = 1

    for day in (1, 2, 3):
        start = datetime(2026, 10, day, 8, 0)
        events = []

        for _ in range(8):
            customer = customers.sample(1, random_state=rng.randrange(10_000)).iloc[0]
            events.append(
                {
                    "event_id": event_id,
                    "type": rng.choices(["view", "click", "purchase"], [5, 3, 2])[0],
                    "timestamp": (
                        start + timedelta(minutes=rng.randrange(600))
                    ).isoformat(),
                    "user": {
                        "id": f"u{customer['customer_id']}",
                        "region": customer["region"],
                    },
                    "properties": {
                        "product_id": rng.choice(products)["product_id"],
                        "duration_ms": rng.randrange(200, 5000),
                    },
                }
            )
            event_id += 1

        batch = {
            "batch_id": f"web-2026-10-{day:02d}",
            "source": {"system": "web", "version": "2.1"},
            "events": events,
        }
        (folder / f"2026-10-{day:02d}.json").write_text(
            json.dumps(batch, indent=2) + "\n", encoding="utf-8", newline="\n"
        )


def write_clicks(rng: random.Random, customers: pd.DataFrame) -> None:
    pages = ["/", "/lighting", "/furniture", "/cart", "/checkout"]
    lines = []

    for click_id in range(1, 21):
        customer_id = int(rng.choice(customers["customer_id"].tolist()))
        lines.append(
            json.dumps(
                {
                    "click_id": click_id,
                    "user_id": f"u{customer_id}",
                    "page": rng.choice(pages),
                    "timestamp": (
                        datetime(2026, 10, 2, 9, 0)
                        + timedelta(seconds=rng.randrange(36_000))
                    ).isoformat(),
                }
            )
        )

    (OUTPUT / "clicks.jsonl").write_text(
        "\n".join(lines) + "\n", encoding="utf-8", newline="\n"
    )


def write_regional_sales(rng: random.Random) -> None:
    months = [f"2026-{month:02d}" for month in range(1, 7)]

    with pd.ExcelWriter(OUTPUT / "regional_sales.xlsx", engine="openpyxl") as writer:
        for region in REGIONS:
            pd.DataFrame(
                {
                    "month": months,
                    "revenue": [rng.randrange(8_000, 20_000) for _ in months],
                    "units": [rng.randrange(80, 250) for _ in months],
                }
            ).to_excel(writer, sheet_name=region, index=False)

        pd.DataFrame(
            {"region": REGIONS, "revenue_target": [80_000, 75_000, 90_000, 70_000]}
        ).to_excel(writer, sheet_name="Targets", index=False)


def write_warehouse(
    customers: pd.DataFrame,
    products: list[dict[str, object]],
    orders: pd.DataFrame,
) -> None:
    path = OUTPUT / "warehouse.db"
    path.unlink(missing_ok=True)

    flat_products = pd.json_normalize(products).drop(columns=["tags"])
    flat_products.columns = [str(column).replace(".", "_") for column in flat_products]

    with sqlite3.connect(path) as connection:
        customers.to_sql("customers", connection, index=False)
        flat_products.to_sql("products", connection, index=False)
        orders.to_sql("orders", connection, index=False)
    connection.close()


if __name__ == "__main__":
    main()
