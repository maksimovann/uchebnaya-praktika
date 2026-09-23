# CRM: карточка партнера и CRUD

Итоговая версия этапа объединяет два экрана, добавление и редактирование партнеров, обновление реестра без перезагрузки, валидацию и диалоговые уведомления.

## Возможности

- `MainWindow`: реестр партнеров, поиск, обновление и кнопка добавления.
- `PartnerEditWindow`: карточка добавления/редактирования с отдельным заголовком страницы.
- Поля типа партнера, рейтинга, адреса, директора, ИНН, телефона и email.
- `POST /api/partners`, `GET /api/partners/{id}` и `PUT /api/partners/{id}`.
- Error, Warning и Information диалоги с соответствующими пиктограммами.
- Предупреждение при выходе из измененной формы без сохранения.
- Автоматическое обновление реестра после успешного сохранения.

## Запуск с PostgreSQL

База прошлой практики: `partners_db`, PostgreSQL 18, порт `5432`. При первом запуске приложение автоматически добавляет недостающие поля в таблицу `partners`.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-postgres.txt
.\.venv\Scripts\python.exe server.py --postgres --pg-database partners_db --pg-port 5432 --port 8767
```

Введите пароль PostgreSQL локально в терминале. Откройте `http://127.0.0.1:8767/` и не закрывайте терминал во время работы.

## Демонстрационный запуск без PostgreSQL

```powershell
python server.py --port 8767
```

В этом режиме создается локальная SQLite-база `practice.sqlite3`.

## Тесты

```powershell
python -m unittest discover -s tests -v
```

Тесты проверяют расчет скидок, импорт, отсутствие истории продаж, CRUD API и ошибки валидации.
