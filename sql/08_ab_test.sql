-- Выгрузка результатов A/B-теста реактивации спящих клиентов (PostgreSQL).
--
-- Окно эксперимента: 2025-10-01 — 2025-11-15.
-- Заказы участников не помечены в базе, поэтому к тесту их привязывает
-- только принадлежность участника к группе и попадание заказа в окно.
--
-- Запрос возвращает одну строку на участника, включая тех, кто ничего
-- не купил: без них конверсия и выручка на пользователя будут завышены.

WITH window_bounds AS (
    SELECT DATE '2025-10-01' AS date_from,
           DATE '2025-11-15' AS date_to
),
-- Витрина sales уже содержит только выполненные заказы с выручкой и маржой
experiment_orders AS (
    SELECT e.customer_id,
           s.order_id,
           SUM(s.item_revenue) AS order_revenue,
           SUM(s.item_margin)  AS order_margin,
           MAX(s.discount)     AS discount
    FROM ab_experiment e
    JOIN sales         s ON s.customer_id = e.customer_id
    CROSS JOIN window_bounds w
    WHERE s.order_date BETWEEN w.date_from AND w.date_to
    GROUP BY e.customer_id, s.order_id
),
per_customer AS (
    SELECT customer_id,
           COUNT(DISTINCT order_id) AS orders,
           SUM(order_revenue)       AS revenue,
           SUM(order_margin)        AS margin,
           MAX(discount)            AS discount
    FROM experiment_orders
    GROUP BY customer_id
)
SELECT e.customer_id,
       e.group_name,
       c.channel,
       c.is_subscribed,
       COALESCE(pc.orders, 0)                                  AS orders,
       CASE WHEN pc.orders > 0 THEN 1 ELSE 0 END               AS converted,
       ROUND(COALESCE(pc.revenue, 0), 2)                       AS revenue,
       ROUND(COALESCE(pc.margin, 0), 2)                        AS margin,
       COALESCE(pc.discount, 0)                                AS discount
FROM ab_experiment   e
JOIN customers_clean c  ON c.customer_id = e.customer_id
LEFT JOIN per_customer pc ON pc.customer_id = e.customer_id
ORDER BY e.group_name, e.customer_id;
