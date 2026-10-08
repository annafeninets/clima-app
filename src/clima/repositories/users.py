from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from psycopg.types.json import Jsonb

from clima.errors import NotFoundError
from clima.models.entities import User
from clima.repositories.base import Repository
from clima.repositories.mappers import user_from_row


class UsersRepository(Repository[User]):
    def findById(self, id: int) -> User | None:
        rows = self.db.query("SELECT * FROM users WHERE id = %s", (id,))
        return user_from_row(rows[0]) if rows else None

    def findByEmail(self, email: str) -> User | None:
        rows = self.db.query(
            "SELECT * FROM users WHERE lower(email) = lower(%s)", (email.strip(),)
        )
        return user_from_row(rows[0]) if rows else None

    def findByPhone(self, phone: str) -> User | None:
        rows = self.db.query("SELECT * FROM users WHERE phone = %s", (phone.strip(),))
        return user_from_row(rows[0]) if rows else None

    def findByEmailOrPhone(self, login: str) -> User | None:
        return self.findByEmail(login) if "@" in login else self.findByPhone(login)

    def findByNotificationTime(self, time: time) -> list[User]:
        return [
            user for user in self.findNotificationUsers()
            if user.settings.notificationTime.hour == time.hour
            and user.settings.notificationTime.minute == time.minute
        ]

    def findDueUsers(self, now: datetime) -> list[User]:
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        due = []
        for user in self.findNotificationUsers():
            try:
                local_now = now.astimezone(ZoneInfo(user.settings.timeZone))
            except (ZoneInfoNotFoundError, ValueError):
                continue
            if local_now.strftime("%H:%M") == user.settings.notificationTime.strftime("%H:%M"):
                due.append(user)
        return due

    def findNotificationUsers(self) -> list[User]:
        rows = self.db.query(
            "SELECT * FROM users WHERE (settings->>'notificationsEnabled')::boolean IS TRUE"
        )
        return [user_from_row(row) for row in rows]

    def add(self, entity: User) -> None:
        entity.id = self.db.insert(
            """INSERT INTO users(created_at,email,phone,password_hash,location,preferences,settings)
               VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                entity.createdAt, entity.email, entity.phone, entity.passwordHash,
                entity.location, Jsonb(self._preferences(entity)), Jsonb(self._settings(entity)),
            ),
        )

    def update(self, entity: User) -> None:
        result = self.db.execute(
            """UPDATE users SET email=%s,phone=%s,password_hash=%s,location=%s,
               preferences=%s,settings=%s WHERE id=%s""",
            (
                entity.email, entity.phone, entity.passwordHash, entity.location,
                Jsonb(self._preferences(entity)), Jsonb(self._settings(entity)), entity.id,
            ),
        )
        if result.rowcount == 0:
            raise NotFoundError("Пользователь не найден")

    def delete(self, id: int) -> None:
        self.db.execute("DELETE FROM users WHERE id=%s", (id,))

    def saveSession(self, token: str, userId: int, expiresAt: datetime) -> None:
        self.db.execute(
            "INSERT INTO sessions(token,user_id,expires_at) VALUES(%s,%s,%s)",
            (token, userId, expiresAt),
        )

    def findSession(self, token: str):
        rows = self.db.query("SELECT * FROM sessions WHERE token=%s", (token,))
        return rows[0] if rows else None

    def deleteSession(self, token: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE token=%s", (token,))

    def deleteSessionsByUser(self, userId: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id=%s", (userId,))

    @staticmethod
    def _preferences(entity: User) -> dict:
        return {
            "style": entity.preferences.style, "colors": entity.preferences.colors,
            "sizes": entity.preferences.sizes, "bodyFeatures": entity.preferences.bodyFeatures,
        }

    @staticmethod
    def _settings(entity: User) -> dict:
        settings = entity.settings
        subscription = settings.pushSubscription
        return {
            "theme": settings.theme.value,
            "notificationsEnabled": settings.notificationsEnabled,
            "notificationTime": settings.notificationTime.isoformat(timespec="minutes"),
            "timeZone": settings.timeZone,
            "pushSubscription": ({
                "endpoint": subscription.endpoint,
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            } if subscription else None),
        }
