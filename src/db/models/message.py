from datetime import datetime
from typing import TYPE_CHECKING, Optional
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import BigInteger, ForeignKey, Text, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.channel import Channel
    from src.db.models.webhook import Webhook


class MessageCreate(BaseModel):
    """
    Pydantic model for creating a new Message.

    Attributes:
        id (int): The unique identifier for the message.
        content (str): The content of the message.
        user_id (Optional[int]): The ID of the user who authored the message.
        webhook_id (Optional[int]): The ID of the webhook that sent the message.
        channel_id (int): The ID of the channel the message belongs to.
        created_at (datetime): The timestamp when the message was created.
    """
    id: int
    content: str
    user_id: Optional[int]
    webhook_id: Optional[int]
    channel_id: int
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
        user_id (Optional[int]): The ID of the user who authored the message.
        webhook_id (Optional[int]): The ID of the webhook that sent the message.
        channel_id (int): The ID of the channel the message belongs to.
        created_at (datetime): The timestamp when the message was created.
        user (Optional[User]): The User object who authored this message.
        webhook (Optional[Webhook]): The Webhook object that sent this message.
        channel (Channel): The Channel object this message belongs to.
    """
    __tablename__ = "message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"), nullable=True)
    webhook_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("webhook.id"), nullable=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channel.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False)

    user: Mapped[Optional["User"]] = relationship(back_populates="messages")
    webhook: Mapped[Optional["Webhook"]] = relationship(back_populates="messages")
    channel: Mapped["Channel"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint('(user_id IS NULL) != (webhook_id IS NULL)',
                        name='user_xor_webhook'),
    )
