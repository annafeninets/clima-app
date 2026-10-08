#!/usr/bin/env python3
"""Переносит данные Clima из старой базы SQLite в PostgreSQL.

Сохраняет идентификаторы (на них ссылаются фото и избранное), переносит сессии, после вставки
выравнивает счётчики id. Целевые таблицы должны быть пустыми. Всё выполняется одной транзакцией:
при любой ошибке PostgreSQL остаётся нетронутым.

    docker compose cp backend:/data/clima.sqlite3 ./clima.sqlite3
    make dev-db
    uv run python scripts/sqlite_to_postgres.py --sqlite clima.sqlite3 \\
        --database-url postgresql://clima:ПАРОЛЬ@127.0.0.1:5432/clima
"""

import argparse
from datetime import date
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from psycopg.types.json import Jsonb  # noqa: E402

from clima.database.database import Database  # noqa: E402
from clima.repositories.mappers import datetime_from_db  # noqa: E402

# (таблица, колонки, преобразования значений) в порядке внешних ключей.
TABLES = [
    ("users", ["id", "created_at", "email", "phone", "password_hash", "location", "preferences", "settings"],
     {"created_at": datetime_from_db, "preferences": json.loads, "settings": json.loads}),
    ("sessions", ["token", "user_id", "expires_at"], {"expires_at": datetime_from_db}),
    ("items", ["id", "user_id", "created_at", "photo", "type", "color", "seasons", "min_temperature",
               "max_temperature", "part", "dress_code", "style", "silhouette", "material",
               "in_laundry", "deleted"],
     {"created_at": datetime_from_db, "seasons": json.loads, "in_laundry": bool, "deleted": bool}),
    ("outfits", ["id", "user_id", "created_at", "outfit_date", "place", "occasion", "selected", "rating"],
     {"created_at": datetime_from_db, "outfit_date": date.fromisoformat, "selected": bool}),
    ("outfit_items", ["outfit_id", "item_id"], {}),
    ("favorites", ["id", "user_id", "outfit_id", "created_at"], {"created_at": datetime_from_db}),
]
JSON_COLUMNS = {"preferences", "settings", "seasons"}
IDENTITY_TABLES = ["users", "items", "outfits", "favorites"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sqlite", required=True, type=Path, help="путь к clima.sqlite3")
    parser.add_argument("--database-url", required=True, help="адрес PostgreSQL (как CLIMA_DATABASE_URL)")
    args = parser.parse_args()
    if not args.sqlite.is_file():
        print(f"Файл не найден: {args.sqlite}", file=sys.stderr)
        return 1

    source = sqlite3.connect(f"file:{args.sqlite}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    database = Database(args.database_url, maxSize=2)  # заодно создаёт схему, если её ещё нет
    try:
        with database.transaction():
            for table, _, _ in TABLES:
                if database.query(f"SELECT 1 FROM {table} LIMIT 1"):
                    print(f"Таблица {table} в PostgreSQL не пуста — перенос отменён", file=sys.stderr)
                    return 1
            for table, columns, converters in TABLES:
                rows = source.execute(f"SELECT {', '.join(columns)} FROM {table}").fetchall()
                insert = (
                    f"INSERT INTO {table}({', '.join(columns)}) OVERRIDING SYSTEM VALUE "
                    f"VALUES({', '.join(['%s'] * len(columns))})"
                )
                for row in rows:
                    values = []
                    for column in columns:
                        value = row[column]
                        if value is not None and column in converters:
                            value = converters[column](value)
                        if column in JSON_COLUMNS:
                            value = Jsonb(value)
                        values.append(value)
                    database.execute(insert, values)
                print(f"{table}: перенесено строк — {len(rows)}")
            for table in IDENTITY_TABLES:
                database.execute(
                    f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                    f"(SELECT MAX(id) FROM {table}) IS NOT NULL)"
                )
    finally:
        database.close()
        source.close()
    print("Готово. Проверьте вход в приложение и запустите backend на PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
