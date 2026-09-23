#!/usr/bin/env python3
"""
check_pipeline.py — Post-build pipeline health monitor.

Runs AFTER `dbt build` and answers the question every data team dreads:
"the pipeline was green, but is the DATA right?"

Checks:
  1. Freshness   — is the latest revenue date within 2 days of today?
  2. Volume      — is the latest day's order count within 0.5x–2x of the
                   trailing 28-day average? (catches a half-missing extract)
  3. Null rates  — revenue_usd nulls must be 0; customer email null rate
                   must stay under 15%; orphan-order rate under 5%.

Every check is logged to the `pipeline_health` table in the warehouse
(check_name, checked_at, status, metric_value, details) so there is an
audit trail, and the script exits non-zero on any FAIL so CI fails too.

Usage:
    python monitoring/check_pipeline.py [--db path/to/ecommerce.duckdb]

In production this same script would POST failures to Slack/email (see README).
"""

import argparse
import os
import sys
from datetime import date

import duckdb

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(REPO_ROOT, "ecommerce.duckdb")

# dbt-duckdb names a model's custom schema "<database>_<schema>", so the
# `marts` schema from dbt_project.yml becomes `main_marts` in DuckDB.
# (On Snowflake/BigQuery these would just be `marts`, `staging`, etc.)
SCHEMA_RAW = "main_raw"
SCHEMA_STAGING = "main_staging"
SCHEMA_INTERMEDIATE = "main_intermediate"
SCHEMA_MARTS = "main_marts"

CHECKS = []  # (name, sql returning one row: metric_value, detail)


def register(name, sql):
    CHECKS.append((name, sql))


# --- check definitions -------------------------------------------------------
# Each query returns exactly one row: (metric_value DOUBLE, detail VARCHAR).
# The Python wrapper below decides PASS/FAIL from the metric.

register(
    "freshness_days_stale",
    f"""
    select
        date_diff('day', max(date_day), current_date)::double as metric_value,
        'latest revenue date: ' || max(date_day)::varchar as detail
    from {SCHEMA_MARTS}.mart_daily_revenue
    """,
)

register(
    "volume_latest_vs_trailing_avg",
    f"""
    with daily as (
        select order_date, count(*) as n
        from {SCHEMA_INTERMEDIATE}.int_order_lines
        where status = 'completed'
        group by 1
    ),
    latest as (select max(order_date) as d from daily)
    select
        (select n from daily where order_date = (select d from latest))::double
            / nullif((select avg(n) from daily
                      where order_date between (select d from latest) - 28
                                         and (select d from latest) - 1), 0)
            as metric_value,
        'latest day vs trailing 28-day avg order-line count' as detail
    """,
)

register(
    "null_rate_revenue",
    f"""
    select
        avg(case when revenue_usd is null then 1.0 else 0.0 end) as metric_value,
        'share of mart_daily_revenue rows with null revenue' as detail
    from {SCHEMA_MARTS}.mart_daily_revenue
    """,
)

register(
    "null_rate_customer_email",
    f"""
    select
        avg(case when email is null then 1.0 else 0.0 end) as metric_value,
        'share of CLV rows with null email' as detail
    from {SCHEMA_MARTS}.mart_customer_lifetime_value
    """,
)

register(
    "orphan_order_rate",
    f"""
    select
        avg(case when is_orphan_order then 1.0 else 0.0 end) as metric_value,
        'share of order lines with no matching customer' as detail
    from {SCHEMA_INTERMEDIATE}.int_order_lines
    """,
)

# --- pass/fail thresholds ----------------------------------------------------
# (check_name -> (max_ok_value, human-readable rule))
THRESHOLDS = {
    "freshness_days_stale": (2.0, "latest revenue date must be within 2 days of today"),
    "volume_latest_vs_trailing_avg": (None, "latest day must be 0.5x–2x of trailing avg"),
    "null_rate_revenue": (0.0, "revenue must never be null"),
    "null_rate_customer_email": (0.15, "email null rate must stay under 15%"),
    "orphan_order_rate": (0.05, "orphan order rate must stay under 5%"),
}


def evaluate(name, metric):
    """Return (status, reason). None metric = check query found no data -> FAIL."""
    if metric is None:
        return "FAIL", "check returned no data"
    if name == "volume_latest_vs_trailing_avg":
        ok = 0.5 <= metric <= 2.0
        return ("PASS" if ok else "FAIL",
                f"ratio={metric:.2f} (allowed 0.50–2.00)")
    limit, rule = THRESHOLDS[name]
    ok = metric <= limit
    return ("PASS" if ok else "FAIL",
            f"value={metric:.4f} (limit {limit}) — {rule}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("DBT_DUCKDB_PATH", DEFAULT_DB))
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"ERROR: warehouse not found at {args.db} — run `dbt build` first.")
        return 2

    con = duckdb.connect(args.db)
    con.execute(
        """
        create table if not exists main.pipeline_health (
            check_name varchar,
            checked_at timestamp,
            status varchar,
            metric_value double,
            details varchar
        )
        """
    )

    failures = 0
    print(f"Pipeline health check — {date.today().isoformat()} — {args.db}\n")
    for name, sql in CHECKS:
        metric, detail = con.execute(sql).fetchone()
        status, reason = evaluate(name, metric)
        con.execute(
            "insert into main.pipeline_health values (?, now(), ?, ?, ?)",
            [name, status, metric, f"{detail} | {reason}"],
        )
        mark = "PASS" if status == "PASS" else "FAIL"
        print(f"  [{mark}] {name}: {reason}")
        if status == "FAIL":
            failures += 1

    print(f"\n{len(CHECKS) - failures}/{len(CHECKS)} checks passed "
          f"(logged to main.pipeline_health)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
