from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import BaseModel
from sqlalchemy import BigInteger, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.channel import Channel
    from src.db.models.guild import Guild


class MessageCreate(BaseModel):
    """
    Pydantic model for creating a new Message.

    Attributes:
        id (int): The unique identifier for the message.
        content (str): The content of the message.
        author_id (int): The ID of the user who authored the message.
        channel_id (int): The ID of the channel the message belongs to.
        guild_id (int): The ID of the guild the message belongs to.
        created_at (datetime): The timestamp when the message was created.
    """
    id: int
    content: str
    author_id: int
    channel_id: int
    guild_id: int
    created_at: datetime


class MessageUpdate(BaseModel):
    """
    Pydantic model for updating an existing Message.

    Attributes:
        content (Optional[str]): The new content for the message.
    """
    content: Optional[str] = None


class Message(Base):
    """
    SQLAlchemy model representing a Discord message.

    Attributes:
        id (int): The unique identifier for the message.
        content (str): The content of the message.
        author_id (int): The ID of the user who authored the message.
        channel_id (int): The ID of the channel the message belongs to.
        guild_id (int): The ID of the guild the message belongs to.
        created_at (datetime): The timestamp when the message was created.
        author (User): The User object who authored this message.
        channel (Channel): The Channel object this message belongs to.
        guild (Guild): The Guild object this message belongs to.
    """
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    author_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channels.id"), nullable=False)
    guild_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("guilds.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    author: Mapped["User"] = relationship(back_populates="messages")
    channel: Mapped["Channel"] = relationship(back_populates="messages")
    guild: Mapped["Guild"] = relationship(back_populates="messages")
