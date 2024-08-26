from typing import List

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base


class Channel(Base):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel", overlaps="language_models")