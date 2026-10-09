-- Схема аналитической витрины (PostgreSQL).
-- Таблицы повторяют структуру выгрузки из бэкенда магазина: данные загружаются
-- "как есть", со всеми дефектами. Очистка выполняется на уровне представлений
-- в 03_clean_views.sql.

DROP VIEW IF EXISTS sales             CASCADE;
DROP VIEW IF EXISTS orders_clean      CASCADE;
DROP VIEW IF EXISTS order_items_clean CASCADE;
DROP VIEW IF EXISTS customers_clean   CASCADE;

DROP TABLE IF EXISTS customers       CASCADE;
DROP TABLE IF EXISTS products        CASCADE;
DROP TABLE IF EXISTS orders          CASCADE;
DROP TABLE IF EXISTS order_items     CASCADE;
DROP TABLE IF EXISTS marketing_spend CASCADE;
DROP TABLE IF EXISTS ab_experiment   CASCADE;

CREATE TABLE customers (
    customer_id   INTEGER     PRIMARY KEY,
    signup_date   DATE        NOT NULL,   -- дата регистрации
    channel       TEXT        NOT NULL,   -- канал привлечения
    city          TEXT,                   -- город (есть пропуски)
    device        TEXT,                   -- устройство регистрации (есть пропуски)
    age           SMALLINT,
    is_subscribed SMALLINT    NOT NULL    -- подписка на рассылку, 0/1
);

CREATE TABLE products (
    product_id   INTEGER       PRIMARY KEY,
    product_name TEXT          NOT NULL,
    category     TEXT          NOT NULL,
    price        NUMERIC(12,2) NOT NULL,  -- цена в каталоге, руб.
    cost_price   NUMERIC(12,2) NOT NULL   -- себестоимость, руб.
);

-- Внимание: в выгрузке есть дубли строк, поэтому первичный ключ не задаётся
-- и внешние ключи на orders повесить нельзя — это часть исходной задачи.
CREATE TABLE orders (
    order_id       INTEGER       NOT NULL,
    customer_id    INTEGER       NOT NULL REFERENCES customers (customer_id),
    order_date     DATE          NOT NULL,
    status         TEXT          NOT NULL,  -- delivered / returned / canceled, регистр не нормализован
    payment_method TEXT,
    order_number   SMALLINT      NOT NULL,  -- порядковый номер заказа клиента
    total_amount   NUMERIC(12,2) NOT NULL   -- сумма заказа со скидкой, руб.
);

CREATE TABLE order_items (
    order_id   INTEGER       NOT NULL,
    product_id INTEGER       NOT NULL REFERENCES products (product_id),
    quantity   INTEGER       NOT NULL,
    unit_price NUMERIC(12,2) NOT NULL,      -- цена продажи за единицу, руб.
    discount   NUMERIC(4,2)  NOT NULL       -- скидка на позицию, доля от 0 до 1
);

CREATE TABLE marketing_spend (
    month   TEXT          NOT NULL,         -- YYYY-MM
    channel TEXT          NOT NULL,
    spend   NUMERIC(14,2) NOT NULL,         -- расходы на канал за месяц, руб.
    clicks  INTEGER       NOT NULL,
    PRIMARY KEY (month, channel)
);

-- Распределение по группам A/B-теста реактивации спящих клиентов.
-- Заказы участников лежат в общей таблице orders и ничем не помечены:
-- связать их с экспериментом можно только через эту таблицу и даты окна.
CREATE TABLE ab_experiment (
    customer_id   INTEGER PRIMARY KEY REFERENCES customers (customer_id),
    group_name    TEXT    NOT NULL CHECK (group_name IN ('control', 'test')),
    assigned_date DATE    NOT NULL
);

CREATE INDEX idx_orders_customer ON orders (customer_id);
CREATE INDEX idx_orders_date     ON orders (order_date);
CREATE INDEX idx_items_order     ON order_items (order_id);
CREATE INDEX idx_items_product   ON order_items (product_id);
