from datetime import date
import sqlite3

from clima.errors import NotFoundError
from clima.models.entities import Item, Outfit
from clima.repositories.base import Repository
from clima.repositories.items import ItemsRepository
from clima.repositories.mappers import datetime_from_db, item_from_row
from clima.database.database import Database


class OutfitsRepository(Repository[Outfit]):
    def __init__(self, db: Database, itemsRepository: ItemsRepository):
        super().__init__(db)
        self.itemsRepository = itemsRepository

    def findById(self, id: int) -> Outfit | None:
        rows = self.db.query("SELECT * FROM outfits WHERE id=?", (id,))
        return self._withItems(rows[0]) if rows else None

    def findByUser(self, userId: int) -> list[Outfit]:
        rows = self.db.query(
            "SELECT * FROM outfits WHERE user_id=? ORDER BY created_at DESC", (userId,)
        )
        return [self._withItems(row) for row in rows]

    def findHistoryByUser(self, userId: int) -> list[Outfit]:
        rows = self.db.query(
            """SELECT * FROM outfits WHERE user_id=? AND selected=1
               ORDER BY created_at DESC""", (userId,)
        )
        return [self._withItems(row) for row in rows]

    def findSelectedByUser(self, userId: int, date: date) -> list[Outfit]:
        rows = self.db.query(
            """SELECT * FROM outfits WHERE user_id=? AND outfit_date=? AND selected=1
               ORDER BY created_at DESC""", (userId, date.isoformat())
        )
        return [self._withItems(row) for row in rows]

    def findByDate(self, userId: int, date: date, place: str) -> list[Outfit]:
        rows = self.db.query(
            """SELECT o.* FROM outfits o
               WHERE o.user_id=? AND o.outfit_date=? AND o.place=? AND o.selected=0
               AND NOT EXISTS (
                   SELECT 1 FROM favorites f
                   WHERE f.user_id=o.user_id AND f.outfit_id=o.id
               )
               ORDER BY o.created_at DESC""",
            (userId, date.isoformat(), place),
        )
        return [self._withItems(row) for row in rows]

    def deleteGeneratedByDate(self, userId: int, date: date, place: str) -> None:
        self.db.execute(
            """DELETE FROM outfits
               WHERE user_id=? AND outfit_date=? AND place=? AND selected=0
               AND NOT EXISTS (
                   SELECT 1 FROM favorites f
                   WHERE f.user_id=outfits.user_id AND f.outfit_id=outfits.id
               )""",
            (userId, date.isoformat(), place),
        )

    def create(self, entity: Outfit) -> None:
        self.save([entity])

    def save(self, outfits: list[Outfit]) -> None:
        with self.db.transaction() as connection:
            for outfit in outfits:
                self._insert(connection, outfit)

    def add(self, entity: Outfit) -> None:
        self.create(entity)

    def update(self, entity: Outfit) -> None:
        with self.db.transaction() as connection:
            cursor = connection.execute(
                """UPDATE outfits SET outfit_date=?,place=?,occasion=?,selected=?,rating=?
                   WHERE id=? AND user_id=?""",
                (entity.date.isoformat(), entity.place, entity.occasion, int(entity.selected),
                 entity.rating, entity.id, entity.userId),
            )
            if cursor.rowcount == 0:
                raise NotFoundError("Аутфит не найден")
            connection.execute("DELETE FROM outfit_items WHERE outfit_id=?", (entity.id,))
            for item in entity.items:
                connection.execute(
                    "INSERT INTO outfit_items(outfit_id,item_id) VALUES(?,?)",
                    (entity.id, item.id),
                )

    def delete(self, id: int) -> None:
        self.db.execute("DELETE FROM outfits WHERE id=?", (id,))

    def _withItems(self, row: sqlite3.Row) -> Outfit:
        rows = self.db.query(
            """SELECT i.* FROM items i JOIN outfit_items oi ON oi.item_id=i.id
               WHERE oi.outfit_id=?""", (row["id"],)
        )
        return Outfit(
            id=row["id"], userId=row["user_id"], createdAt=datetime_from_db(row["created_at"]),
            date=date.fromisoformat(row["outfit_date"]), place=row["place"],
            occasion=row["occasion"], selected=bool(row["selected"]), rating=row["rating"],
            items=[item_from_row(item_row) for item_row in rows],
        )

    @staticmethod
    def _insert(connection, outfit: Outfit) -> None:
        cursor = connection.execute(
            """INSERT INTO outfits(user_id,created_at,outfit_date,place,occasion,selected,rating)
               VALUES(?,?,?,?,?,?,?)""",
            (outfit.userId, outfit.createdAt.isoformat(), outfit.date.isoformat(), outfit.place,
             outfit.occasion, int(outfit.selected), outfit.rating),
        )
        outfit.id = cursor.lastrowid or 0
        connection.executemany(
            "INSERT INTO outfit_items(outfit_id,item_id) VALUES(?,?)",
            [(outfit.id, item.id) for item in outfit.items],
        )
