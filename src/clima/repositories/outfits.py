from collections import defaultdict
from datetime import date
from typing import Any, Mapping

from clima.errors import NotFoundError
from clima.models.entities import Outfit
from clima.repositories.base import Repository
from clima.repositories.items import ItemsRepository
from clima.repositories.mappers import datetime_from_db, item_from_row
from clima.database.database import Database


class OutfitsRepository(Repository[Outfit]):
    def __init__(self, db: Database, itemsRepository: ItemsRepository):
        super().__init__(db)
        self.itemsRepository = itemsRepository

    def findById(self, id: int) -> Outfit | None:
        rows = self.db.query("SELECT * FROM outfits WHERE id=%s", (id,))
        return self._hydrate(rows)[0] if rows else None

    def findByUser(self, userId: int) -> list[Outfit]:
        rows = self.db.query(
            "SELECT * FROM outfits WHERE user_id=%s ORDER BY created_at DESC, id DESC", (userId,)
        )
        return self._hydrate(rows)

    def findHistoryByUser(self, userId: int) -> list[Outfit]:
        rows = self.db.query(
            """SELECT * FROM outfits WHERE user_id=%s AND selected
               ORDER BY created_at DESC, id DESC""", (userId,)
        )
        return self._hydrate(rows)

    def findSelectedByUser(self, userId: int, date: date) -> list[Outfit]:
        rows = self.db.query(
            """SELECT * FROM outfits WHERE user_id=%s AND outfit_date=%s AND selected
               ORDER BY created_at DESC, id DESC""", (userId, date)
        )
        return self._hydrate(rows)

    def findByDate(self, userId: int, date: date, place: str) -> list[Outfit]:
        rows = self.db.query(
            """SELECT o.* FROM outfits o
               WHERE o.user_id=%s AND o.outfit_date=%s AND o.place=%s AND NOT o.selected
               AND NOT EXISTS (
                   SELECT 1 FROM favorites f
                   WHERE f.user_id=o.user_id AND f.outfit_id=o.id
               )
               ORDER BY o.created_at DESC, o.id DESC""",
            (userId, date, place),
        )
        return self._hydrate(rows)

    def deleteGeneratedByDate(self, userId: int, date: date, place: str) -> None:
        self.db.execute(
            """DELETE FROM outfits
               WHERE user_id=%s AND outfit_date=%s AND place=%s AND NOT selected
               AND NOT EXISTS (
                   SELECT 1 FROM favorites f
                   WHERE f.user_id=outfits.user_id AND f.outfit_id=outfits.id
               )""",
            (userId, date, place),
        )

    def create(self, entity: Outfit) -> None:
        self.save([entity])

    def save(self, outfits: list[Outfit]) -> None:
        with self.db.transaction():
            for outfit in outfits:
                self._insert(outfit)

    def add(self, entity: Outfit) -> None:
        self.create(entity)

    def update(self, entity: Outfit) -> None:
        with self.db.transaction():
            result = self.db.execute(
                """UPDATE outfits SET outfit_date=%s,place=%s,occasion=%s,selected=%s,rating=%s
                   WHERE id=%s AND user_id=%s""",
                (entity.date, entity.place, entity.occasion, entity.selected,
                 entity.rating, entity.id, entity.userId),
            )
            if result.rowcount == 0:
                raise NotFoundError("Аутфит не найден")
            self.db.execute("DELETE FROM outfit_items WHERE outfit_id=%s", (entity.id,))
            self._linkItems(entity)

    def delete(self, id: int) -> None:
        self.db.execute("DELETE FROM outfits WHERE id=%s", (id,))

    def _hydrate(self, rows: list[Mapping[str, Any]]) -> list[Outfit]:
        """Собирает аутфиты вместе с вещами одним дополнительным запросом (без N+1)."""
        if not rows:
            return []
        item_rows = self.db.query(
            """SELECT oi.outfit_id, i.* FROM outfit_items oi
               JOIN items i ON i.id = oi.item_id
               WHERE oi.outfit_id = ANY(%s) ORDER BY i.id""",
            ([row["id"] for row in rows],),
        )
        items = defaultdict(list)
        for item_row in item_rows:
            items[item_row["outfit_id"]].append(item_from_row(item_row))
        return [
            Outfit(
                id=row["id"], userId=row["user_id"], createdAt=datetime_from_db(row["created_at"]),
                date=row["outfit_date"], place=row["place"], occasion=row["occasion"],
                selected=row["selected"], rating=row["rating"], items=items[row["id"]],
            )
            for row in rows
        ]

    def _insert(self, outfit: Outfit) -> None:
        outfit.id = self.db.insert(
            """INSERT INTO outfits(user_id,created_at,outfit_date,place,occasion,selected,rating)
               VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (outfit.userId, outfit.createdAt, outfit.date, outfit.place,
             outfit.occasion, outfit.selected, outfit.rating),
        )
        self._linkItems(outfit)

    def _linkItems(self, outfit: Outfit) -> None:
        if outfit.items:
            self.db.execute(
                "INSERT INTO outfit_items(outfit_id,item_id) SELECT %s, unnest(%s::bigint[])",
                (outfit.id, [item.id for item in outfit.items]),
            )
