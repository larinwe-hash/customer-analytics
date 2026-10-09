-- Экономика каналов привлечения (PostgreSQL).
-- Для каждого канала: сколько клиентов привлекли, сколько на это потратили,
-- какую выручку и маржу они принесли, доля вернувшихся, LTV и окупаемость.
-- Маржа считается по себестоимости товаров, CAC — по расходам на канал.

WITH acquisition AS (
    SELECT channel,
           COUNT(*) AS new_customers
    FROM customers_clean
    GROUP BY channel
),
spend AS (
    SELECT channel,
           SUM(spend) AS total_spend
    FROM marketing_spend
    GROUP BY channel
),
customer_value AS (
    SELECT customer_id,
           channel,
           COUNT(DISTINCT order_id) AS orders,
           SUM(item_revenue)        AS revenue,
           SUM(item_margin)         AS margin
    FROM sales
    GROUP BY customer_id, channel
),
channel_value AS (
    SELECT channel,
           COUNT(*)                                            AS buyers,
           SUM(orders)                                         AS orders,
           SUM(revenue)                                        AS revenue,
           SUM(margin)                                         AS margin,
           SUM(CASE WHEN orders > 1 THEN 1 ELSE 0 END)         AS repeat_buyers
    FROM customer_value
    GROUP BY channel
)
-- Важно: CAC считается на привлечённого (зарегистрированного) клиента,
-- поэтому и маржа для сравнения берётся в расчёте на привлечённого, а не
-- на покупателя — иначе канал с низкой конверсией выглядел бы лучше, чем есть.
SELECT a.channel,
       a.new_customers,
       v.buyers,
       ROUND(100.0 * v.buyers / a.new_customers, 1)        AS conversion_pct,
       ROUND(100.0 * v.repeat_buyers / v.buyers, 1)        AS repeat_pct,
       ROUND(s.total_spend)                                AS spend,
       ROUND(s.total_spend / a.new_customers)              AS cac,
       ROUND(v.revenue)                                    AS revenue,
       ROUND(v.margin)                                     AS gross_profit,
       ROUND(v.revenue / v.buyers)                         AS ltv_revenue_per_buyer,
       ROUND(v.margin  / a.new_customers)                  AS margin_per_acquired,
       ROUND((v.margin / a.new_customers)
             / (s.total_spend / a.new_customers), 2)       AS ltv_cac_ratio,
       ROUND(v.margin - s.total_spend)                     AS net_profit
FROM acquisition   a
JOIN spend         s ON s.channel = a.channel
JOIN channel_value v ON v.channel = a.channel
ORDER BY ltv_cac_ratio DESC;
