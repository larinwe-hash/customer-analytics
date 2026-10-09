"""
Подключение к PostgreSQL.

Параметры читаются из переменных окружения, а если их нет — из файла .env
в корне проекта. Шаблон лежит в .env.example.

Использование:

    from db import get_engine
    engine = get_engine()
    df = pd.read_sql('SELECT * FROM sales LIMIT 5', engine)
"""

from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV_PATH = os.path.join(BASE_DIR, '.env')

DEFAULTS = {
    'PGHOST': 'localhost',
    'PGPORT': '5432',
    'PGDATABASE': 'shop',
    'PGUSER': 'postgres',
    'PGPASSWORD': 'postgres',
}


def load_env(path: str = ENV_PATH) -> None:
    """Читает .env, не перезаписывая уже заданные переменные окружения."""
    if not os.path.exists(path):
        return
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"\''))


def get_settings() -> dict:
    load_env()
    return {key: os.environ.get(key, default) for key, default in DEFAULTS.items()}


def get_dsn() -> str:
    s = get_settings()
    return (f"postgresql+psycopg2://{s['PGUSER']}:{s['PGPASSWORD']}"
            f"@{s['PGHOST']}:{s['PGPORT']}/{s['PGDATABASE']}")


def get_engine(**kwargs) -> Engine:
    """Создаёт SQLAlchemy-движок для подключения к базе проекта."""
    return create_engine(get_dsn(), future=True, **kwargs)


def describe_connection() -> str:
    """Строка подключения без пароля — для вывода в логах и ноутбуке."""
    s = get_settings()
    return f"{s['PGUSER']}@{s['PGHOST']}:{s['PGPORT']}/{s['PGDATABASE']}"
