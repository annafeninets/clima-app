from clima.errors import NotFoundError
from clima.models.entities import Favorite
from clima.repositories.base import Repository
from clima.repositories.mappers import datetime_from_db


class FavoritesRepository(Repository[Favorite]):
    def findById(self, id: int) -> Favorite | None:
        rows = self.db.query("SELECT * FROM favorites WHERE id=%s", (id,))
        return self._favorite(rows[0]) if rows else None

    def findByUser(self, userId: int) -> list[Favorite]:
        rows = self.db.query(
            "SELECT * FROM favorites WHERE user_id=%s ORDER BY created_at DESC, id DESC", (userId,)
        )
        return [self._favorite(row) for row in rows]

    def exists(self, userId: int, outfitId: int) -> bool:
        return bool(self.db.query(
            "SELECT 1 FROM favorites WHERE user_id=%s AND outfit_id=%s", (userId, outfitId)
        ))

    def add(self, entity: Favorite) -> None:
        entity.id = self.db.insert(
            "INSERT INTO favorites(user_id,outfit_id,created_at) VALUES(%s,%s,%s) RETURNING id",
            (entity.userId, entity.outfitId, entity.createdAt),
        )

    def update(self, entity: Favorite) -> None:
        result = self.db.execute(
            "UPDATE favorites SET outfit_id=%s WHERE id=%s AND user_id=%s",
            (entity.outfitId, entity.id, entity.userId),
        )
        if result.rowcount == 0:
            raise NotFoundError("Избранное не найдено")

    def delete(self, id: int) -> None:
        self.db.execute("DELETE FROM favorites WHERE id=%s", (id,))

    @staticmethod
    def _favorite(row) -> Favorite:
        return Favorite(
            id=row["id"], userId=row["user_id"], outfitId=row["outfit_id"],
            createdAt=datetime_from_db(row["created_at"]),
        )
