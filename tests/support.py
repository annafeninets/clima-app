"""Общие помощники тестов с PostgreSQL.

Тесты, которым нужна база, берут адрес из CLIMA_TEST_DATABASE_URL и работают в отдельной схеме
со случайным именем, которую удаляют после теста, — рабочие данные не затрагиваются.
Пример: CLIMA_TEST_DATABASE_URL=postgresql://clima:пароль@127.0.0.1:5432/clima_test
"""

import os
import unittest
import uuid

TEST_DATABASE_URL = os.environ.get("CLIMA_TEST_DATABASE_URL", "").strip()
NO_DATABASE_REASON = "задайте CLIMA_TEST_DATABASE_URL (PostgreSQL), чтобы запустить тесты с БД"

requires_database = unittest.skipUnless(TEST_DATABASE_URL, NO_DATABASE_REASON)


def new_schema_name() -> str:
    return f"test_{uuid.uuid4().hex[:16]}"


def drop_schema(name: str) -> None:
    import psycopg
    from psycopg import sql

    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(name))
        )
