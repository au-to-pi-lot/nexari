from typing import Optional, TYPE_CHECKING

from pydantic import BaseModel
from sqlalchemy import ForeignKey, Text, UniqueConstraint, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.channel import Channel
    from src.db.models.llm import LLM
    from src.db.models.message import Message


class WebhookCreate(BaseModel):
    """
    Pydantic model for creating a new Webhook.

    Attributes:
        id (int): The unique identifier for the webhook.
        token (str): The token for the webhook.
        channel_id (int): The ID of the channel the webhook belongs to.
        language_model_id (int): The ID of the language model associated with the webhook.
    """

    id: int
    token: str
    channel_id: int
    language_model_id: int


class WebhookUpdate(BaseModel):
    """
    Pydantic model for updating an existing Webhook.

    Attributes:
        token (Optional[str]): The new token for the webhook.
        channel_id (Optional[int]): The new channel ID for the webhook.
        language_model_id (Optional[int]): The new language model ID for the webhook.
    """

    token: Optional[str] = None
    channel_id: Optional[int] = None
    language_model_id: Optional[int] = None


class Webhook(Base):
    """
    SQLAlchemy model representing a Discord webhook.

    Attributes:
        id (int): The unique identifier for the webhook.
        token (str): The token for the webhook.
        channel_id (int): The ID of the channel the webhook belongs to.
        llm_id (int): The ID of the language model associated with the webhook.
        channel (Channel): The Channel object this webhook belongs to.
        llm (LLM): The LLM object associated with this webhook.
    """

    __tablename__ = "webhook"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[Optional[str]] = mapped_column(Text)
    token: Mapped[str] = mapped_column(Text)
    channel_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("channel.id"))
    llm_id: Mapped[int] = mapped_column(ForeignKey("llm.id"))

    channel: Mapped["Channel"] = relationship(back_populates="webhooks")
    llm: Mapped["LLM"] = relationship(back_populates="webhooks")
    messages: Mapped["Message"] = relationship(back_populates="webhook")

    unique_channel_model = UniqueConstraint("channel_id", "llm_id")
