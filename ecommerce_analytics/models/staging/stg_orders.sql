{{
  config(
    description="Cleaned order lines. One row per order line; duplicates removed, "
                "timestamps parsed, currencies normalized to USD."
  )
}}

-- Cleaning decisions (each one is documented because "trust me" is not a data strategy):
--  1. Dedupe on order_line_id: the order feed occasionally emits the same event
--     twice. Keep the latest copy; an exact duplicate can never be "new information".
--  2. Parse created_at: three source systems write three timestamp formats
--     (ISO, US, date-only). Rows that match none are dropped — a revenue mart
--     must never silently misplace revenue in time.
--  3. Negative quantities are data-entry errors (returns are recorded as separate
--     refund rows with a status, not as negative lines). Dropped.
--  4. Currency is upper-cased and converted to USD with static illustrative rates.
--     In production this would join a daily FX rates table instead.
with source as (
    select * from {{ ref('raw_orders') }}
),

parsed as (
    select
        order_line_id,
        nullif(trim(order_id), '') as order_id,
        nullif(trim(customer_id), '') as customer_id,
        nullif(trim(product_id), '') as product_id,
        quantity::integer as quantity,
        unit_price::double as unit_price,
        upper(trim(currency)) as currency,
        lower(trim(status)) as status,
        -- try each known source-system format; unparseable -> NULL -> filtered below
        coalesce(
            try_strptime(created_at, '%Y-%m-%d %H:%M:%S'),
            try_strptime(created_at, '%m/%d/%Y %H:%M'),
            try_strptime(created_at, '%Y-%m-%d')
        ) as created_at
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by order_line_id
            order by created_at desc nulls last
        ) as _rn
    from parsed
)

select
    order_line_id,
    order_id,
    customer_id,
    product_id,
    quantity,
    unit_price,
    -- static illustrative FX rates; see model description
    unit_price * case currency
        when 'USD' then 1.0
        when 'EUR' then 1.08
        when 'GBP' then 1.27
    end as unit_price_usd,
    currency,
    status,
    created_at
from deduped
where _rn = 1
  and order_id is not null
  and created_at is not null
  and quantity > 0
  and unit_price >= 0
