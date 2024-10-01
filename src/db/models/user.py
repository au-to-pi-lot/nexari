from typing import TYPE_CHECKING, List, Optional
from pydantic import BaseModel
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models import Base

if TYPE_CHECKING:
    from src.db.models.message import Message


class UserCreate(BaseModel):
    """
    Pydantic model for creating a new User.

    Attributes:
        id (int): The unique identifier for the user.
        name (str): The name of the user.
        discriminator (str): The discriminator of the user.
    """

    id: int
    name: str


class UserUpdate(BaseModel):
    """
    Pydantic model for updating an existing User.

    Attributes:
        name (Optional[str]): The new name for the user.
        discriminator (Optional[str]): The new discriminator for the user.
    """

    name: Optional[str] = None


class User(Base):
    """
    SQLAlchemy model representing a Discord user.

    Attributes:
        id (int): The unique identifier for the user.
        name (str): The name of the user.
        discriminator (str): The discriminator of the user.
        messages (List[Message]): List of Message objects associated with this user.
    """

    __tablename__ = "user"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(nullable=False)

    messages: Mapped[List["Message"]] = relationship(back_populates="user")
