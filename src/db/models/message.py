from datetime import datetime
from typing import TYPE_CHECKING, Optional

import sqlalchemy
from pydantic import BaseModel
from sqlalchemy import BigInteger, ForeignKey, Text, CheckConstraint, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.schema import Index

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.user import User
    from src.db.models.channel import Channel


class MessageCreate(BaseModel):
    """
    Pydantic model for creating a new Message.

    Attributes:
        id (int): The unique identifier for the message.
        content (str): The content of the message.
        user_id (Optional[int]): The ID of the user who authored the message.
        llm_id (Optional[int]): The ID of the LLM that sent the message.
        channel_id (int): The ID of the channel the message belongs to.
        created_at (datetime): The timestamp when the message was created.
    """

    id: int
    content: str
    user_id: Optional[int]
    llm_id: Optional[int]
    channel_id: int
    created_at: datetime
    from_webhook: bool


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
        user_id (Optional[int]): The ID of the user who authored the message, or None if not applicable.
        llm_id (Optional[int]): The ID of the LLM that sent the message, or None if not applicable.
        channel_id (int): The ID of the channel the message belongs to.
        created_at (datetime): The timestamp when the message was created.
        user (Optional[User]): The User object who authored this message, or None if not applicable.
        channel (Channel): The Channel object this message belongs to.

    Note:
        Both user_id and webhook_id can be null if the message is from an uncontrolled webhook.
    """

    __tablename__ = "message"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    content: Mapped[str] = mapped_column(Text)
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("user.id"))
    llm_id: Mapped[Optional[int]] = mapped_column(BigInteger, ForeignKey("llm.id"))
    channel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("channel.id")
    )
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=True))
    from_webhook: Mapped[bool] = mapped_column(server_default=sqlalchemy.sql.false())

    user: Mapped[Optional["User"]] = relationship(back_populates="messages")
    channel: Mapped["Channel"] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            "(user_id IS NULL AND webhook_id IS NULL) OR (user_id IS NOT NULL) != (webhook_id IS NOT NULL)",
            name="user_xor_webhook_or_both_null",
        ),
        Index("channel_message_idx", "channel_id", "created_at"),
    )

    @property
    def is_from_nexari_llm(self) -> bool:
        return self.llm_id is not None

    @property
    def is_from_user(self) -> bool:
        return not self.from_webhook

    @property
    def is_from_foreign_webhook(self) -> bool:
        return self.from_webhook and self.llm_id is None
