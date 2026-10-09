"""
Генерация синтетического датасета интернет-магазина.

Скрипт создаёт CSV-файлы в data/raw/: клиенты, товары, заказы, позиции заказов
и расходы на маркетинг. Данные вымышленные, но воспроизводят поведение,
характерное для реального e-commerce:

* каналы привлечения различаются по качеству аудитории (удержание, средний чек);
* спрос сезонный: пик в ноябре-декабре, спад в январе и летом;
* часть клиентов покупает один раз и больше не возвращается;
* у заказов есть возвраты и отмены, их нужно исключать из выручки;
* в данных намеренно оставлены типичные дефекты (дубли, пропуски, разный
  регистр в категориях) — их обработка входит в задачу анализа.

Запуск: python scripts/generate_data.py
"""

from __future__ import annotations

import os
import random
from datetime import date, timedelta

import numpy as np
import pandas as pd

SEED = 42
START_DATE = date(2024, 1, 1)
END_DATE = date(2025, 12, 31)
N_CUSTOMERS = 4200

# A/B-тест реактивации спящих клиентов
EXPERIMENT_START = date(2025, 10, 1)
EXPERIMENT_END = date(2025, 11, 15)
DORMANCY_DAYS = 90          # сколько дней без покупок считаем "спящим" клиентом
CONTROL_CONVERSION = 0.035  # обычная рассылка
TEST_CONVERSION = 0.058     # письмо с промокодом на 10%
TEST_DISCOUNT = 0.10

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(BASE_DIR, 'data', 'raw')

rng = np.random.default_rng(SEED)
random.seed(SEED)

# --------------------------------------------------------------------------- #
# Справочники
# --------------------------------------------------------------------------- #

# Каналы различаются качеством аудитории:
#   share      — доля канала в привлечении,
#   conversion — доля зарегистрировавшихся, кто сделал хотя бы один заказ,
#   retention  — вероятность вернуться за следующей покупкой,
#   basket     — множитель среднего чека,
#   cac        — стоимость привлечения одного зарегистрированного клиента, руб.
CHANNELS = {
    'organic':     dict(share=0.22, conversion=0.72, retention=0.52, basket=1.05, cac=220),
    'paid_search': dict(share=0.26, conversion=0.61, retention=0.38, basket=1.00, cac=1200),
    'social_ads':  dict(share=0.24, conversion=0.44, retention=0.19, basket=0.82, cac=1600),
    'email':       dict(share=0.14, conversion=0.78, retention=0.58, basket=1.12, cac=380),
    'referral':    dict(share=0.14, conversion=0.81, retention=0.61, basket=1.18, cac=850),
}

DEVICES = {'mobile': 0.61, 'desktop': 0.31, 'tablet': 0.08}

CITIES = {
    'Москва': 0.27, 'Санкт-Петербург': 0.14, 'Новосибирск': 0.07,
    'Екатеринбург': 0.07, 'Казань': 0.06, 'Нижний Новгород': 0.05,
    'Челябинск': 0.04, 'Самара': 0.04, 'Краснодар': 0.05, 'Ростов-на-Дону': 0.04,
    'Уфа': 0.03, 'Пермь': 0.03, 'Воронеж': 0.03, 'Владивосток': 0.03,
    'Калининград': 0.02, 'Другой': 0.03,
}

# Категории: доля в каталоге, границы цены, вероятность возврата
CATEGORIES = {
    'Кофе и чай':      dict(share=0.24, price=(450, 2600),   returns=0.01),
    'Посуда':          dict(share=0.17, price=(900, 9500),   returns=0.04),
    'Техника для дома': dict(share=0.09, price=(3500, 28000), returns=0.07),
    'Текстиль':        dict(share=0.15, price=(1200, 12000), returns=0.09),
    'Декор':           dict(share=0.17, price=(600, 9000),   returns=0.05),
    'Хранение':        dict(share=0.18, price=(400, 6800),   returns=0.03),
}

