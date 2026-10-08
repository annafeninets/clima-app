## Backend

Backend реализован на Python 3.14 без привязки к веб-фреймворку. HTTP API использует стандартный `ThreadingHTTPServer`, SQLite хранит аккаунты, сессии, вещи, аутфиты и избранное; фотографии сохраняются в отдельном каталоге.

```bash
uv sync
uv run clima
```

По умолчанию API доступен на `http://127.0.0.1:8000`; `GET /health` проверяет доступность сервера и базы данных (503, если база недоступна). Переменные `CLIMA_HOST`, `CLIMA_PORT`, `CLIMA_DB_PATH`, `CLIMA_UPLOADS_PATH` и `CLIMA_CORS_ORIGINS` задают адрес, хранилища и разрешённые CORS-origin. Регистрация принимает JSON с `login`, `password` и `confirm`; вход — с `login` и `password`. Защищённые маршруты требуют заголовок `Authorization: Bearer <token>`.

Маршруты сгруппированы по авторизации (`/auth/*`), профилю и настройкам (`/profile`, `/settings`, `/push/subscriptions`, `/account`), гардеробу (`/wardrobe/*`), подбору и истории (`/outfits/*`), избранному (`/favorites/*`) и внутреннему планировщику (`/internal/scheduler/morning`). После `POST /wardrobe/items` клиент получает путь сохранённого фото и передаёт его вместе с характеристиками в `PUT /wardrobe/items/draft`. Фото можно отправлять base64 в JSON или бинарным телом `application/octet-stream`; поддерживаются PNG, JPEG, GIF и WebP размером до 5 МБ. Прогноз берётся из OpenWeather, если задан `CLIMA_OPENWEATHER_API_KEY` (бесплатный план: геокодинг и прогноз «5 дней / 3 часа», то есть горизонт около 5 суток); для более далёких дат, при неизвестном OpenWeather месте и при его сбое Clima автоматически использует Open-Meteo (до 16 дней, ключ не нужен). Без ключа работает только Open-Meteo. Недавний сохранённый прогноз используется при временном сбое обоих сервисов. Для Web Push задайте `CLIMA_VAPID_PRIVATE_KEY` и `CLIMA_VAPID_SUBJECT`. Фоновый планировщик проверяет локальное время уведомлений; ручной запуск доступен через `POST /internal/scheduler/morning` с заголовком `X-Scheduler-Token`, заданным через `CLIMA_SCHEDULER_TOKEN`.

Backend сохраняет фото и проверенные пользователем характеристики вещей. Автоматическое распознавание типа, цвета и других характеристик по фотографии пока не реализовано: в UML и конфигурации проекта не задан поставщик или модель распознавания.

Успешные запросы возвращают JSON-конверт `{ "success": true, "message": "...", "data": ... }`; ошибки содержат `success: false`, `message` и HTTP-статус.

Проверка backend-тестов: `uv run python -m unittest discover -s tests -v` (или `make test`). В тестах есть проверка HTTP-границы и корректной остановки процесса по SIGTERM.