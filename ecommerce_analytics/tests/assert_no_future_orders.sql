/*
Sanity rule: no order may be dated in the future. A future-dated order means
either a source-system clock bug or a timezone parsing error — both would
corrupt the freshness monitor and any "latest day" reporting.
*/
select order_line_id, order_date
from {{ ref('int_order_lines') }}
where order_date > current_date
