from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel
from sqlalchemy import ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.models import Base
from src.db.models.message import Message

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook
    from src.db.models.guild import Guild
    from src.db.models.llm import LLM


class ChannelCreate(BaseModel):
    """Pydantic model for creating a new Channel.

    Attributes:
        id (int): The unique identifier for the channel.
        guild_id (int): The ID of the guild the channel belongs to.
    """

    id: int
    guild_id: int
    name: str


class ChannelUpdate(BaseModel):
    """Pydantic model for updating an existing Channel."""
    name: Optional[str]


class Channel(Base):
    """SQLAlchemy model representing a Discord channel.

    Attributes:
        id (int): The unique identifier for the channel.
        guild_id (int): The ID of the guild the channel belongs to.
        last_responder_id (Optional[int]): The ID of the last LLM that responded in this channel.
        guild (Guild): The Guild object this channel belongs to.
        webhooks (List[Webhook]): List of Webhook objects associated with this channel.
        last_responder (Optional[LLM]): The last LLM that responded in this channel.
    """

    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guild.id"))
    name: Mapped[str] = mapped_column()
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("channel.id"))

    guild: Mapped["Guild"] = relationship(back_populates="channels", foreign_keys=[guild_id])
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel")
    messages: Mapped[List[Message]] = relationship(back_populates="channel")
    parent: Mapped[Optional["Channel"]] = relationship()
