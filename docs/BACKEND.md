# Backend

Backend Clima — чистый Python 3.14 без веб-фреймворка. HTTP-сервер построен на стандартном `ThreadingHTTPServer`, данные пользователей, сессии, вещи, аутфиты и избранное хранятся в PostgreSQL (`psycopg` 3 + пул соединений), фотографии вещей — в отдельном каталоге на диске. Redis (необязателен) используется как кеш прогноза погоды, геокодинга и отметок утренней рассылки; при его отсутствии работает in-memory кеш процесса.

## Быстрый старт (локально)

```bash
uv sync
export CLIMA_DATABASE_URL=postgresql://clima:ПАРОЛЬ@127.0.0.1:5432/clima
# опционально:
# export CLIMA_REDIS_URL=redis://127.0.0.1:6379/0
uv run clima
```

API по умолчанию слушает `http://127.0.0.1:8000`.  
`GET /health` возвращает 200, если сервер и база доступны, иначе 503.

Для разработки удобно поднимать только инфраструктуру:

```bash
make dev-db   # PostgreSQL + Redis на localhost (см. docker.md)
```

## Переменные окружения

| Переменная | Обязательна | Назначение |
|---|---|---|
| `CLIMA_DATABASE_URL` | да | Строка подключения к PostgreSQL |
| `CLIMA_REDIS_URL` | нет | Redis (`redis://…`). Пусто → кеш в памяти |
| `CLIMA_DB_POOL_MAX` | нет | Максимум соединений в пуле (по умолчанию 10) |
| `CLIMA_HOST` / `CLIMA_PORT` | нет | Адрес и порт HTTP-сервера (по умолчанию `127.0.0.1:8000`) |
| `CLIMA_UPLOADS_PATH` | нет | Каталог для фотографий (по умолчанию `./data/uploads`) |
| `CLIMA_CORS_ORIGINS` | нет | Список разрешённых origin через запятую |
| `CLIMA_VAPID_PRIVATE_KEY` | для push | Приватный VAPID-ключ |
| `CLIMA_VAPID_SUBJECT` | для push | Subject для Web Push (`mailto:…`) |
| `CLIMA_SCHEDULER_TOKEN` | нет | Токен для ручного запуска утренней рассылки |
| `CLIMA_OPENWEATHER_API_KEY` | нет | Ключ OpenWeather. Без него используется только Open-Meteo |
| `CLIMA_LOG_LEVEL` | нет | Уровень логирования (`INFO` по умолчанию) |

## Архитектура

Структура соответствует слоям UML:

```
src/clima/
├── main.py                 # точка входа, загрузка конфигурации, запуск сервера
├── api.py                  # маршрутизация и сериализация запросов/ответов
├── config.py               # сборка конфигурации из env
├── container.py            # composition root
├── scheduler.py            # фоновый планировщик утренних push
├── cache.py                # абстракция кеша (Redis / in-memory)
├── outfit_rules.py         # правила сочетаемости и слоёв одежды
├── push_limits.py          # ограничения на push-уведомления
├── errors.py               # доменные ошибки
│
├── boundaries/
│   └── http_gateway.py     # HTTP-адаптер (ThreadingHTTPServer)
│
├── handlers/               # обработчики HTTP-запросов
│   ├── command.py
│   ├── callback.py
│   ├── settings.py
│   ├── schedule.py
│   └── upload.py
│
├── controllers/            # прикладная логика
│   ├── users.py
│   ├── profile.py
│   ├── wardrobe.py
│   ├── outfits.py
│   ├── notifications.py
│   ├── cities.py
│   └── feedback.py
│
├── repositories/           # доступ к данным
│   ├── users.py
│   ├── items.py
│   ├── outfits.py
│   ├── favorites.py
│   ├── mappers.py          # преобразование строк БД → сущности
│   └── base.py
│
├── models/
│   ├── entities/           # User, Item, Outfit, Favorite, Settings, Preferences
│   ├── enums.py
│   └── value_objects.py
│
├── database/
│   ├── database.py         # пул, миграции схемы (CREATE TABLE IF NOT EXISTS)
│   └── schema.sql
│
└── integrations/
    ├── weather.py          # фасад погоды
    ├── openweather.py
    ├── places.py
    ├── push.py             # Web Push
    └── photo_storage.py
```

- `main.py` только загружает конфигурацию и запускает сервер.
- `api.py` содержит таблицу маршрутов и преобразует HTTP ↔ value objects.
- SQL-схема хранится отдельно в `database/schema.sql` и применяется при старте под advisory-lock.

## HTTP API

Все ответы обёрнуты в конверт:

```json
{
  "success": true,
  "message": "...",
  "data": { ... }
}
```

Ошибки возвращают `success: false`, человекочитаемое `message` и соответствующий HTTP-статус.

Защищённые маршруты требуют заголовок:

```
Authorization: Bearer <token>
```

### Группы маршрутов