BRANDS = ['Nordvik', 'Kezma', 'Lumio', 'Варяг', 'Tavola', 'Orbis',
          'Светлица', 'Brevis', 'Мирта', 'Haveli', 'Soleno', 'Пикта']

PRODUCT_WORDS = {
    'Кофе и чай': ['Кофе в зёрнах', 'Молотый кофе', 'Чай улун', 'Чай пуэр',
                   'Френч-пресс', 'Турка', 'Кофемолка', 'Набор чая'],
    'Посуда': ['Сковорода', 'Кастрюля', 'Набор тарелок', 'Чайник',
               'Салатник', 'Нож шеф', 'Разделочная доска', 'Форма для выпечки'],
    'Техника для дома': ['Блендер', 'Мультиварка', 'Увлажнитель', 'Пылесос',
                         'Тостер', 'Кофемашина', 'Очиститель воздуха', 'Миксер'],
    'Текстиль': ['Плед', 'Комплект белья', 'Полотенце', 'Штора',
                 'Подушка', 'Скатерть', 'Ковёр', 'Покрывало'],
    'Декор': ['Ваза', 'Светильник', 'Постер', 'Зеркало',
              'Подсвечник', 'Кашпо', 'Часы настенные', 'Гирлянда'],
    'Хранение': ['Корзина', 'Органайзер', 'Контейнер', 'Полка',
                 'Короб', 'Вешалка', 'Ящик', 'Набор банок'],
}

# Сезонность спроса по месяцам (1 — средний уровень)
SEASONALITY = {
    1: 0.72, 2: 0.88, 3: 1.06, 4: 0.97, 5: 0.90, 6: 0.82,
    7: 0.78, 8: 0.92, 9: 1.08, 10: 1.12, 11: 1.52, 12: 1.44,
}


def pick(mapping: dict, size: int) -> np.ndarray:
    """Случайный выбор ключей словаря с весами."""
    keys = list(mapping)
    weights = np.array([mapping[k] if isinstance(mapping[k], float) else mapping[k]['share']
                        for k in keys], dtype=float)
    return rng.choice(keys, size=size, p=weights / weights.sum())


# --------------------------------------------------------------------------- #
# Товары
# --------------------------------------------------------------------------- #

def make_products(n: int = 320) -> pd.DataFrame:
    rows = []
    for product_id in range(1, n + 1):
        category = pick(CATEGORIES, 1)[0]
        cfg = CATEGORIES[category]
        low, high = cfg['price']
        price = float(np.round(rng.uniform(low, high) / 10) * 10)
        rows.append({
            'product_id': product_id,
            'product_name': f'{random.choice(PRODUCT_WORDS[category])} {random.choice(BRANDS)}',
            'category': category,
            'price': price,
            'cost_price': round(price * rng.uniform(0.42, 0.68), 2),
        })
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- #
# Клиенты
# --------------------------------------------------------------------------- #

def make_customers(n: int = N_CUSTOMERS) -> pd.DataFrame:
    days = (END_DATE - START_DATE).days
    # Приток клиентов растёт со временем и повторяет сезонность
    weights = np.array([
        SEASONALITY[(START_DATE + timedelta(days=int(d))).month] * (1 + 0.45 * d / days)
        for d in range(days + 1)
    ])
    offsets = rng.choice(days + 1, size=n, p=weights / weights.sum())

    customers = pd.DataFrame({
        'customer_id': np.arange(1, n + 1),
        'signup_date': [START_DATE + timedelta(days=int(o)) for o in np.sort(offsets)],
        'channel': pick(CHANNELS, n),
        'city': pick(CITIES, n),
        'device': pick(DEVICES, n),
    })
    customers['age'] = np.clip(rng.normal(37, 11, n).round(), 18, 75).astype(int)
    customers['is_subscribed'] = (rng.random(n) < 0.46).astype(int)
    return customers


# --------------------------------------------------------------------------- #
# Заказы
# --------------------------------------------------------------------------- #

