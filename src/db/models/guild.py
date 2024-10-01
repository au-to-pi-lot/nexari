from typing import List, TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlalchemy import BigInteger, ForeignKey
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
    simulator_id: Optional[int] = None
    simulator_channel_id: Optional[int] = None


class GuildUpdate(BaseModel):
    """
    Pydantic model for updating an existing Guild.
    """

    simulator_id: Optional[int] = None
    simulator_channel_id: Optional[int] = None


class Guild(Base):
    """
    SQLAlchemy model representing a Discord guild.

    Attributes:
        id (int): The unique identifier for the guild.
        channels (List[Channel]): List of Channel objects associated with this guild.
        llms (List[LLM]): List of LLM objects associated with this guild.
        simulator_channel_id (Optional[int]): ID of the channel for simulator responses.
    """

    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[Optional[str]] = mapped_column()
    simulator_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("llm.id", use_alter=True)
    )
    simulator_channel_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("channel.id", use_alter=True), nullable=True
    )

    channels: Mapped[List["Channel"]] = relationship(
        back_populates="guild",
        foreign_keys="Channel.guild_id",
    )
    llms: Mapped[List["LLM"]] = relationship(
        back_populates="guild",
        foreign_keys="LLM.guild_id",
    )
