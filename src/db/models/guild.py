from typing import List, TYPE_CHECKING, Union

import discord
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.channel import Channel
    from src.db.models.llm import LLM


class GuildCreate(BaseModel):
    id: int


class GuildUpdate(BaseModel):
    pass


class Guild(Base[GuildCreate, GuildUpdate]):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

    channels: Mapped[List["Channel"]] = relationship(back_populates="guild")
    llms: Mapped[List["LLM"]] = relationship(back_populates="guild")

    @staticmethod
    def get_guild_id(guild: Union[discord.Guild, "Guild", int]) -> int:
        if isinstance(guild, (discord.Guild, Guild)):
            return guild.id
        elif isinstance(guild, int):
            return guild
        else:
            raise ValueError("Invalid guild type. Expected discord.Guild, Guild, or int.")

