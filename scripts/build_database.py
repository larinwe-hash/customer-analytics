"""
Сборка аналитической базы PostgreSQL из CSV-выгрузки.

Скрипт применяет схему из sql/01_schema.sql, загружает файлы из data/raw/
командой COPY и создаёт очищенные представления из sql/03_clean_views.sql.

Параметры подключения берутся из переменных окружения или из .env
(см. .env.example).

Запуск: python scripts/build_database.py
"""

from __future__ import annotations

import os
import sys

import pandas as pd
from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import describe_connection, get_engine  # noqa: E402

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')
SQL_DIR = os.path.join(BASE_DIR, 'sql')

# Порядок важен: на customers и products ссылаются внешние ключи
TABLES = [
    ('customers', 'customers.csv'),
    ('products', 'products.csv'),
    ('orders', 'orders.csv'),
    ('order_items', 'order_items.csv'),
    ('marketing_spend', 'marketing_spend.csv'),
    ('ab_experiment', 'ab_experiment.csv'),
]


def read_sql_file(name: str) -> str:
    with open(os.path.join(SQL_DIR, name), encoding='utf-8') as f:
        return f.read()


def copy_csv(raw_connection, table: str, file_path: str) -> int:
    """Загружает CSV в таблицу через COPY — быстрее построчных INSERT."""
    columns = pd.read_csv(file_path, nrows=0).columns.tolist()
    column_list = ', '.join(f'"{c}"' for c in columns)
    cursor = raw_connection.cursor()
    with open(file_path, encoding='utf-8') as f:
        cursor.copy_expert(
            f'COPY {table} ({column_list}) FROM STDIN WITH (FORMAT csv, HEADER true)',
            f,
        )
    count = cursor.rowcount
    cursor.close()
    return count


def main() -> None:
    missing = [f for _, f in TABLES if not os.path.exists(os.path.join(RAW_DIR, f))]
    if missing:
        raise SystemExit(
            'Не найдены файлы: ' + ', '.join(missing)
            + '\nСначала выполните: python scripts/generate_data.py'
        )

    engine = get_engine()
    print(f'Подключение: {describe_connection()}')

    try:
        with engine.begin() as conn:
            conn.execute(text(read_sql_file('01_schema.sql')))
    except Exception as error:  # noqa: BLE001
        raise SystemExit(
            f'Не удалось подключиться к базе или применить схему:\n  {error}\n\n'
            'Проверьте, что PostgreSQL запущен и параметры в .env верны.'
        )

    raw = engine.raw_connection()
    try:
        for table, file_name in TABLES:
            rows = copy_csv(raw, table, os.path.join(RAW_DIR, file_name))
            print(f'{table:<16} загружено строк: {rows:>6,}'.replace(',', ' '))
        raw.commit()
    finally:
        raw.close()

    with engine.begin() as conn:
        conn.execute(text(read_sql_file('03_clean_views.sql')))
        views = conn.execute(text("""
            SELECT table_name
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)).scalars().all()

    print('\nСозданы представления:', ', '.join(views))
    print('База готова.')


if __name__ == '__main__':
    main()
