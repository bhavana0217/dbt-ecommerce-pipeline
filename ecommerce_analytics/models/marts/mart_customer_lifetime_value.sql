{{
  config(
    description="Customer lifetime value mart. One row per customer with at "
                "least one completed order."
  )
}}

-- CLV inputs every retention analysis needs: when they started, when they
-- last bought, how often, and how much. INNER JOIN is deliberate here — a
-- customer with zero completed orders has no lifetime value to report, and
-- orphan lines (no customer) can't be attributed to anyone.
with customer_orders as (
    select
        customer_id,
        min(order_date) as first_order_date,
        max(order_date) as last_order_date,
        count(distinct order_id) as total_orders,
        round(sum(line_revenue_usd), 2) as lifetime_revenue_usd
    from {{ ref('int_order_lines') }}
    where status = 'completed'
      and not is_orphan_order
    group by 1
)

select
    c.customer_id,
    c.email,
    c.country,
    c.signup_date,
    o.first_order_date,
    o.last_order_date,
    o.total_orders,
    o.lifetime_revenue_usd,
    round(o.lifetime_revenue_usd / nullif(o.total_orders, 0), 2) as avg_order_value_usd,
    date_diff('day', o.last_order_date, current_date) as days_since_last_order
from {{ ref('stg_customers') }} as c
inner join customer_orders as o
    on c.customer_id = o.customer_id
