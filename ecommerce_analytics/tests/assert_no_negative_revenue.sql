/*
Business rule: revenue in the marts must never be negative.
A negative revenue row means a cleaning bug (e.g. a sign error in FX
conversion) — it is always a pipeline defect, never a real business event,
because returns are modeled as separate refund rows.
*/
select date_day, revenue_usd
from {{ ref('mart_daily_revenue') }}
where revenue_usd < 0

union all

select null as date_day, lifetime_revenue_usd as revenue_usd
from {{ ref('mart_customer_lifetime_value') }}
where lifetime_revenue_usd < 0
