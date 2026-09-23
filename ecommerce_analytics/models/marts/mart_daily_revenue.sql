{{
  config(
    description="Daily revenue mart. One row per calendar day: the table the "
                "finance dashboard reads."
  )
}}

-- Business rule: revenue counts only 'completed' order lines. Cancelled,
-- refunded, and pending lines are excluded — mixing them in would overstate
-- revenue and no metric should need an asterisk in a board meeting.
select
    order_date as date_day,
    count(distinct order_id) as orders,
    count(*) as order_lines,
    round(sum(line_revenue_usd), 2) as revenue_usd,
    round(
        sum(line_revenue_usd) / nullif(count(distinct order_id), 0), 2
    ) as avg_order_value_usd
from {{ ref('int_order_lines') }}
where status = 'completed'
group by 1
order by 1
