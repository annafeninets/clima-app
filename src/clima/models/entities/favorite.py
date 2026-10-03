from dataclasses import dataclass

from clima.models.entities.base import OwnedEntity


@dataclass(slots=True)
class Favorite(OwnedEntity):
    outfitId: int = 0
