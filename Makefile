.PHONY: up down logs build test secrets backup

up:        ## собрать и запустить backend + frontend
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f --tail=100

build:
	docker compose build

test:
	uv run python -m unittest discover -s tests -v

secrets:   ## сгенерировать VAPID-ключи и токен планировщика в .env
	uv run python scripts/gen_secrets.py

backup:
	./scripts/backup.sh
