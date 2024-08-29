from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, Text, UniqueConstraint, select
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.exc import SQLAlchemyError

from src.db.models import Base
from src.db.engine import Session

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

    @classmethod
    async def get_by_language_model_id(cls, language_model_id: int, *, session: Optional[Session] = None) -> List["Webhook"]:
        async def _get_by_language_model_id(s):
            try:
                result = await s.execute(select(cls).filter(cls.language_model_id == language_model_id))
                return result.scalars().all()
            except SQLAlchemyError as e:
                # Log the error here
                raise

        if session:
            return await _get_by_language_model_id(session)
        else:
            async with Session() as new_session:
                return await _get_by_language_model_id(new_session)
