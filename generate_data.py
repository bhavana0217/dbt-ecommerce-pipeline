#!/usr/bin/env python3
"""
generate_data.py — Seeded generator for the fictional e-commerce company's raw tables.

Scenario: a mid-size online retailer dumps daily extracts from its order system,
CRM, and product catalog. The extracts are messy, exactly like real life.

Writes:
  ecommerce_analytics/seeds/raw_orders.csv
  ecommerce_analytics/seeds/raw_customers.csv
  ecommerce_analytics/seeds/raw_products.csv
  data_manifest.json   (exact counts of every injected data-quality issue,
                        so the README's claims are verifiable, not invented)

The generator is seeded (SEED = 42) and the date window always ends yesterday,
so `dbt build` + the freshness monitor stay green whenever the pipeline is
re-run. Re-running overwrites the CSVs.
"""

import csv
import json
import os
import random
from datetime import date, datetime, timedelta

import numpy as np

SEED = 42
random.seed(SEED)
rng = np.random.default_rng(SEED)

REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
SEEDS_DIR = os.path.join(REPO_ROOT, "ecommerce_analytics", "seeds")
os.makedirs(SEEDS_DIR, exist_ok=True)

# ~20 months of history, ending yesterday (keeps the freshness check honest).
END_DATE = date.today() - timedelta(days=1)
START_DATE = END_DATE - timedelta(days=609)

FIRST_NAMES = ["Ava", "Liam", "Maya", "Noah", "Zoe", "Ethan", "Priya", "Lucas",
               "Sofia", "Mateo", "Amara", "Kai", "Nora", "Omar", "Ivy", "Ravi",
               "Elena", "Dante", "Tara", "Yuki", "Sam", "Nina", "Leo", "Aisha",
               "Marco", "Hana", "Victor", "Lena", "Arjun", "Cleo", "Diego",
               "Mira", "Jonas", "Anya", "Theo", "Rosa", "Kofi", "June", "Ali", "Wren"]
LAST_NAMES = ["Patel", "Garcia", "Kim", "Nguyen", "Smith", "Khan", "Muller",
              "Rossi", "Dubois", "Silva", "Johnson", "Ali", "Chen", "Okafor",
              "Haddad", "Novak", "Tanaka", "Iyer", "Costa", "Weber", "Brown",
              "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson",
              "Thomas", "Jackson", "White", "Harris", "Martin", "Garcia",
              "Martinez", "Robinson", "Clark", "Lewis", "Lee", "Walker", "Hall"]

CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Beauty",
              "Sports", "Books", "Toys", "Grocery"]

COUNTRIES = ["US"] * 70 + ["CA"] * 10 + ["UK"] * 8 + ["AU"] * 5 + ["DE", "IN", "BR"] * 2 + ["JP"]

FX_CURRENCIES = ["USD"] * 85 + ["EUR"] * 10 + ["GBP"] * 5
STATUSES = ["completed"] * 85 + ["cancelled"] * 8 + ["refunded"] * 4 + ["pending"] * 3


def random_case(s: str) -> str:
    """Return a string in random casing, mimicking inconsistent source systems."""
    r = random.random()
    if r < 0.5:
        return s.upper()
    if r < 0.8:
        return s.lower()
    return s.capitalize()


def random_datetime() -> datetime:
    """Uniform random timestamp inside the window."""
    delta_days = rng.integers(0, (END_DATE - START_DATE).days + 1)
    d = START_DATE + timedelta(days=int(delta_days))
    return datetime(d.year, d.month, d.day,
                    int(rng.integers(0, 24)), int(rng.integers(0, 60)),
                    int(rng.integers(0, 60)))


def messy_timestamp(dt: datetime) -> str:
    """Render a timestamp the way three different source systems would."""
    r = random.random()
    if r < 0.70:      # system A: ISO
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    if r < 0.90:      # system B: US format
        return dt.strftime("%m/%d/%Y %H:%M")
    if r < 0.98:      # system C: date only
        return dt.strftime("%Y-%m-%d")
    # broken rows: impossible dates, free text, blanks
    return random.choice(["2025/13/45 25:99:99", "not-a-date", ""])


