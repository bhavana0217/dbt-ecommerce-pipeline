{{
  config(
    description="Cleaned product catalog. Duplicate SKUs resolved, price strings "
                "normalized to numeric USD."
  )
}}

-- Cleaning decisions:
--  1. Duplicate product_ids arrive with slightly drifted prices (catalog sync
--     lag). Keep the row with the highest price — the most recent sync wins.
--     (Documented assumption; a real catalog would carry a version timestamp.)
--  2. Prices sometimes arrive as "$1,299.99". Strip symbols/separators, cast.
--  3. Missing category -> 'Uncategorized', same reasoning as country in
--     stg_customers: honest and BI-friendly.
with source as (
    select * from {{ ref('raw_products') }}
),

deduped as (
    select
        *,
        row_number() over (
            partition by product_id
            order by unit_price_raw desc
        ) as _rn
    from source
)

select
    product_id,
    nullif(trim(sku), '') as sku,
    trim(product_name) as product_name,
    coalesce(nullif(trim(category), ''), 'Uncategorized') as category,
    regexp_replace(unit_price_raw, '[$,]', '')::double as unit_price_usd
from deduped
where _rn = 1
  and product_id is not null
