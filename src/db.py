from typing import Optional, Tuple

from sqlalchemy import create_engine, Column, Integer, Text, ForeignKey, UniqueConstraint, \
    Float, CheckConstraint
from sqlalchemy.orm import sessionmaker, Mapped, mapped_column, DeclarativeBase, validates


class Base(DeclarativeBase):
    pass


class LanguageModel(Base):
    __tablename__ = 'language_model'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False, unique=True)

class SamplingConfig(Base):
    __tablename__ = 'sampling_config'

    id: Mapped[int] = mapped_column(primary_key=True)
    temperature: Mapped[float] = mapped_column(nullable=False)

    @validates('temperature')
    def validate_temperature(self, temperature: float) -> float:
        temp_min = 0.0
        temp_max = 2.0
        if not temp_min <= temperature <= temp_max:
            raise ValueError(f'`temperature` out of range: {temperature}. Value must be between {temp_min} and {temp_max} inclusive.')
        return temperature

    top_p: Mapped[float]

    @validates('top_p')
    def validate_top_p(self, top_p: Optional[float]) -> Optional[float]:
        top_p_min = 0.0
        top_p_max = 1.0
        if top_p is not None and not top_p_min <= top_p <= top_p_max:
            raise ValueError(
                f'`top_p` out of range: {top_p}. Value must be between {top_p_min} and {top_p_max} inclusive.')
        return top_p

    top_k: Mapped[float]
    frequency_penalty: Mapped[float]
    presence_penalty: Mapped[float]
    repetition_penalty: Mapped[float]
    min_p: Mapped[float]
    top_a: Mapped[float]


class Channel(Base):
    __tablename__ = "channel"

    id = Column(Integer, primary_key=True)


class Webhook(Base):
    __tablename__ = 'webhooks'

    id = Column(Integer, primary_key=True)
    token = Column(Text, nullable=False)
    channel_id = Column(Integer, ForeignKey('channel.id'), nullable=False)
    language_model = Column(Integer, ForeignKey('language_model.id'), nullable=False)

    unique_channel_model = UniqueConstraint("channel_id", "language_model")

class WebhookDB:
    def __init__(self, db_name: str = 'webhooks.db'):
        self.engine = create_engine(f'sqlite:///{db_name}')
        self.Session = sessionmaker(bind=self.engine)

    def init_db(self):
        Base.metadata.create_all(self.engine)

    def get_webhook_info(self, name: str) -> Optional[Tuple[int, str]]:
        with self.Session() as session:
            webhook = session.query(Webhook).filter_by(name=name).first()
            if webhook:
                return webhook.webhook_id, webhook.webhook_token
        return None

    def save_webhook_info(self, name: str, webhook_id: int, webhook_token: str):
        with self.Session() as session:
            webhook = Webhook(name=name, webhook_id=webhook_id, webhook_token=webhook_token)
            session.merge(webhook)
            session.commit()

# Create a global instance of WebhookDB
webhook_db = WebhookDB()
