from psycopg.types.json import Jsonb

from clima.errors import NotFoundError
from clima.models.entities import Item
from clima.repositories.base import Repository
from clima.repositories.mappers import item_from_row


class ItemsRepository(Repository[Item]):
    def findById(self, id: int) -> Item | None:
        rows = self.db.query("SELECT * FROM items WHERE id=%s", (id,))
        return item_from_row(rows[0]) if rows else None

    def findByIds(self, ids: list[int]) -> list[Item]:
        if not ids:
            return []
        rows = self.db.query("SELECT * FROM items WHERE id = ANY(%s)", (list(ids),))
        indexed = {row["id"]: item_from_row(row) for row in rows}
        return [indexed[item_id] for item_id in ids if item_id in indexed]

    def findByUser(self, userId: int) -> list[Item]:
        rows = self.db.query(
            "SELECT * FROM items WHERE user_id=%s AND NOT deleted ORDER BY created_at DESC, id DESC",
            (userId,),
        )
        return [item_from_row(row) for row in rows]

    def findAvailableByUser(self, userId: int) -> list[Item]:
        rows = self.db.query(
            """SELECT * FROM items WHERE user_id=%s AND NOT deleted AND NOT in_laundry
               ORDER BY created_at DESC, id DESC""", (userId,)
        )
        return [item_from_row(row) for row in rows]

    def add(self, entity: Item) -> None:
        entity.id = self.db.insert(
            """INSERT INTO items(user_id,created_at,photo,type,color,seasons,min_temperature,
               max_temperature,part,dress_code,style,silhouette,material,in_laundry,deleted)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            (
                entity.userId, entity.createdAt, entity.photo, entity.type, entity.color,
                Jsonb([season.value for season in entity.seasons]), entity.minTemperature,
                entity.maxTemperature, entity.part.value, entity.dressCode, entity.style,
                entity.silhouette, entity.material, entity.inLaundry, entity.deleted,
            ),
        )

    def update(self, entity: Item) -> None:
        result = self.db.execute(
            """UPDATE items SET photo=%s,type=%s,color=%s,seasons=%s,min_temperature=%s,
               max_temperature=%s,part=%s,dress_code=%s,style=%s,silhouette=%s,material=%s,
               in_laundry=%s,deleted=%s WHERE id=%s AND user_id=%s""",
            (
                entity.photo, entity.type, entity.color,
                Jsonb([season.value for season in entity.seasons]),
                entity.minTemperature, entity.maxTemperature, entity.part.value, entity.dressCode,
                entity.style, entity.silhouette, entity.material, entity.inLaundry,
                entity.deleted, entity.id, entity.userId,
            ),
        )
        if result.rowcount == 0:
            raise NotFoundError("Вещь не найдена")

    def delete(self, id: int) -> None:
        self.db.execute("UPDATE items SET deleted=TRUE WHERE id=%s", (id,))
