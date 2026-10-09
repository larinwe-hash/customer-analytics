-- RFM-сегментация клиентов (PostgreSQL).
-- Recency  — сколько дней прошло с последней покупки,
-- Frequency — сколько заказов сделал клиент,
-- Monetary  — сколько денег принёс.
-- Каждый показатель разбивается на 4 группы через NTILE, затем клиент
-- относится к одному из бизнес-сегментов.

WITH report_date AS (
    SELECT MAX(order_date) AS max_date FROM sales
),
customer_stats AS (
    SELECT s.customer_id,
           s.channel,
           ((SELECT max_date FROM report_date) - MAX(s.order_date))::int AS recency_days,
           COUNT(DISTINCT s.order_id)                       AS frequency,
           ROUND(SUM(s.item_revenue))                       AS monetary
    FROM sales s
    GROUP BY s.customer_id, s.channel
),
scored AS (
    SELECT *,
           -- recency: чем меньше дней, тем выше балл
           NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
           NTILE(4) OVER (ORDER BY frequency ASC, monetary ASC) AS f_score,
           NTILE(4) OVER (ORDER BY monetary ASC)      AS m_score
    FROM customer_stats
)
SELECT customer_id,
       channel,
       recency_days,
       frequency,
       monetary,
       r_score,
       f_score,
       m_score,
       CASE
           WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN 'Лояльные'
           WHEN r_score >= 3 AND f_score <= 2                  THEN 'Новички'
           WHEN r_score <= 2 AND f_score >= 3 AND m_score >= 3  THEN 'В зоне риска'
           WHEN r_score <= 2 AND f_score <= 2                   THEN 'Потерянные'
           ELSE 'Стабильные'
       END AS segment
FROM scored
ORDER BY monetary DESC;
