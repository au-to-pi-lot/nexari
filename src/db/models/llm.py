from typing import List, Optional, TYPE_CHECKING
from pydantic import BaseModel, Field
from sqlalchemy import Text, select, UniqueConstraint, ForeignKey
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from src.db.engine import Session
from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook
    from src.db.models.guild import Guild

class LLMCreate(BaseModel):
    name: str
    guild_id: int
    api_base: str
    llm_name: str
    api_key: str
    max_tokens: int
    system_prompt: Optional[str]
    context_length: int
    message_limit: int
    temperature: float = Field(default=1.0)
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None
    top_a: Optional[float] = None

class LLMUpdate(BaseModel):
    name: Optional[str] = None
    guild_id: Optional[int] = None
    api_base: Optional[str] = None
    llm_name: Optional[str] = None
    api_key: Optional[str] = None
    max_tokens: Optional[int] = None
    system_prompt: Optional[str] = None
    context_length: Optional[int] = None
    message_limit: Optional[int] = None
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None
    frequency_penalty: Optional[float] = None
    presence_penalty: Optional[float] = None
    repetition_penalty: Optional[float] = None
    min_p: Optional[float] = None
    top_a: Optional[float] = None

class LLM(Base[LLMCreate, LLMUpdate]):
    __tablename__ = 'llm'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, index=True)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id"), nullable=False)
    api_base: Mapped[str] = mapped_column(Text)
    llm_name: Mapped[str] = mapped_column(Text)
    api_key: Mapped[str] = mapped_column(Text)
    max_tokens: Mapped[int]
    system_prompt: Mapped[Optional[str]] = mapped_column(Text)
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

    guild: Mapped["Guild"] = relationship(back_populates="llms")
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="llm")

    __table_args__ = (UniqueConstraint('name', 'guild_id', name='uq_name_guild_id'),)

    # ... (keep all the existing validators)

    @classmethod
    async def get_by_name(cls, name: str, guild_id: int, *, session: Optional[Session] = None) -> Optional["LLM"]:
        async def _get_by_name(s):
            try:
                result = await s.execute(select(cls).filter(cls.name == name, cls.guild_id == guild_id))
                return result.scalar_one_or_none()
            except SQLAlchemyError as e:
                # Log the error here
                raise

        if session:
            return await _get_by_name(session)
        else:
            async with Session() as new_session:
                return await _get_by_name(new_session)
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.models import Base

class GuildCreate(BaseModel):
    id: int
    name: str

class GuildUpdate(BaseModel):
    name: Optional[str] = None

class Guild(Base[GuildCreate, GuildUpdate]):
    __tablename__ = "guild"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(nullable=False)

    channels: Mapped[List["Channel"]] = relationship(back_populates="guild")
    llms: Mapped[List["LLM"]] = relationship(back_populates="guild")
