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
    top_p: Mapped[Optional[float]]
    top_k: Mapped[Optional[int]]
    frequency_penalty: Mapped[Optional[float]]
    presence_penalty: Mapped[Optional[float]]
    repetition_penalty: Mapped[Optional[float]]
    min_p: Mapped[Optional[float]]
    top_a: Mapped[Optional[float]]

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
