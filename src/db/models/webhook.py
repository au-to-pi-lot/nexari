from typing import TYPE_CHECKING
from sqlalchemy import ForeignKey, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.channel import Channel
    from src.db.models.language_model import LanguageModel


class Webhook(Base):
    __tablename__ = "webhook"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"), nullable=False)
    language_model_id: Mapped[int] = mapped_column(ForeignKey("language_model.id"), nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="webhooks")
    language_model: Mapped["LanguageModel"] = relationship(back_populates="webhooks")

    unique_channel_model = UniqueConstraint("channel_id", "language_model_id")
