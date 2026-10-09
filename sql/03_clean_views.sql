-- Очищенный слой данных (PostgreSQL).
-- Представления скрывают дефекты выгрузки: дубли, разный регистр статусов,
-- выбросы в количестве. Весь дальнейший анализ опирается только на них.

DROP VIEW IF EXISTS sales             CASCADE;
DROP VIEW IF EXISTS orders_clean      CASCADE;
DROP VIEW IF EXISTS order_items_clean CASCADE;
DROP VIEW IF EXISTS customers_clean   CASCADE;

-- Заказы без дублей и с нормализованным статусом.
CREATE VIEW orders_clean AS
SELECT DISTINCT
       order_id,
       customer_id,
       order_date,
       LOWER(TRIM(status)) AS status,
       payment_method,
       order_number,
       total_amount,
       TO_CHAR(order_date, 'YYYY-MM')          AS order_month,
       DATE_TRUNC('month', order_date)::date   AS order_month_start
FROM orders;

-- Позиции заказов без выбросов по количеству.
CREATE VIEW order_items_clean AS
SELECT order_id,
       product_id,
       quantity,
       unit_price,
       discount,
       ROUND(unit_price * quantity * (1 - discount), 2) AS item_revenue
FROM order_items
WHERE quantity BETWEEN 1 AND 20;

-- Клиенты с заполненными заглушками вместо пропусков.
CREATE VIEW customers_clean AS
SELECT customer_id,
       signup_date,
       TO_CHAR(signup_date, 'YYYY-MM')          AS signup_month,
       DATE_TRUNC('month', signup_date)::date   AS signup_month_start,
       channel,
       COALESCE(NULLIF(TRIM(city), ''), 'не указан')     AS city,
       COALESCE(NULLIF(TRIM(device), ''), 'не указано')  AS device,
       age,
       is_subscribed
FROM customers;

-- Витрина продаж: одна строка на позицию выполненного заказа.
-- Отменённые и возвращённые заказы исключены — они не формируют выручку.
CREATE VIEW sales AS
SELECT o.order_id,
       o.customer_id,
       o.order_date,
       o.order_month,
       o.order_month_start,
       o.order_number,
       o.payment_method,
       c.channel,
       c.city,
       c.signup_month,
       c.is_subscribed,
       p.product_id,
       p.category,
       i.quantity,
       i.discount,
       i.item_revenue,
       ROUND(p.cost_price * i.quantity, 2)                  AS item_cost,
       ROUND(i.item_revenue - p.cost_price * i.quantity, 2) AS item_margin
FROM orders_clean       o
JOIN order_items_clean  i ON i.order_id    = o.order_id
JOIN products           p ON p.product_id  = i.product_id
JOIN customers_clean    c ON c.customer_id = o.customer_id
WHERE o.status = 'delivered';
