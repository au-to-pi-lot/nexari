from typing import List, TYPE_CHECKING
from pydantic import BaseModel
from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook
    from src.db.models.guild import Guild

class ChannelCreate(BaseModel):
    id: int
    guild_id: int

class ChannelUpdate(BaseModel):
    guild_id: Optional[int] = None

class Channel(Base[ChannelCreate, ChannelUpdate]):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    guild_id: Mapped[int] = mapped_column(ForeignKey("guild.id"), nullable=False)

    guild: Mapped["Guild"] = relationship(back_populates="channels")
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel")
