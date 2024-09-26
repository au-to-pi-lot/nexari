from typing import Optional, Self

import discord
from discord.ext.commands import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.user import User as DBUser
from src.services.db import Session
from src.services.discord_client import bot
from src.types.proxy import BaseProxy


class UserProxy(BaseProxy[discord.User, DBUser]):
    def __init__(self, discord_user: discord.User, db_user: DBUser):
        super().__init__(discord_user, db_user)

    @classmethod
    async def get(cls, identifier: int) -> Optional[Self]:
        discord_user = await bot.fetch_user(identifier)
        if not discord_user:
            return None

        async with Session() as session:
            db_user = await session.get(DBUser, identifier)
            if not db_user:
                db_user = DBUser(
                    id=identifier,
                    name=discord_user.name,
                    discriminator=discord_user.discriminator
                )
                session.add(db_user)
                try:
                    await session.commit()
                except sqlalchemy.exc.IntegrityError:
                    await session.rollback()
                    logger.error(f"Failed to create user {identifier} due to integrity error")
                    return None

        return cls(discord_user, db_user)

    async def save(self):
        async with Session() as session:
            session.add(self._db_obj)
            await session.commit()

    @property
    def id(self) -> int:
        return self._discord_obj.id

    @property
    def name(self) -> str:
        return self._discord_obj.name

    @property
    def discriminator(self) -> str:
        return self._discord_obj.discriminator

    @property
    def display_name(self) -> str:
        return self._discord_obj.display_name

    @property
    def avatar_url(self) -> str:
        return str(self._discord_obj.avatar.url) if self._discord_obj.avatar else None

    async def send(self, content: str = None, **kwargs) -> discord.Message:
        return await self._discord_obj.send(content, **kwargs)

    async def edit(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self._db_obj, key):
                setattr(self._db_obj, key, value)
        await self.save()
