-- Когортный анализ удержания (PostgreSQL).
-- Когорта — месяц первой покупки клиента. Период — сколько месяцев прошло
-- с этого момента. Для каждой пары считаем, сколько клиентов когорты
-- сделали покупку, и какую выручку они принесли.

WITH first_purchase AS (
    SELECT customer_id,
           MIN(order_month_start) AS cohort_month_start
    FROM sales
    GROUP BY customer_id
),
cohort_size AS (
    SELECT cohort_month_start,
           COUNT(*) AS cohort_customers
    FROM first_purchase
    GROUP BY cohort_month_start
),
activity AS (
    SELECT f.cohort_month_start,
           -- Разница в месяцах между месяцем заказа и месяцем когорты
           (EXTRACT(YEAR  FROM AGE(s.order_month_start, f.cohort_month_start)) * 12
          + EXTRACT(MONTH FROM AGE(s.order_month_start, f.cohort_month_start)))::int
               AS period_number,
           s.customer_id,
           s.item_revenue
    FROM sales          s
    JOIN first_purchase f ON f.customer_id = s.customer_id
)
SELECT TO_CHAR(a.cohort_month_start, 'YYYY-MM')                              AS cohort_month,
       a.period_number,
       z.cohort_customers,
       COUNT(DISTINCT a.customer_id)                                         AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id) / z.cohort_customers, 1)  AS retention_pct,
       ROUND(SUM(a.item_revenue))                                            AS revenue,
       ROUND(SUM(a.item_revenue) / z.cohort_customers)                       AS revenue_per_customer
FROM activity    a
JOIN cohort_size z ON z.cohort_month_start = a.cohort_month_start
GROUP BY a.cohort_month_start, a.period_number, z.cohort_customers
ORDER BY a.cohort_month_start, a.period_number;
