from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Self, TypeVar

DiscordObj = TypeVar("DiscordObj")
DBObj = TypeVar("DBObj")


class BaseProxy(ABC, Generic[DiscordObj, DBObj]):
    def __init__(self, discord_obj: DiscordObj, db_obj: DBObj) -> None:
        self._discord_obj: DiscordObj = discord_obj
        self._db_obj: DBObj = db_obj

    @classmethod
    @abstractmethod
    async def get(cls, identifier: Any) -> Optional[Self]:
        pass

    @abstractmethod
    async def save(self) -> None:
        pass
