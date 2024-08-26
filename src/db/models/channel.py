from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel")
    language_models: Mapped[List["LanguageModel"]] = relationship(
        secondary="webhook",
        back_populates="channels",
        primaryjoin="Channel.id == Webhook.channel_id",
        secondaryjoin="Webhook.language_model_id == LanguageModel.id"
    )