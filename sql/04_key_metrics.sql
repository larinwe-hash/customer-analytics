-- Ключевые метрики по месяцам (PostgreSQL): выручка, заказы, покупатели, средний чек,
-- доля выручки от новых и вернувшихся клиентов.
-- Новым считается клиент в месяце своей первой покупки.

WITH order_totals AS (
    SELECT order_id,
           customer_id,
           order_month,
           order_number,
           SUM(item_revenue) AS order_revenue,
           SUM(item_margin)  AS order_margin
    FROM sales
    GROUP BY order_id, customer_id, order_month, order_number
),
first_order AS (
    SELECT customer_id,
           MIN(order_month) AS first_month
    FROM order_totals
    GROUP BY customer_id
)
SELECT t.order_month                                              AS month,
       COUNT(*)                                                   AS orders,
       COUNT(DISTINCT t.customer_id)                              AS customers,
       ROUND(SUM(t.order_revenue))                                AS revenue,
       ROUND(SUM(t.order_margin))                                 AS gross_profit,
       ROUND(SUM(t.order_revenue) / COUNT(*))                     AS avg_check,
       ROUND(1.0 * COUNT(*) / COUNT(DISTINCT t.customer_id), 2)   AS orders_per_customer,
       ROUND(100.0 * SUM(CASE WHEN t.order_month = f.first_month
                              THEN t.order_revenue ELSE 0 END)
             / SUM(t.order_revenue), 1)                           AS new_revenue_share
FROM order_totals t
JOIN first_order  f ON f.customer_id = t.customer_id
GROUP BY t.order_month
ORDER BY t.order_month;
