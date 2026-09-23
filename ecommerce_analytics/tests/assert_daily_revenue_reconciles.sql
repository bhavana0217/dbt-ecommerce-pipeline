/*
Reconciliation: the daily revenue mart must tie out to the underlying order
lines. If aggregation logic ever drifts (a filter changes, a join fans out),
this test catches it before finance does. Tolerance of one cent absorbs
floating-point rounding only.
*/
with mart_total as (
    select round(sum(revenue_usd), 2) as total
    from {{ ref('mart_daily_revenue') }}
),
lines_total as (
    select round(sum(line_revenue_usd), 2) as total
    from {{ ref('int_order_lines') }}
    where status = 'completed'
)

select
    (select total from mart_total) as mart_revenue,
    (select total from lines_total) as lines_revenue
where abs(
    (select total from mart_total) - (select total from lines_total)
) >= 0.01