| Группа | Префикс / маршруты | Описание |
|---|---|---|
| Авторизация | `/auth/form`, `/auth/login`, `/auth/register`, `/auth/logout` | Регистрация (`login`, `password`, `confirm`), вход, выход |
| Профиль и настройки | `/profile`, `/profile/location`, `/settings`, `/settings/theme`, `/settings/notifications`, `/account` | Профиль, тема, уведомления, удаление аккаунта |
| Push | `/push/subscribe`, `/push/subscriptions`, `/push/settings` | Подписка, отписка, настройки времени |
| Гардероб | `/wardrobe`, `/wardrobe/status`, `/wardrobe/items`, `/wardrobe/items/draft`, `/wardrobe/items/{id}`, `/wardrobe/items/{id}/photo`, `/wardrobe/items/{id}/laundry` | CRUD вещей, фото, статус стирки, комплектность |
| Места | `/places/search`, `/places/context` | Поиск городов и контекст |
| Аутфиты | `/outfits/plan`, `/outfits/today`, `/outfits/history`, `/outfits/rate`, `/outfits/{id}`, `/outfits/{id}/select`, `/outfits/{id}/unselect`, `/outfits/{id}/rating` | Подбор, история, оценка, выбор |
| Избранное | `/favorites/*` | Сохранённые комплекты |
| Служебные | `/health`, `/internal/scheduler/morning` | Healthcheck и ручной запуск рассылки |

### Особенности эндпоинтов

- **`GET /wardrobe/status`** — количество вещей по категориям и список обязательных недостающих. Комплект считается достаточным, если есть (верх + низ) или платье/комбинезон, а также обувь.
- **`GET /outfits/plan`** — при недостатке вещей возвращает `409` с телом:
  ```json
  {
    "success": false,
    "error": "insufficient_wardrobe",
    "missing": ["top", "shoes"],
    "have": { "bottom": 2 }
  }
  ```
- **Загрузка фото** (`POST /wardrobe/items`):
  - base64 в JSON или бинарное тело `application/octet-stream`;
  - форматы: PNG, JPEG, GIF, WebP;
  - максимум 5 МБ.
  После загрузки клиент получает путь и передаёт его вместе с характеристиками в `PUT /wardrobe/items/draft`.
- **Погода**:
  - приоритет — OpenWeather (бесплатный план: геокодинг + «5 дней / 3 часа»);
  - fallback — Open-Meteo (до 16 дней, без ключа);
  - при временном сбое обоих сервисов используется недавно сохранённый прогноз.
- **Планировщик**:
  - фоновый поток проверяет локальное время уведомлений пользователя;
  - ручной запуск: `POST /internal/scheduler/morning` с заголовком `X-Scheduler-Token`;
  - через nginx маршрут `/api/internal/` закрыт (404).

## Правила гардероба и подбора

Категории вещей:

- верх
- низ
- обувь
- верхняя одежда
- аксессуары
- платье / комбинезон

Правила комплекта:

- обязательны: (верх + низ) **или** платье/комбинезон, плюс обувь;
- верхняя одежда — отдельный слой поверх верха;
- куртки/пальто предлагаются при ≤ 15 °C или осадках;
- шарфы — при ≤ 8 °C или снеге/морозе;
- в одном образе: не более одного базового верха, одного низа, одной пары обуви и одной верхней одежды;
- аксессуары разных типов можно сочетать, одинаковые типы — нельзя (две сумки, два шарфа и т.д.).

Автоматическое распознавание типа/цвета вещи по фото **не реализовано** — характеристики задаёт пользователь.

## CitiesController

Контроллер поиска городов через геокодинг OpenWeather.

```python
controller = CitiesController(weather_service)
results = controller.search_cities(user_id, "London")
```

Каждый результат содержит:

| Поле | Описание |
|---|---|
| `name` | Название города |
| `region` | Регион / штат (если есть) |
| `country` | Код страны |
| `lat` / `lon` | Координаты |
| `timezone` | Часовой пояс (пока пустая строка — API геокодинга не отдаёт) |
| `id` | Сгенерированный идентификатор `{slug}-{country.lower()}` |

При отсутствии ключа OpenWeather или ошибке API выбрасывается `ServiceUnavailableError`.

## Тестирование

```bash
# отдельная тестовая база
docker compose exec postgres createdb -U clima clima_test
export CLIMA_TEST_DATABASE_URL=postgresql://clima:ПАРОЛЬ@127.0.0.1:5432/clima_test

make test
# или
uv run python -m unittest discover -s tests -v
```

Каждый тест, которому нужна БД, работает в собственной временной схеме PostgreSQL и удаляет её по завершении. Без `CLIMA_TEST_DATABASE_URL` тесты с базой пропускаются; тесты кеша и погоды выполняются всегда. В наборе есть проверка HTTP-границы и корректной остановки процесса по `SIGTERM`.

## Безопасность и жизненный цикл

- Контейнер backend (см. `docker.md`) запускается от непривилегированного пользователя, с read-only корневой ФС; запись разрешена только в `/data`.
- При получении `SIGTERM` корректно останавливается планировщик и закрывается пул соединений с БД.
- Сессии и пользовательские данные всегда живут в PostgreSQL; Redis хранит только восстанавливаемые данные (прогноз, геокодинг, флаги рассылки).
