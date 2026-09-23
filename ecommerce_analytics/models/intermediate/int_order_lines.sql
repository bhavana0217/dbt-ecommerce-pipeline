{{
  config(
    description="Order lines enriched with customer and product attributes. "
                "One row per order line — the clean grain every mart aggregates from."
  )
}}

-- The join that answers "which customer bought which product, when, for how much".
-- LEFT JOINs are deliberate: an order line that fails to match a customer or
-- product is still real revenue, so it must not vanish. Unmatched rows are
-- flagged (is_orphan_order) and monitored, not silently dropped.
select
    o.order_line_id,
    o.order_id,
    o.created_at::date as order_date,
    o.customer_id,
    o.product_id,
    o.quantity,
    o.unit_price_usd,
    o.currency,
    o.status,
    round(o.quantity * o.unit_price_usd, 2) as line_revenue_usd,
    c.country as customer_country,
    p.category as product_category,
    p.product_name,
    (c.customer_id is null) as is_orphan_order
from {{ ref('stg_orders') }} as o
left join {{ ref('stg_customers') }} as c
    on o.customer_id = c.customer_id
left join {{ ref('stg_products') }} as p
    on o.product_id = p.product_id
