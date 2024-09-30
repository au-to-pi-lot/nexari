from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from src.db.models.guild import Guild, GuildCreate, GuildUpdate
from src.db.models.llm import LLM

class GuildService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_guild(self, guild_id: int) -> Optional[Guild]:
        return await self.session.get(Guild, guild_id)

    async def create_guild(self, guild_data: GuildCreate) -> Guild:
        guild = Guild(**guild_data.dict())
        self.session.add(guild)
        await self.session.commit()
        return guild

    async def update_guild(self, guild: Guild, update_data: GuildUpdate) -> Guild:
        for key, value in update_data.dict(exclude_unset=True).items():
            setattr(guild, key, value)
        await self.session.commit()
        return guild

    async def delete_guild(self, guild: Guild) -> None:
        await self.session.delete(guild)
        await self.session.commit()

    async def get_all_guilds(self) -> List[Guild]:
        result = await self.session.execute(select(Guild))
        return result.scalars().all()

    async def get_llms_for_guild(self, guild_id: int) -> List[LLM]:
        result = await self.session.execute(select(LLM).where(LLM.guild_id == guild_id))
        return result.scalars().all()

    async def set_simulator(self, guild: Guild, simulator_id: int) -> Guild:
        guild.simulator_id = simulator_id
        await self.session.commit()
        return guild

    async def set_simulator_channel(self, guild: Guild, channel_id: int) -> Guild:
        guild.simulator_channel_id = channel_id
        await self.session.commit()
        return guild