def write_csv(path, fieldnames, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------- products ---
products = []
for i in range(1, 601):
    price = round(float(rng.uniform(5, 500)), 2)
    # ~15% of prices arrive with currency symbols / thousand separators
    price_raw = f"${price:,.2f}" if random.random() < 0.15 else f"{price:.2f}"
    products.append({
        "product_id": f"P-{i:04d}",
        "sku": f"SKU-{i:05d}",
        "product_name": f"{random.choice(['Pro', 'Ultra', 'Classic', 'Mini', 'Max'])} "
                        f"{random.choice(CATEGORIES).split(' ')[0]}-{i}",
        "category": "" if random.random() < 0.05 else random.choice(CATEGORIES),
        "unit_price_raw": price_raw,
        "_price": price,  # helper, not written
    })

n_dup_products = 0
for _ in range(int(0.03 * len(products))):  # ~3% duplicate SKUs, price drifted
    dup = dict(random.choice(products))
    dup["_price"] = round(dup["_price"] * float(rng.uniform(0.9, 1.1)), 2)
    dup["unit_price_raw"] = f"{dup['_price']:.2f}"
    products.append(dup)
    n_dup_products += 1

product_rows = [{k: v for k, v in p.items() if not k.startswith("_")} for p in products]
write_csv(os.path.join(SEEDS_DIR, "raw_products.csv"),
          ["product_id", "sku", "product_name", "category", "unit_price_raw"],
          product_rows)
n_missing_category = sum(1 for p in product_rows if p["category"] == "")

# --------------------------------------------------------------- customers ---
customers = []
for i in range(1, 5001):
    first, last = random.choice(FIRST_NAMES), random.choice(LAST_NAMES)
    email = "" if random.random() < 0.08 else f"{first.lower()}.{last.lower()}{i}@example.com"
    signup = datetime(2024, 6, 1) + timedelta(days=int(rng.integers(0, 400)))
    if signup.date() > END_DATE:
        signup = datetime.combine(END_DATE, datetime.min.time())
    updated = signup + timedelta(days=int(rng.integers(0, 300)))
    if updated.date() > END_DATE:
        updated = datetime.combine(END_DATE, datetime.min.time())
    customers.append({
        "customer_id": f"C-{i:05d}",
        "first_name": first,
        "last_name": last,
        "email": email,
        "country": random.choice(COUNTRIES),
        "signup_date": signup.strftime("%Y-%m-%d"),
        "updated_at": updated.strftime("%Y-%m-%d %H:%M:%S"),
    })

# ~2% duplicate accounts: same email, new id, later signup (CRM merge never happened)
n_dup_emails = 0
with_email = [c for c in customers if c["email"]]
for _ in range(int(0.02 * len(with_email))):
    src = dict(random.choice(with_email))
    src["customer_id"] = f"C-{5000 + n_dup_emails + 1:05d}"
    later = datetime.strptime(src["signup_date"], "%Y-%m-%d") + timedelta(days=int(rng.integers(30, 300)))
    if later.date() > END_DATE:
        later = datetime.combine(END_DATE, datetime.min.time())
    src["signup_date"] = later.strftime("%Y-%m-%d")
    src["updated_at"] = later.strftime("%Y-%m-%d %H:%M:%S")
    customers.append(src)
    n_dup_emails += 1

write_csv(os.path.join(SEEDS_DIR, "raw_customers.csv"),
          ["customer_id", "first_name", "last_name", "email", "country",
           "signup_date", "updated_at"],
          customers)
n_missing_email = sum(1 for c in customers if c["email"] == "")

# ------------------------------------------------------------------ orders ---
order_lines = []
line_id, order_id = 1, 1
while len(order_lines) < 32000:
    n_lines = 1 if random.random() < 0.70 else (2 if random.random() < 0.85 else 3)
    oid = f"O-{order_id:06d}"
    order_id += 1
    for _ in range(n_lines):
        product = random.choice(products)
        qty = int(rng.choice([1, 2, 3, 4, 5], p=[0.55, 0.25, 0.12, 0.05, 0.03]))
        if random.random() < 0.01:                      # data-entry error
            qty = -qty
        order_lines.append({
            "order_line_id": f"L-{line_id:07d}",
            "order_id": oid,
            "customer_id": "" if random.random() < 0.005 else f"C-{int(rng.integers(1, 5001)):05d}",
            "product_id": product["product_id"],
            "quantity": qty,
            "unit_price": f"{product['_price']:.2f}",
            "currency": random_case(random.choice(FX_CURRENCIES)),
            "status": random_case(random.choice(STATUSES)),
            "created_at": messy_timestamp(random_datetime()),
        })
        line_id += 1

n_negative_qty = sum(1 for o in order_lines if int(o["quantity"]) < 0)
n_bad_ts = sum(1 for o in order_lines if o["created_at"] in ("2025/13/45 25:99:99", "not-a-date", ""))
n_orphans = sum(1 for o in order_lines if o["customer_id"] == "")

# ~1.5% exact-duplicate rows (double-emitted events from the order feed)
n_dup_lines = 0
for _ in range(int(0.015 * len(order_lines))):
    order_lines.append(dict(random.choice(order_lines)))
    n_dup_lines += 1
random.shuffle(order_lines)

write_csv(os.path.join(SEEDS_DIR, "raw_orders.csv"),
          ["order_line_id", "order_id", "customer_id", "product_id", "quantity",
           "unit_price", "currency", "status", "created_at"],
          order_lines)

# ----------------------------------------------------------------- manifest ---
manifest = {
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "seed": SEED,
    "window": {"start": str(START_DATE), "end": str(END_DATE)},
    "raw_products": len(product_rows),
    "duplicate_product_skus": n_dup_products,
    "products_missing_category": n_missing_category,
    "raw_customers": len(customers),
    "customers_missing_email": n_missing_email,
    "duplicate_customer_emails": n_dup_emails,
    "raw_order_lines": len(order_lines),
    "duplicate_order_lines": n_dup_lines,
    "negative_quantities": n_negative_qty,
    "unparseable_timestamps": n_bad_ts,
    "orphan_order_lines_no_customer": n_orphans,
}
with open(os.path.join(REPO_ROOT, "data_manifest.json"), "w") as f:
    json.dump(manifest, f, indent=2)

print(f"Seeds written to {SEEDS_DIR}/")
for k, v in manifest.items():
    if k not in ("generated_at", "seed", "window"):
        print(f"  {k}: {v}")
