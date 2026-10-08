from datetime import datetime
from types import SimpleNamespace
import unittest
from zoneinfo import ZoneInfo

from clima.cache import MemoryCache
from clima.errors import NotEnoughItemsError
from clima.controllers.notifications import formatMissingText
from clima.scheduler import Scheduler


class FakeOutfitController:
    def __init__(self, status):
        self.status = status

    def getTodayOutfit(self, userId):
        raise NotEnoughItemsError(
            "Недостаточно чистых вещей",
            self.status["missing"],
            self.status["have"],
        )

    def getWardrobeStatus(self, userId):
        return self.status


class FakeNotificationController:
    def __init__(self, user):
        self.user = user
        self.hints = []

    def findDueUsers(self, now):
        return [self.user]

    def hasPushSubscription(self, userId):
        return True

    def sendWardrobeHint(self, userId, missing):
        self.hints.append((userId, missing))


class SchedulerTests(unittest.TestCase):
    def test_missing_categories_are_formatted_for_people(self):
        self.assertEqual(
            formatMissingText(["bottom", "shoes"]),
            "Не хватает: низ, обувь. Добавьте, чтобы получить образ",
        )

    def setUp(self):
        self.user = SimpleNamespace(
            id=7,
            location="Moscow",
            settings=SimpleNamespace(timeZone="Europe/Moscow"),
        )
        self.status = {
            "have": {"top": 1, "outerwear": 0, "bottom": 0, "shoes": 0},
            "missing": ["bottom", "shoes"],
            "is_complete": False,
        }
        self.cache = MemoryCache()
        self.notifications = FakeNotificationController(self.user)
        self.scheduler = Scheduler(
            None,
            FakeOutfitController(self.status),
            self.notifications,
            self.cache,
        )

    def test_shortage_sends_once_and_does_not_mark_daily_outfit_as_sent(self):
        self.scheduler.triggerMorningBroadcast()
        self.scheduler.triggerMorningBroadcast()

        local_day = datetime.now(ZoneInfo("Europe/Moscow")).date()
        self.assertEqual(self.notifications.hints, [(7, ["bottom", "shoes"])])
        self.assertIsNone(self.cache.get(self.scheduler._deliveredKey(7, local_day)))
        self.assertEqual(
            self.cache.get(self.scheduler._wardrobeHintKey(7, local_day)), "1"
        )

    def test_complete_wardrobe_still_receives_hint_when_no_outfit_can_be_built(self):
        self.status.update({"missing": [], "is_complete": True})
        self.scheduler.triggerMorningBroadcast()

        self.assertEqual(self.notifications.hints, [(7, [])])
        self.assertEqual(len(self.cache._data), 1)


if __name__ == "__main__":
    unittest.main()
