.PHONY: up down logs build test secrets backup dev-db

up:        ## собрать и запустить backend + frontend
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

build:
	docker compose build

dev-db:   ## поднять только PostgreSQL и Redis на localhost для `uv run clima`
	docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d postgres redis

test:      ## нужен CLIMA_TEST_DATABASE_URL (см. README), иначе тесты с БД пропускаются
	uv run python -m unittest discover -s tests -v

secrets:   ## сгенерировать VAPID-ключи, токен планировщика и пароль PostgreSQL в .env
	uv run python scripts/gen_secrets.py

backup:
	./scripts/backup.sh
