from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship

from src.db.models import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    content = Column(String, nullable=False)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    guild_id = Column(Integer, ForeignKey("guilds.id"), nullable=False)
    created_at = Column(DateTime, nullable=False)

    author = relationship("User", back_populates="messages")
    channel = relationship("Channel", back_populates="messages")
    guild = relationship("Guild", back_populates="messages")
