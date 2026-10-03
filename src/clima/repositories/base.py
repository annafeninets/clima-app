from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from clima.errors import NotFoundError
from clima.models.entities import Entity
from clima.database.database import Database

T = TypeVar("T", bound=Entity)


class Repository(ABC, Generic[T]):
    def __init__(self, db: Database):
        self.db = db

    @abstractmethod
    def findById(self, id: int) -> T | None:
        raise NotImplementedError

    @abstractmethod
    def add(self, entity: T) -> None:
        raise NotImplementedError

    @abstractmethod
    def update(self, entity: T) -> None:
        raise NotImplementedError

    @abstractmethod
    def delete(self, id: int) -> None:
        raise NotImplementedError

    def requireById(self, id: int) -> T:
        entity = self.findById(id)
        if entity is None:
            raise NotFoundError("Объект не найден")
        return entity
