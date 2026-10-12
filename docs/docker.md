# Docker

Стек состоит из четырёх сервисов:

| Сервис | Образ / сборка | Назначение | Данные |
|---|---|---|---|
| `postgres` | `postgres:17-alpine` | Основная БД | том `clima-pgdata` |
| `redis` | `redis:7-alpine` | Кеш погоды, геокодинг, флаги рассылки | без диска (in-memory, LRU 128 MB) |
| `backend` | собирается из корневого `Dockerfile` | Python API | том `clima-data` (фотографии) |
| `frontend` | собирается из `frontend/Dockerfile` | nginx: статика + reverse-proxy `/api/` | — |

CORS не нужен: nginx проксирует `/api/` на backend внутри сети compose.

## Быстрый старт

```bash
cp .env.example .env
make secrets          # VAPID-ключи, токен планировщика, пароль PostgreSQL
docker compose up -d --build
```

Приложение доступно по адресу:

```
http://localhost:8080
```

Порт и интерфейс задаются переменными `CLIMA_WEB_PORT` и `CLIMA_WEB_BIND` (по умолчанию `127.0.0.1:8080`).

Для доступа извне поставьте перед `frontend` HTTPS-прокси: **Web Push работает только по HTTPS** (или на `localhost`).

## Переменные окружения

| Переменная | Назначение |
|---|---|
| `POSTGRES_PASSWORD` (`POSTGRES_USER`, `POSTGRES_DB`) | Пароль и имя роли/базы PostgreSQL. Пароль обязателен, создаётся `make secrets`. Допустимы только символы `A-Za-z0-9-_` (подставляется в URL подключения) |
| `CLIMA_DATABASE_URL` | Адрес PostgreSQL для backend. В compose собирается автоматически из `POSTGRES_*` |
| `CLIMA_REDIS_URL` | Адрес Redis. В compose: `redis://redis:6379/0`. Пустое значение → кеш в памяти процесса |
| `CLIMA_DB_POOL_MAX` | Максимум соединений backend → PostgreSQL (по умолчанию 10) |
| `CLIMA_VAPID_PRIVATE_KEY`, `CLIMA_VAPID_SUBJECT` | Backend: отправка Web Push |
| `CLIMA_VAPID_PUBLIC_KEY` | Frontend: публичный ключ (попадает в `config.js` при старте контейнера) |
| `CLIMA_SCHEDULER_TOKEN` | Заголовок `X-Scheduler-Token` для ручного запуска рассылки |
| `CLIMA_OPENWEATHER_API_KEY` | Ключ OpenWeather. Без него прогноз берётся только из Open-Meteo. Новый ключ активируется не сразу (до пары часов) |
| `CLIMA_PUBLIC_API_URL` | Адрес API для браузера (по умолчанию `/api`) |
| `CLIMA_CORS_ORIGINS` | Нужен только если frontend открыт с другого origin, чем API |
| `CLIMA_WEB_BIND` / `CLIMA_WEB_PORT` | Интерфейс и порт публикации frontend |

Полный список с комментариями — в `.env.example`.

## Важные особенности

- Без заполненного `.env` стек поднимется, но push-уведомления будут отключены (в логе backend появится предупреждение).
- Маршрут `/internal/scheduler/morning` через nginx закрыт (`/api/internal/` → 404). Утренняя рассылка работает фоновым потоком backend; ручной запуск возможен только изнутри сети compose.
- Контейнер backend запускается от непривилегированного пользователя, с read-only корневой ФС; пишет только в `/data` (фотографии). Данные пользователей лежат в PostgreSQL.
- `docker stop` корректно завершает backend по `SIGTERM`: останавливается планировщик, закрывается пул соединений.
- Redis хранит только восстанавливаемые данные. Если он недоступен, backend пишет предупреждение и продолжает работу без кеша.
- Обновление:

  ```bash
  git pull && docker compose up -d --build
  ```

  Данные в томах сохраняются. Схема БД создаётся автоматически при старте backend (`CREATE TABLE IF NOT EXISTS` под advisory-lock). Изменения существующих таблиц так не применятся — для них нужна миграция.
- `POSTGRES_PASSWORD` читается PostgreSQL только при создании тома. Если поменять пароль в `.env` позже, backend перестанет подключаться. Смените пароль и в базе:

  ```bash
  docker compose exec postgres psql -U clima -c "ALTER ROLE clima PASSWORD 'новый_пароль'"
  ```

  Поэтому `make secrets --force` пароль не перезаписывает.
- Пересоздание VAPID-ключей (`--force`) делает уже оформленные push-подписки недействительными — пользователям нужно заново включить уведомления.

## Резервное копирование и восстановление

```bash
make backup
```

В каталоге `./backups` появятся:

- `clima-*.dump` — `pg_dump` в формате custom;
- `uploads-*.tar` — архив фотографий.

Восстановление:

```bash
# 1. Останавливаем backend и frontend
docker compose stop backend frontend

# 2. Восстанавливаем базу
docker compose exec -T postgres sh -c \
  'pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists' \
  < backups/clima-ДАТА.dump

# 3. Распаковываем фотографии в том clima-data
#    (способ зависит от того, как вы монтируете том)
```

## Разработка

Поднять только PostgreSQL и Redis на localhost (чтобы запускать backend через `uv run clima`):

```bash
make dev-db
# эквивалент:
# docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis
```

Порты:

- PostgreSQL → `127.0.0.1:5432`
- Redis → `127.0.0.1:6379`

## Makefile-команды

| Команда | Действие |
|---|---|
| `make up` | Собрать и запустить весь стек |
| `make down` | Остановить |
| `make logs` | Логи с хвостом |
| `make build` | Только сборка образов |
| `make dev-db` | PostgreSQL + Redis на localhost |
| `make secrets` | Генерация секретов в `.env` |
| `make backup` | Резервная копия БД и фотографий |
| `make test` | Запуск unit-тестов (нужен `CLIMA_TEST_DATABASE_URL`) |

## Безопасность контейнеров

- `security_opt: no-new-privileges:true` на всех сервисах.
- Backend: `read_only: true`, `cap_drop: ALL`, `tmpfs: /tmp`, пользователь `clima` (uid 10001).
- Redis: без персистентности (`--save ""`, `--appendonly no`), лимит памяти 128 MB, политика `allkeys-lru`.
- Frontend: nginx отдаёт только статику и проксирует API; `/api/internal/` заблокирован.

## Миграция со старой версии на SQLite

Если в томе `clima-data` остался файл `clima.sqlite3` от предыдущей версии:

```bash
# 1. Скопировать старую базу (backend должен быть запущен старой версией)
docker compose cp backend:/data/clima.sqlite3 ./clima.sqlite3

# 2. Поднять PostgreSQL и Redis
make dev-db

# 3. Перенести данные (идентификаторы и сессии сохраняются)
uv run python scripts/sqlite_to_postgres.py \
  --sqlite clima.sqlite3 \
  --database-url postgresql://clima:ПАРОЛЬ@127.0.0.1:5432/clima

# 4. Запустить актуальный стек
docker compose up -d --build
```

## Схема сети и прокси

```
Браузер
   │
   ▼
frontend (nginx :80)
   ├── /                 → статика (index.html, src/, styles/)
   ├── /config.js        → генерируется при старте
   ├── /service-worker.js
   └── /api/*            → proxy_pass http://backend:8000/
         └── /api/internal/* → 404 (закрыто)
```

Публичный порт наружу публикует только `frontend`. Backend и базы доступны только внутри сети compose.
