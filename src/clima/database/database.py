"""PostgreSQL connection pool and schema management."""

from contextlib import contextmanager
import logging
from pathlib import Path
import re
from threading import RLock, local
from typing import Any

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

logger = logging.getLogger(__name__)

# Произвольное число для pg_advisory_xact_lock: несколько реплик backend не будут
# одновременно создавать схему при старте.
_SCHEMA_LOCK_ID = 7_351_201


class Result:
    """Итог одного запроса: число затронутых строк и (если были) сами строки."""

    __slots__ = ("rowcount", "rows")

    def __init__(self, rowcount: int, rows: list[dict[str, Any]]):
        self.rowcount = rowcount
        self.rows = rows


class Database:
    _instance: "Database | None" = None
    _instance_lock = RLock()
    _schema_path = Path(__file__).with_name("schema.sql")

    def __init__(
        self, url: str, *, schema: str | None = None, minSize: int = 1, maxSize: int = 10,
        startupTimeout: float = 30.0,
    ):
        if not url:
            raise ValueError("Не задан адрес PostgreSQL (CLIMA_DATABASE_URL)")
        if schema is not None and not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError("Некорректное имя схемы PostgreSQL")
        self.url = url
        self.schema = schema
        self._local = local()
        kwargs: dict[str, Any] = {"autocommit": True, "row_factory": dict_row}
        if schema:
            with psycopg.connect(url, autocommit=True) as admin:
                admin.execute(
                    sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(schema))
                )
            kwargs["options"] = f"-c search_path={schema}"
        self._pool = ConnectionPool(
            url, min_size=minSize, max_size=maxSize, kwargs=kwargs, open=False, name="clima-db",
        )
        try:
            # Ждём первое соединение: при недоступной базе падаем на старте, а не на первом запросе.
            self._pool.open(wait=True, timeout=startupTimeout)
            self._initialize()
        except BaseException:
            self._pool.close()
            raise

    @classmethod
    def getInstance(
        cls, url: str | None = None, schema: str | None = None, maxSize: int = 10,
    ) -> "Database":
        with cls._instance_lock:
            instance = cls._instance
            if instance is None:
                if not url:
                    raise RuntimeError("Database ещё не инициализирована: нужен адрес PostgreSQL")
                instance = cls(url, schema=schema, maxSize=maxSize)
                cls._instance = instance
            elif url is not None and (instance.url, instance.schema) != (url, schema):
                raise RuntimeError("Database singleton is already initialized with another URL")
            return instance

    @classmethod
    def resetInstance(cls) -> None:
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None

    def _initialize(self) -> None:
        schema = self._schema_path.read_text(encoding="utf-8")
        with self._pool.connection() as connection:
            with connection.transaction():
                connection.execute("SELECT pg_advisory_xact_lock(%s)", (_SCHEMA_LOCK_ID,))
                connection.execute(schema)

    def getConnection(self):
        """Контекст-менеджер: ``with db.getConnection() as connection`` берёт соединение из пула."""
        return self._pool.connection()

    def execute(self, sql_text: str, parameters: tuple | list = ()) -> Result:
        connection = getattr(self._local, "connection", None)
        if connection is not None:  # внутри transaction() этого потока
            return self._run(connection, sql_text, parameters)
        with self._pool.connection() as connection:
            return self._run(connection, sql_text, parameters)

    def query(self, sql_text: str, parameters: tuple | list = ()) -> list[dict[str, Any]]:
        return self.execute(sql_text, parameters).rows

    def insert(self, sql_text: str, parameters: tuple | list = ()) -> int:
        """Выполняет ``INSERT ... RETURNING id`` и возвращает выданный id."""
        return self.execute(sql_text, parameters).rows[0]["id"]

    @contextmanager
    def transaction(self):
        """Транзакция потока: все ``execute``/``query`` внутри неё идут через одно соединение.

        Вложенный вызов превращается в SAVEPOINT.
        """
        outer = getattr(self._local, "connection", None)
        if outer is not None:
            with outer.transaction():
                yield outer
            return
        with self._pool.connection() as connection:
            self._local.connection = connection
            try:
                with connection.transaction():
                    yield connection
            finally:
                self._local.connection = None

    def close(self) -> None:
        self._pool.close()

    @staticmethod
    def _run(connection, sql_text: str, parameters) -> Result:
        cursor = connection.execute(sql_text, parameters)
        rows = cursor.fetchall() if cursor.description else []
        return Result(cursor.rowcount, rows)
