from typing import List, TYPE_CHECKING, Union

import discord
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.channel import Channel
    from src.db.models.llm import LLM


class GuildCreate(BaseModel):
    """
    Pydantic model for creating a new Guild.

    Attributes:
        id (int): The unique identifier for the guild.
    """
    id: int


class GuildUpdate(BaseModel):
    """
    Pydantic model for updating an existing Guild.
    Currently empty as there are no updatable fields.
    """
    pass


class Guild(Base[GuildCreate, GuildUpdate]):
    """
    SQLAlchemy model representing a Discord guild.

    Attributes:
        id (int): The unique identifier for the guild.
        channels (List[Channel]): List of Channel objects associated with this guild.
        llms (List[LLM]): List of LLM objects associated with this guild.
    """
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)

    channels: Mapped[List["Channel"]] = relationship(back_populates="guild")
    llms: Mapped[List["LLM"]] = relationship(back_populates="guild")

    @staticmethod
    def get_guild_id(guild: Union[discord.Guild, "Guild", int]) -> int:
        """
        Get the guild ID from various guild representations.

        Args:
            guild (Union[discord.Guild, Guild, int]): The guild object or ID.

        Returns:
            int: The guild ID.

        Raises:
            ValueError: If an invalid guild type is provided.
        """
        if isinstance(guild, (discord.Guild, Guild)):
            return guild.id
        elif isinstance(guild, int):
            return guild
        else:
            raise ValueError(
                "Invalid guild type. Expected discord.Guild, Guild, or int."
            )