def make_orders(customers: pd.DataFrame, products: pd.DataFrame):
    orders, items = [], []
    order_id = 100_000
    product_ids = products['product_id'].to_numpy()
    product_price = products.set_index('product_id')['price'].to_dict()
    product_category = products.set_index('product_id')['category'].to_dict()
    # Популярность товаров распределена неравномерно (принцип Парето)
    popularity = rng.pareto(1.6, len(product_ids)) + 1
    popularity = popularity / popularity.sum()

    for customer in customers.itertuples(index=False):
        cfg = CHANNELS[customer.channel]

        # Часть зарегистрировавшихся так и не доходит до первой покупки
        conversion = min(cfg['conversion'] + 0.05 * customer.is_subscribed, 0.97)
        if rng.random() > conversion:
            continue

        # Подписка на рассылку повышает шанс вернуться
        retention = min(cfg['retention'] + 0.07 * customer.is_subscribed, 0.95)
        order_date = customer.signup_date
        n_orders = 0

        while order_date <= END_DATE:
            n_orders += 1
            order_id += 1

            # Корзина: 1-5 позиций
            n_items = int(np.clip(rng.poisson(0.8) + 1, 1, 5))
            chosen = rng.choice(product_ids, size=n_items, replace=False, p=popularity)

            order_total = 0.0
            # Скидка: чаще в высокий сезон
            discount = 0.0
            if rng.random() < 0.28:
                discount = float(rng.choice([0.05, 0.10, 0.15, 0.20]))

            for product_id in chosen:
                quantity = int(np.clip(rng.poisson(0.3) + 1, 1, 6))
                unit_price = round(product_price[product_id] * cfg['basket']
                                   * rng.uniform(0.97, 1.03), 2)
                items.append({
                    'order_id': order_id,
                    'product_id': int(product_id),
                    'quantity': quantity,
                    'unit_price': unit_price,
                    'discount': discount,
                })
                order_total += unit_price * quantity * (1 - discount)

            # Статус заказа: вероятность возврата зависит от категорий в заказе
            return_prob = np.mean([CATEGORIES[product_category[p]]['returns'] for p in chosen])
            roll = rng.random()
            if roll < 0.045:
                status = 'canceled'
            elif roll < 0.045 + return_prob:
                status = 'returned'
            else:
                status = 'delivered'

            payment = rng.choice(['card', 'sbp', 'cash_on_delivery', 'credit'],
                                 p=[0.56, 0.27, 0.11, 0.06])

            orders.append({
                'order_id': order_id,
                'customer_id': customer.customer_id,
                'order_date': order_date,
                'status': status,
                'payment_method': payment,
                'order_number': n_orders,
                'total_amount': round(order_total, 2),
            })

            # Вернётся ли клиент ещё раз
            # Вероятность повторной покупки падает с каждым заказом
            if rng.random() > retention * (0.92 ** (n_orders - 1)):
                break

            # Интервал до следующей покупки: лояльные возвращаются быстрее
            gap = int(np.clip(rng.gamma(2.0, 26 / max(retention, 0.2) / 2.2), 5, 420))
            order_date = order_date + timedelta(days=gap)

    df_orders = pd.DataFrame(orders)
    df_items = pd.DataFrame(items)

    # Сезонность: часть заказов вне высокого сезона "не случилась"
    month_factor = df_orders['order_date'].map(lambda d: SEASONALITY[d.month])
    keep = rng.random(len(df_orders)) < np.clip(month_factor / SEASONALITY[11], 0.35, 1.0)
    # Первый заказ клиента сохраняем всегда, иначе ломается когортный анализ
    keep = keep | (df_orders['order_number'] == 1)
    df_orders = df_orders[keep].reset_index(drop=True)
    df_items = df_items[df_items['order_id'].isin(df_orders['order_id'])].reset_index(drop=True)

    return df_orders, df_items


# --------------------------------------------------------------------------- #
# A/B-тест реактивации
# --------------------------------------------------------------------------- #

