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

    llms: Mapped[List["LLM"]] = relationship(back_populates="guild")