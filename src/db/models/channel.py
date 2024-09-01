from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook
    from src.db.models.guild import Guild


class ChannelCreate(BaseModel):
    """Pydantic model for creating a new Channel.

    Attributes:
        id (int): The unique identifier for the channel.
        guild_id (int): The ID of the guild the channel belongs to.
    """
    id: int
    guild_id: int


class ChannelUpdate(BaseModel):
    """Pydantic model for updating an existing Channel.

    Attributes:
        guild_id (Optional[int]): The new guild ID for the channel, if changing.
    """
    guild_id: Optional[int] = None


class Channel(Base[ChannelCreate, ChannelUpdate]):
    """SQLAlchemy model representing a Discord channel.

    Attributes:
        id (int): The unique identifier for the channel.
        guild_id (int): The ID of the guild the channel belongs to.
        guild (Guild): The Guild object this channel belongs to.
        webhooks (List[Webhook]): List of Webhook objects associated with this channel.
    """
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id"), nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="channels")
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel")
