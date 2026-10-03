"""SQLite connection and schema management."""

from pathlib import Path
import sqlite3
from threading import RLock


class Database:
    _instance: "Database | None" = None
    _instance_lock = RLock()
    _schema_path = Path(__file__).with_name("schema.sql")

    def __init__(self, path: str | Path = "clima.sqlite3"):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            self.path, check_same_thread=False, isolation_level=None, timeout=30
        )
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        if self.path != ":memory:":
            self._connection.execute("PRAGMA journal_mode = WAL")
        self._initialize()

    @classmethod
    def getInstance(cls, path: str | Path | None = None) -> "Database":
        with cls._instance_lock:
            instance = cls._instance
            if instance is None:
                instance = cls(path or "clima.sqlite3")
                cls._instance = instance
            elif path is not None and instance.path != str(path):
                raise RuntimeError("Database singleton is already initialized with another path")
            return instance

    @classmethod
    def resetInstance(cls) -> None:
        with cls._instance_lock:
            if cls._instance is not None:
                cls._instance.close()
                cls._instance = None

    def _initialize(self) -> None:
        schema = self._schema_path.read_text(encoding="utf-8")
        with self._lock:
            self._connection.executescript(schema)

    def getConnection(self) -> sqlite3.Connection:
        return self._connection

    def execute(self, sql: str, parameters: tuple = ()) -> sqlite3.Cursor:
        with self._lock:
            return self._connection.execute(sql, parameters)

    def query(self, sql: str, parameters: tuple = ()) -> list[sqlite3.Row]:
        with self._lock:
            return self._connection.execute(sql, parameters).fetchall()

    def transaction(self):
        return _Transaction(self)

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class _Transaction:
    def __init__(self, database: Database):
        self.database = database

    def __enter__(self):
        self.database._lock.acquire()
        try:
            self.database._connection.execute("BEGIN IMMEDIATE")
        except BaseException:
            self.database._lock.release()
            raise
        return self.database._connection

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.database._connection.execute("ROLLBACK" if exc_type else "COMMIT")
        finally:
            self.database._lock.release()
        return False
