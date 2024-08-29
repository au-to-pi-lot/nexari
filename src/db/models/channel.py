from typing import List, TYPE_CHECKING
from pydantic import BaseModel

from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base, CreateSchemaType, UpdateSchemaType

if TYPE_CHECKING:
    from src.db.models.webhook import Webhook


class ChannelCreate(BaseModel):
    id: int

class ChannelUpdate(BaseModel):
    pass

class Channel(Base[ChannelCreate, ChannelUpdate]):
    __tablename__ = "channel"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=False)
    webhooks: Mapped[List["Webhook"]] = relationship(back_populates="channel", overlaps="language_models")
