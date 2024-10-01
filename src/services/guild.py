from typing import Optional, List

import discord
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from src.db.models.guild import Guild, GuildUpdate
from src.db.models.llm import LLM


class GuildService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, guild_id: int) -> Optional[Guild]:
        return await self.session.get(Guild, guild_id)

    async def create(self, guild: discord.Guild) -> Guild:
        db_guild = Guild(
            id=guild.id,
            name=guild.name,
            simulator_id=None,
            simulator_channel_id=None
        )
        self.session.add(db_guild)
        await self.session.commit()
        return db_guild

    async def get_or_create(self, guild: discord.Guild) -> Guild:
        db_guild = await self.get(guild.id)
        if db_guild is None:
            db_guild = await self.create(guild)

        return db_guild

    async def update(self, guild: Guild, update_data: GuildUpdate) -> Guild:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(guild, key, value)
        await self.session.commit()
        return guild

    async def delete(self, guild: Guild) -> None:
        await self.session.delete(guild)
        await self.session.commit()

    async def get_all(self) -> List[Guild]:
        result = await self.session.execute(select(Guild))
        return list(result.scalars().all())

    async def get_llms_by_guild(self, guild_id: int) -> List[LLM]:
        result = await self.session.execute(select(LLM).where(LLM.guild_id == guild_id))
        return list(result.scalars().all())

    async def sync(self, discord_guild: discord.Guild) -> Guild:
        """
        Synchronize the database guild with the Discord guild.

        Args:
            discord_guild (discord.Guild): The Discord guild to sync with.

        Returns:
            Guild: The updated database Guild object.
        """
        db_guild = await self.get(discord_guild.id)
        if db_guild is None:
            db_guild = await self.create(discord_guild)
        else:
            # Update guild properties
            db_guild.name = discord_guild.name

            await self.session.commit()

        return db_guild
