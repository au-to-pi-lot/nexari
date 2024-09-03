from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from src.db.models.guild import Guild
from src.db.models.channel import Channel
from src.db.models.llm import LLM
from src.db.models.webhook import Webhook

metadata = Base.metadata
