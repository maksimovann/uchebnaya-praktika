# Интеграция с БД и агрегация данных

`database.py` содержит локальную реализацию на SQLite, а `postgres_database.py` подключается к схеме прошлой практики в PostgreSQL (`partners`, `products`, `shipments`). Оба варианта используют `LEFT JOIN`, `SUM(quantity)`, `GROUP BY` и `COALESCE` для партнеров без истории продаж.

Результат запроса дополняется процентом из `calculate_partner_discount`. Проверки находятся в `tests/test_database.py`. 