def make_experiment(orders: pd.DataFrame, items: pd.DataFrame,
                    products: pd.DataFrame, customers: pd.DataFrame):
    """
    Разыгрывает A/B-тест реактивации спящих клиентов.

    В эксперимент попадает вся спящая база: клиенты, зарегистрированные
    до начала теста, которые либо не заказывали DORMANCY_DAYS дней, либо
    не покупали ни разу. Они случайно делятся пополам:
      * control — обычная рассылка,
      * test    — письмо с промокодом на 10%.

    Клиенты, отреагировавшие на письмо, делают заказ внутри окна эксперимента.
    Эти заказы дописываются в общую таблицу заказов: в реальной базе они
    ничем не помечены, и связать их с тестом можно только через таблицу
    назначений и даты.
    """
    delivered = orders[orders['status'] == 'delivered']
    last_order = delivered.groupby('customer_id')['order_date'].max()
    cutoff = EXPERIMENT_START - timedelta(days=DORMANCY_DAYS)

    registered = customers.loc[customers['signup_date'] < EXPERIMENT_START, 'customer_id']
    dormant = last_order[last_order <= cutoff].index
    never_bought = set(registered) - set(last_order.index)
    eligible = np.array(sorted(set(dormant) | never_bought))

    # Случайное разделение на группы
    groups = rng.choice(['control', 'test'], size=len(eligible), p=[0.5, 0.5])
    assignment = pd.DataFrame({
        'customer_id': eligible,
        'group_name': groups,
        'assigned_date': EXPERIMENT_START.isoformat(),
    })

    product_ids = products['product_id'].to_numpy()
    product_price = products.set_index('product_id')['price'].to_dict()
    window_days = (EXPERIMENT_END - EXPERIMENT_START).days

    # Сколько заказов клиент уже сделал — нужно для сквозной нумерации
    orders_made = orders.groupby('customer_id')['order_number'].max().to_dict()
    order_id = int(orders['order_id'].max())

    new_orders, new_items = [], []

    for row in assignment.itertuples(index=False):
        rate = TEST_CONVERSION if row.group_name == 'test' else CONTROL_CONVERSION
        if rng.random() > rate:
            continue

        order_id += 1
        offset = int(rng.integers(0, window_days + 1))
        order_date = EXPERIMENT_START + timedelta(days=offset)
        discount = TEST_DISCOUNT if row.group_name == 'test' else 0.0

        n_items = int(np.clip(rng.poisson(0.7) + 1, 1, 4))
        chosen = rng.choice(product_ids, size=n_items, replace=False)

        order_total = 0.0
        for product_id in chosen:
            quantity = int(np.clip(rng.poisson(0.3) + 1, 1, 5))
            unit_price = round(product_price[product_id] * rng.uniform(0.97, 1.03), 2)
            new_items.append({
                'order_id': order_id,
                'product_id': int(product_id),
                'quantity': quantity,
                'unit_price': unit_price,
                'discount': discount,
            })
            order_total += unit_price * quantity * (1 - discount)

        # В окне эксперимента доля отмен и возвратов обычная
        roll = rng.random()
        status = 'canceled' if roll < 0.045 else ('returned' if roll < 0.09 else 'delivered')

        orders_made[row.customer_id] = orders_made.get(row.customer_id, 0) + 1
        new_orders.append({
            'order_id': order_id,
            'customer_id': row.customer_id,
            'order_date': order_date,
            'status': status,
            'payment_method': rng.choice(['card', 'sbp', 'cash_on_delivery', 'credit'],
                                         p=[0.56, 0.27, 0.11, 0.06]),
            'order_number': orders_made[row.customer_id],
            'total_amount': round(order_total, 2),
        })

    orders = pd.concat([orders, pd.DataFrame(new_orders)], ignore_index=True)
    items = pd.concat([items, pd.DataFrame(new_items)], ignore_index=True)
    return orders, items, assignment


# --------------------------------------------------------------------------- #
# Маркетинг
# --------------------------------------------------------------------------- #

