{% snapshot customers_snapshot %}

{{
    config(
        target_schema='snapshots',
        unique_key='customer_id',
        strategy='timestamp',
        updated_at='updated_at',
    )
}}

/*
Type-2 slowly changing dimension for customer attributes.

Why it exists: customers change countries and emails. If the CLV mart always
reads the *current* country, last year's "UK revenue" silently becomes this
year's "US revenue" every time someone moves. The snapshot keeps every
historical version with dbt_valid_from / dbt_valid_to, so any analysis can
ask "what did we know on date X?" — the foundation of correct point-in-time
reporting.
*/
select * from {{ ref('stg_customers') }}

{% endsnapshot %}
