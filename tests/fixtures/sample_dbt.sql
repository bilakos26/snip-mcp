{{ config(materialized='table') }}

WITH source_data AS (
    SELECT *
    FROM {{ ref('raw_orders') }}
    WHERE status != 'cancelled'
),

aggregated AS (
    SELECT
        customer_id,
        COUNT(*) AS order_count,
        SUM(amount) AS total_amount
    FROM source_data
    GROUP BY customer_id
)

SELECT * FROM aggregated
