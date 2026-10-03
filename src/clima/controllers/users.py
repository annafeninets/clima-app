from datetime import datetime, timedelta, timezone
import re
import secrets
import sqlite3

from clima.errors import AuthError, ValidationError
from clima.integrations.photo_storage import PhotoStorage
from clima.models.entities import User
from clima.models.value_objects import Messages, Session
from clima.repositories.users import UsersRepository


class AuthController:
    SESSION_TTL = timedelta(days=30)

    def __init__(self, usersRepository: UsersRepository, photoStorage: PhotoStorage):
        self.usersRepository = usersRepository
        self.photoStorage = photoStorage

    def startAuth(self) -> None:
        return None

    def register(self, login: str, password: str, confirm: str) -> Session:
        login = login.strip()
        if password != confirm:
            raise ValidationError(Messages.PASSWORD_MISMATCH)
        if len(password) < 8:
            raise ValidationError("Пароль должен содержать не менее 8 символов")
        email = login.lower() if "@" in login else None
        phone = self._normalizePhone(login) if email is None else None
        if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
            raise ValidationError("Укажите корректный email")
        if phone and len(re.sub(r"\D", "", phone)) < 7:
            raise ValidationError("Укажите корректный номер телефона")
        if self.usersRepository.findByEmailOrPhone(email or phone or login):
            raise ValidationError(Messages.ACCOUNT_EXISTS)
        user = User(email=email, phone=phone)
        user.setPassword(password)
        try:
            self.usersRepository.add(user)
        except sqlite3.IntegrityError as error:
            raise ValidationError(Messages.ACCOUNT_EXISTS) from error
        return self._newSession(user)

    def login(self, login: str, password: str) -> Session:
        login = login.strip()
        user = self.usersRepository.findByEmailOrPhone(
            login.lower() if "@" in login else self._normalizePhone(login)
        )
        if user is None or not user.checkPassword(password):
            raise AuthError(Messages.INVALID_CREDENTIALS)
        return self._newSession(user)

    def validateSession(self, token: str) -> Session:
        row = self.usersRepository.findSession(token)
        if row is None:
            raise AuthError(Messages.SESSION_EXPIRED)
        session = Session(token, row["user_id"], datetime.fromisoformat(row["expires_at"]))
        if session.isExpired():
            self.usersRepository.deleteSession(token)
            raise AuthError(Messages.SESSION_EXPIRED)
        return session

    def deleteAccount(self, userId: int) -> None:
        self.usersRepository.deleteSessionsByUser(userId)
        self.photoStorage.deleteAllByUser(userId)
        self.usersRepository.delete(userId)

    def confirmDelete(self, userId: int) -> None:
        self.deleteAccount(userId)

    def endSession(self, userId: int) -> None:
        self.usersRepository.deleteSessionsByUser(userId)

    def _newSession(self, user: User) -> Session:
        expires = datetime.now(timezone.utc) + self.SESSION_TTL
        session = Session(secrets.token_urlsafe(48), user.id, expires)
        self.usersRepository.saveSession(session.token, session.userId, session.expiresAt)
        return session

    @staticmethod
    def _normalizePhone(value: str) -> str:
        value = value.strip()
        prefix = "+" if value.startswith("+") else ""
        return prefix + re.sub(r"\D", "", value)
