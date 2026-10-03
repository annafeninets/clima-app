import json

from clima.errors import NotFoundError
from clima.models.entities import Item
from clima.repositories.base import Repository
from clima.repositories.mappers import item_from_row


class ItemsRepository(Repository[Item]):
    def findById(self, id: int) -> Item | None:
        rows = self.db.query("SELECT * FROM items WHERE id=?", (id,))
        return item_from_row(rows[0]) if rows else None

    def findByIds(self, ids: list[int]) -> list[Item]:
        if not ids:
            return []
        placeholders = ",".join("?" for _ in ids)
        rows = self.db.query(f"SELECT * FROM items WHERE id IN ({placeholders})", tuple(ids))
        indexed = {row["id"]: item_from_row(row) for row in rows}
        return [indexed[item_id] for item_id in ids if item_id in indexed]

    def findByUser(self, userId: int) -> list[Item]:
        rows = self.db.query(
            "SELECT * FROM items WHERE user_id=? AND deleted=0 ORDER BY created_at DESC",
            (userId,),
        )
        return [item_from_row(row) for row in rows]

    def findAvailableByUser(self, userId: int) -> list[Item]:
        rows = self.db.query(
            """SELECT * FROM items WHERE user_id=? AND deleted=0 AND in_laundry=0
               ORDER BY created_at DESC""", (userId,)
        )
        return [item_from_row(row) for row in rows]

    def add(self, entity: Item) -> None:
        cursor = self.db.execute(
            """INSERT INTO items(user_id,created_at,photo,type,color,seasons,min_temperature,
               max_temperature,part,dress_code,style,silhouette,material,in_laundry,deleted)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            self._values(entity),
        )
        entity.id = cursor.lastrowid or 0

    def update(self, entity: Item) -> None:
        cursor = self.db.execute(
            """UPDATE items SET photo=?,type=?,color=?,seasons=?,min_temperature=?,max_temperature=?,
               part=?,dress_code=?,style=?,silhouette=?,material=?,in_laundry=?,deleted=?
               WHERE id=? AND user_id=?""",
            (
                entity.photo, entity.type, entity.color,
                json.dumps([season.value for season in entity.seasons]),
                entity.minTemperature, entity.maxTemperature, entity.part.value, entity.dressCode,
                entity.style, entity.silhouette, entity.material, int(entity.inLaundry),
                int(entity.deleted), entity.id, entity.userId,
            ),
        )
        if cursor.rowcount == 0:
            raise NotFoundError("Вещь не найдена")

    def delete(self, id: int) -> None:
        self.db.execute("UPDATE items SET deleted=1 WHERE id=?", (id,))

    @staticmethod
    def _values(entity: Item) -> tuple:
        return (
            entity.userId, entity.createdAt.isoformat(), entity.photo, entity.type, entity.color,
            json.dumps([season.value for season in entity.seasons]), entity.minTemperature,
            entity.maxTemperature, entity.part.value, entity.dressCode, entity.style,
            entity.silhouette, entity.material, int(entity.inLaundry), int(entity.deleted),
        )
