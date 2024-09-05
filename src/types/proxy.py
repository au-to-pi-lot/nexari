from abc import ABC, abstractmethod
from typing import Any, Generic, Optional, Self, TypeVar

DiscordObj = TypeVar("DiscordObj")
DBObj = TypeVar("DBObj")


class BaseProxy(ABC, Generic[DiscordObj, DBObj]):
    def __init__(self, discord_obj: DiscordObj, db_obj: DBObj) -> None:
        self._discord_obj: DiscordObj = discord_obj
        self._db_obj: DBObj = db_obj

    def __getattr__(self, name: str):
        if name in self._db_obj.__table__.columns.keys():
            return getattr(self._db_obj, name)
        return getattr(self._discord_obj, name)

    @classmethod
    @abstractmethod
    async def get(cls, identifier: Any) -> Optional[Self]:
        pass

    @abstractmethod
    async def save(self) -> None:
        pass
