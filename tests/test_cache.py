"""Кеш: TTL в памяти и «fail-open» поведение Redis-обёртки (без настоящего Redis)."""

from time import sleep
import unittest

from clima.cache import MemoryCache, RedisCache, create_cache


class MemoryCacheTests(unittest.TestCase):
    def test_returns_value_until_ttl_expires(self):
        cache = MemoryCache()
        cache.set("k", "v", 60)
        self.assertEqual(cache.get("k"), "v")
        cache.set("short", "v", 0.01)
        sleep(0.03)
        self.assertIsNone(cache.get("short"))

    def test_delete_and_missing_key(self):
        cache = MemoryCache()
        cache.set("a", "1", 60)
        cache.delete("a", "does-not-exist")
        self.assertIsNone(cache.get("a"))

    def test_evicts_when_full(self):
        cache = MemoryCache(maxEntries=10)
        for index in range(25):
            cache.set(f"k{index}", "v", 60)
        self.assertLessEqual(len(cache._data), 10)
        self.assertEqual(cache.get("k24"), "v")


class FakeRedis:
    def __init__(self, broken=False):
        self.broken = broken
        self.data = {}
        self.calls = []

    def _check(self):
        if self.broken:
            raise ConnectionError("redis is down")

    def get(self, key):
        self._check()
        return self.data.get(key)

    def set(self, key, value, px=None):
        self._check()
        self.calls.append(("set", key, px))
        self.data[key] = value

    def eval(self, script, numkeys, key, ttl):
        self._check()
        self.calls.append(("eval", key, ttl))
        value = int(self.data.get(key, 0)) + 1
        self.data[key] = str(value)
        return value

    def delete(self, *keys):
        self._check()
        for key in keys:
            self.data.pop(key, None)

    def ping(self):
        self._check()
        return True

    def close(self):
        pass


class RedisCacheTests(unittest.TestCase):
    def test_prefixes_keys_and_passes_ttl_in_milliseconds(self):
        fake = FakeRedis()
        cache = RedisCache("redis://unused", client=fake)
        cache.set("weather:x", "payload", 1.5)
        self.assertEqual(fake.calls, [("set", "clima:weather:x", 1500)])
        self.assertEqual(cache.get("weather:x"), "payload")
        cache.delete("weather:x")
        self.assertIsNone(cache.get("weather:x"))
        self.assertTrue(cache.ping())

    def test_failures_do_not_propagate(self):
        cache = RedisCache("redis://unused", client=FakeRedis(broken=True))
        cache.set("k", "v", 10)
        cache.delete("k")
        self.assertIsNone(cache.get("k"))
        self.assertIsNone(cache.increment("counter", 60))
        self.assertFalse(cache.ping())

    def test_increment_is_atomic_and_sets_expiry_on_first_increment(self):
        fake = FakeRedis()
        cache = RedisCache("redis://unused", client=fake)

        self.assertEqual(cache.increment("push_count", 60), 1)
        self.assertEqual(cache.increment("push_count", 30), 2)
        self.assertEqual(fake.data["clima:push_count"], "2")
        self.assertEqual(fake.calls, [
            ("eval", "clima:push_count", 60000),
            ("eval", "clima:push_count", 30000),
        ])

    def test_factory_uses_memory_cache_without_url(self):
        self.assertIsInstance(create_cache(""), MemoryCache)
        self.assertIsInstance(create_cache("   "), MemoryCache)
