import json
from datetime import datetime, time
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from clima.errors import NotFoundError
from clima.models.entities import User
from clima.repositories.base import Repository
from clima.database.database import Database
from clima.repositories.mappers import user_from_row


class UsersRepository(Repository[User]):
    def findById(self, id: int) -> User | None:
        rows = self.db.query("SELECT * FROM users WHERE id = ?", (id,))
        return user_from_row(rows[0]) if rows else None

    def findByEmail(self, email: str) -> User | None:
        rows = self.db.query(
            "SELECT * FROM users WHERE email = ? COLLATE NOCASE", (email.strip(),)
        )
        return user_from_row(rows[0]) if rows else None

    def findByPhone(self, phone: str) -> User | None:
        rows = self.db.query("SELECT * FROM users WHERE phone = ?", (phone.strip(),))
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
        return [
            user for row in self.db.query("SELECT * FROM users")
            if (user := user_from_row(row)).settings.notificationsEnabled
        ]

    def add(self, entity: User) -> None:
        cursor = self.db.execute(
            """INSERT INTO users(created_at,email,phone,password_hash,location,preferences,settings)
               VALUES(?,?,?,?,?,?,?)""",
            (
                entity.createdAt.isoformat(), entity.email, entity.phone, entity.passwordHash,
                entity.location, self._preferences(entity), self._settings(entity),
            ),
        )
        entity.id = cursor.lastrowid or 0

    def update(self, entity: User) -> None:
        cursor = self.db.execute(
            """UPDATE users SET email=?,phone=?,password_hash=?,location=?,preferences=?,settings=?
               WHERE id=?""",
            (
                entity.email, entity.phone, entity.passwordHash, entity.location,
                self._preferences(entity), self._settings(entity), entity.id,
            ),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("Пользователь не найден")

    def delete(self, id: int) -> None:
        self.db.execute("DELETE FROM users WHERE id=?", (id,))

    def saveSession(self, token: str, userId: int, expiresAt: datetime) -> None:
        self.db.execute(
            "INSERT INTO sessions(token,user_id,expires_at) VALUES(?,?,?)",
            (token, userId, expiresAt.isoformat()),
        )

    def findSession(self, token: str):
        rows = self.db.query("SELECT * FROM sessions WHERE token=?", (token,))
        return rows[0] if rows else None

    def deleteSession(self, token: str) -> None:
        self.db.execute("DELETE FROM sessions WHERE token=?", (token,))

    def deleteSessionsByUser(self, userId: int) -> None:
        self.db.execute("DELETE FROM sessions WHERE user_id=?", (userId,))

    @staticmethod
    def _preferences(entity: User) -> str:
        return json.dumps({
            "style": entity.preferences.style, "colors": entity.preferences.colors,
            "sizes": entity.preferences.sizes, "bodyFeatures": entity.preferences.bodyFeatures,
        }, ensure_ascii=False)

    @staticmethod
    def _settings(entity: User) -> str:
        settings = entity.settings
        subscription = settings.pushSubscription
        return json.dumps({
            "theme": settings.theme.value,
            "notificationsEnabled": settings.notificationsEnabled,
            "notificationTime": settings.notificationTime.isoformat(timespec="minutes"),
            "timeZone": settings.timeZone,
            "pushSubscription": ({
                "endpoint": subscription.endpoint,
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            } if subscription else None),
        })
