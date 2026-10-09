-- Проверка качества выгрузки (PostgreSQL).
-- Один запрос возвращает список проверок: что проверяли, сколько нашли
-- и насколько это критично. Результат читается как чек-лист перед анализом.

WITH duplicate_orders AS (
    SELECT order_id
    FROM orders
    GROUP BY order_id
    HAVING COUNT(*) > 1
),
status_values AS (
    SELECT DISTINCT status
    FROM orders
    WHERE status <> LOWER(TRIM(status))
),
orphan_items AS (
    SELECT i.order_id
    FROM order_items i
    LEFT JOIN orders o ON o.order_id = i.order_id
    WHERE o.order_id IS NULL
),
quantity_outliers AS (
    SELECT order_id, product_id, quantity
    FROM order_items
    WHERE quantity > 20
),
orders_before_signup AS (
    SELECT o.order_id
    FROM orders o
    JOIN customers c ON c.customer_id = o.customer_id
    WHERE o.order_date < c.signup_date
)
SELECT 'Дубли строк в orders'            AS check_name,
       (SELECT COUNT(*) FROM duplicate_orders)    AS issues,
       'критично: завышает число заказов'          AS comment
UNION ALL
SELECT 'Статусы в разном регистре',
       (SELECT COUNT(*) FROM status_values),
       'критично: ломает фильтрацию по статусу'
UNION ALL
SELECT 'Позиции без заказа',
       (SELECT COUNT(*) FROM orphan_items),
       'критично: нарушает связь таблиц'
UNION ALL
SELECT 'Выбросы в quantity (> 20 шт.)',
       (SELECT COUNT(*) FROM quantity_outliers),
       'критично: искажает выручку'
UNION ALL
SELECT 'Заказы раньше даты регистрации',
       (SELECT COUNT(*) FROM orders_before_signup),
       'критично: ломает когортный анализ'
UNION ALL
SELECT 'Пропуски в customers.city',
       (SELECT COUNT(*) FROM customers WHERE city IS NULL OR TRIM(city) = ''),
       'некритично: поле не используется в метриках'
UNION ALL
SELECT 'Пропуски в customers.device',
       (SELECT COUNT(*) FROM customers WHERE device IS NULL OR TRIM(device) = ''),
       'некритично: поле не используется в метриках';
