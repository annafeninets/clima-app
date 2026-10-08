"""Key-value cache with TTL: in-process by default, Redis when ``CLIMA_REDIS_URL`` is set.

Кеш не является источником истины: всё, что в нём лежит, можно восстановить из PostgreSQL
или внешних API. Поэтому ``RedisCache`` «fail-open»: при недоступном Redis чтение возвращает
``None``, запись молча пропускается, и приложение продолжает работать без кеша.
"""

from __future__ import annotations

import logging
from threading import RLock
from time import monotonic
from typing import Protocol

logger = logging.getLogger(__name__)


class Cache(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str, ttlSeconds: float) -> None: ...

    def increment(self, key: str, ttlSeconds: float) -> int | None: ...

    def delete(self, *keys: str) -> None: ...

    def ping(self) -> bool: ...

    def close(self) -> None: ...


class MemoryCache:
    """Потокобезопасный кеш в памяти процесса (по умолчанию и для тестов)."""

    def __init__(self, maxEntries: int = 10_000):
        self.maxEntries = maxEntries
        self._lock = RLock()
        self._data: dict[str, tuple[float, str]] = {}

    def get(self, key: str) -> str | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            if entry[0] <= monotonic():
                del self._data[key]
                return None
            return entry[1]

    def set(self, key: str, value: str, ttlSeconds: float) -> None:
        with self._lock:
            if key not in self._data and len(self._data) >= self.maxEntries:
                self._evict()
            self._data[key] = (monotonic() + ttlSeconds, value)

    def increment(self, key: str, ttlSeconds: float) -> int:
        with self._lock:
            current = self.get(key)
            value = int(current or 0) + 1
            if current is None:
                self.set(key, str(value), ttlSeconds)
            else:
                expires, _ = self._data[key]
                self._data[key] = (expires, str(value))
            return value

    def delete(self, *keys: str) -> None:
        with self._lock:
            for key in keys:
                self._data.pop(key, None)

    def ping(self) -> bool:
        return True

    def close(self) -> None:
        with self._lock:
            self._data.clear()

    def _evict(self) -> None:
        now = monotonic()
        for key in [key for key, (expires, _) in self._data.items() if expires <= now]:
            del self._data[key]
        if len(self._data) >= self.maxEntries:
            # dict помнит порядок вставки: выбрасываем самые старые ~10 %.
            for key in list(self._data)[: max(1, self.maxEntries // 10)]:
                del self._data[key]


class RedisCache:
    """Кеш поверх Redis. Любая ошибка Redis логируется (не чаще раза в 30 с) и не пробрасывается."""

    _WARN_EVERY = 30.0

    def __init__(self, url: str, prefix: str = "clima:", client=None):
        if client is None:
            import redis  # ленивый импорт: без CLIMA_REDIS_URL пакет не нужен

            client = redis.Redis.from_url(
                url, decode_responses=True, socket_timeout=0.5,
                socket_connect_timeout=0.5, health_check_interval=30,
            )
        self._redis = client
        self._prefix = prefix
        self._lastWarning = float("-inf")

    def get(self, key: str) -> str | None:
        try:
            return self._redis.get(self._prefix + key)
        except Exception as error:
            self._warn("get", error)
            return None

    def set(self, key: str, value: str, ttlSeconds: float) -> None:
        try:
            self._redis.set(self._prefix + key, value, px=max(1, int(ttlSeconds * 1000)))
        except Exception as error:
            self._warn("set", error)

    def increment(self, key: str, ttlSeconds: float) -> int | None:
        try:
            result = self._redis.eval(
                "local n=redis.call('INCR',KEYS[1]); "
                "if n==1 then redis.call('PEXPIRE',KEYS[1],ARGV[1]); end; "
                "return n",
                1,
                self._prefix + key,
                max(1, int(ttlSeconds * 1000)),
            )
            return int(result)
        except Exception as error:
            self._warn("increment", error)
            return None

    def delete(self, *keys: str) -> None:
        if not keys:
            return
        try:
            self._redis.delete(*(self._prefix + key for key in keys))
        except Exception as error:
            self._warn("delete", error)

    def ping(self) -> bool:
        try:
            return bool(self._redis.ping())
        except Exception:
            return False

    def close(self) -> None:
        try:
            self._redis.close()
        except Exception:
            pass

    def _warn(self, operation: str, error: Exception) -> None:
        now = monotonic()
        if now - self._lastWarning >= self._WARN_EVERY:
            self._lastWarning = now
            logger.warning("Redis недоступен (%s: %s), работаем без кеша", operation, error)


def create_cache(redisUrl: str = "") -> Cache:
    if redisUrl.strip():
        return RedisCache(redisUrl.strip())
    return MemoryCache()
