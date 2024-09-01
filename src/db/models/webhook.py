from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel
from sqlalchemy import ForeignKey, Text, UniqueConstraint, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.engine import Session
from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.channel import Channel
    from src.db.models.llm import LLM


class WebhookCreate(BaseModel):
    id: int
    token: str
    channel_id: int
    language_model_id: int


class WebhookUpdate(BaseModel):
    token: Optional[str] = None
    channel_id: Optional[int] = None
    language_model_id: Optional[int] = None


class Webhook(Base[WebhookCreate, WebhookUpdate]):
    __tablename__ = "webhook"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    channel_id: Mapped[int] = mapped_column(ForeignKey("channel.id"), nullable=False)
    llm_id: Mapped[int] = mapped_column(ForeignKey("llm.id"), nullable=False)

    channel: Mapped["Channel"] = relationship(back_populates="webhooks")
    llm: Mapped["LLM"] = relationship(back_populates="webhooks")

    unique_channel_model = UniqueConstraint("channel_id", "llm_id")

    @classmethod
    async def get_by_language_model_id(
        cls, language_model_id: int, *, session: Optional[Session] = None
    ) -> List["Webhook"]:
        async def _get_by_language_model_id(s: Session):
            try:
                result = await s.execute(
                    select(cls).filter(cls.language_model_id == language_model_id)
                )
                return result.scalars().all()
            except SQLAlchemyError as e:
                # Log the error here
                raise

        if session:
            return await _get_by_language_model_id(session)
        else:
            async with Session() as new_session:
                return await _get_by_language_model_id(new_session)
