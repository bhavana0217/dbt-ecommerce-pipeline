{{
  config(
    description="Cleaned customers. Duplicate accounts merged on email, "
                "keeping the earliest signup as the surviving record."
  )
}}

-- Cleaning decisions:
--  1. The CRM never merged accounts, so the same email appears under multiple
--     customer_ids. Dedupe on lower(trim(email)), keep the earliest signup_date:
--     the first time we saw the customer is the most defensible "truth".
--     Rows with no email can't be matched, so they are kept as-is (null email
--     rate is monitored downstream).
--  2. Missing country -> 'Unknown' rather than NULL: BI tools group NULLs
--     awkwardly, and "Unknown" is honest about what we know.
with source as (
    select * from {{ ref('raw_customers') }}
),

cleaned as (
    select
        *,
        nullif(lower(trim(email)), '') as email_clean
    from source
),

deduped as (
    select
        *,
        row_number() over (
            partition by email_clean
            order by signup_date asc
        ) as _rn
    from cleaned
)

select
    customer_id,
    trim(first_name) as first_name,
    trim(last_name) as last_name,
    email_clean as email,
    coalesce(nullif(trim(country), ''), 'Unknown') as country,
    signup_date::date as signup_date,
    updated_at::timestamp as updated_at  -- drives the type-2 snapshot
from deduped
where _rn = 1 or email_clean is null