def make_marketing_spend(customers: pd.DataFrame) -> pd.DataFrame:
    """Расходы по каналам: CAC канала × число привлечённых клиентов + шум."""
    customers = customers.copy()
    customers['month'] = pd.to_datetime(customers['signup_date']).dt.to_period('M').astype(str)
    grouped = customers.groupby(['month', 'channel']).size().reset_index(name='new_customers')

    rows = []
    for row in grouped.itertuples(index=False):
        cac = CHANNELS[row.channel]['cac']
        spend = row.new_customers * cac * rng.uniform(0.88, 1.14)
        rows.append({
            'month': row.month,
            'channel': row.channel,
            'spend': round(spend, 2),
            'clicks': int(row.new_customers * rng.uniform(18, 45)),
        })
    return pd.DataFrame(rows).sort_values(['month', 'channel'], ignore_index=True)


# --------------------------------------------------------------------------- #
# Дефекты данных
# --------------------------------------------------------------------------- #

def add_data_issues(orders: pd.DataFrame, items: pd.DataFrame, customers: pd.DataFrame):
    """Добавляет в данные типичные дефекты, которые нужно найти при анализе."""
    # 1. Дубли строк заказов (двойная выгрузка)
    dupes = orders.sample(frac=0.012, random_state=SEED)
    orders = pd.concat([orders, dupes], ignore_index=True)

    # 2. Разный регистр и лишние пробелы в статусах
    mask = orders.sample(frac=0.05, random_state=SEED + 1).index
    orders.loc[mask, 'status'] = orders.loc[mask, 'status'].str.upper()
    mask = orders.sample(frac=0.03, random_state=SEED + 2).index
    orders.loc[mask, 'status'] = ' ' + orders.loc[mask, 'status'] + ' '

    # 3. Пропуски в необязательных полях клиента
    mask = customers.sample(frac=0.04, random_state=SEED + 3).index
    customers.loc[mask, 'city'] = None
    mask = customers.sample(frac=0.02, random_state=SEED + 4).index
    customers.loc[mask, 'device'] = None

    # 4. Единичные выбросы в количестве (ошибка ввода)
    mask = items.sample(n=14, random_state=SEED + 5).index
    items.loc[mask, 'quantity'] = items.loc[mask, 'quantity'] * 100

    orders = orders.sample(frac=1, random_state=SEED + 6).reset_index(drop=True)
    return orders, items, customers


def main() -> None:
    os.makedirs(RAW_DIR, exist_ok=True)

    products = make_products()
    customers = make_customers()
    orders, items = make_orders(customers, products)
    orders, items, experiment = make_experiment(orders, items, products, customers)
    marketing = make_marketing_spend(customers)
    orders, items, customers = add_data_issues(orders, items, customers)

    products.to_csv(os.path.join(RAW_DIR, 'products.csv'), index=False)
    customers.to_csv(os.path.join(RAW_DIR, 'customers.csv'), index=False)
    orders.to_csv(os.path.join(RAW_DIR, 'orders.csv'), index=False)
    items.to_csv(os.path.join(RAW_DIR, 'order_items.csv'), index=False)
    marketing.to_csv(os.path.join(RAW_DIR, 'marketing_spend.csv'), index=False)
    experiment.to_csv(os.path.join(RAW_DIR, 'ab_experiment.csv'), index=False)

    print(f'Товаров:            {len(products):>7,}'.replace(',', ' '))
    print(f'Клиентов:           {len(customers):>7,}'.replace(',', ' '))
    print(f'Заказов:            {len(orders):>7,}'.replace(',', ' '))
    print(f'Позиций в заказах:  {len(items):>7,}'.replace(',', ' '))
    print(f'Строк по расходам:  {len(marketing):>7,}'.replace(',', ' '))
    print(f'Участников A/B:     {len(experiment):>7,}'.replace(',', ' '))
    print(f'\nФайлы сохранены в {RAW_DIR}')


if __name__ == '__main__':
    main()
