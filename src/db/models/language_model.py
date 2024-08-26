from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook


class LanguageModel(Base):
    __tablename__ = 'language_model'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True, index=True)
    api_base: Mapped[str] = mapped_column(Text)
    model_name: Mapped[str] = mapped_column(Text)
    api_key: Mapped[str] = mapped_column(Text)
    max_tokens: Mapped[int]
    system_prompt: Mapped[str] = mapped_column(Text)
    context_length: Mapped[int]
    message_limit: Mapped[int]

    temperature: Mapped[float] = mapped_column(nullable=False, default=1.0)
    top_p: Mapped[Optional[float]]
    top_k: Mapped[Optional[int]]
    frequency_penalty: Mapped[Optional[float]]
    presence_penalty: Mapped[Optional[float]]
    repetition_penalty: Mapped[Optional[float]]
    min_p: Mapped[Optional[float]]
    top_a: Mapped[Optional[float]]

    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="language_model")

    @validates('temperature')
    def validate_temperature(self, key, temperature: float) -> float:
        if not 0.0 <= temperature <= 2.0:
            raise ValueError(f'`temperature` out of range: {temperature}. Value must be between 0.0 and 2.0 inclusive.')
        return temperature

    @validates('top_p')
    def validate_top_p(self, key, top_p: Optional[float]) -> Optional[float]:
        if top_p is not None and not 0.0 <= top_p <= 1.0:
            raise ValueError(f'`top_p` out of range: {top_p}. Value must be between 0.0 and 1.0 inclusive.')
        return top_p

    @validates('top_k')
    def validate_top_k(self, key, top_k: Optional[int]) -> Optional[int]:
        if top_k is not None and top_k < 0:
            raise ValueError(f'`top_k` must be non-negative: {top_k}.')
        return top_k

    @validates('frequency_penalty', 'presence_penalty')
    def validate_penalty(self, key, value: Optional[float]) -> Optional[float]:
        if value is not None and not -2.0 <= value <= 2.0:
            raise ValueError(f'`{key}` out of range: {value}. Value must be between -2.0 and 2.0 inclusive.')
        return value

    @validates('repetition_penalty')
    def validate_repetition_penalty(self, key, value: Optional[float]) -> Optional[float]:
        if value is not None and value < 0.0:
            raise ValueError(f'`repetition_penalty` must be non-negative: {value}.')
        return value

    @validates('min_p')
    def validate_min_p(self, key, min_p: Optional[float]) -> Optional[float]:
        if min_p is not None and not 0.0 <= min_p <= 1.0:
            raise ValueError(f'`min_p` out of range: {min_p}. Value must be between 0.0 and 1.0 inclusive.')
        return min_p

    @validates('top_a')
    def validate_top_a(self, key, top_a: Optional[float]) -> Optional[float]:
        if top_a is not None and top_a < 0.0:
            raise ValueError(f'`top_a` must be non-negative: {top_a}.')
        return top_a
