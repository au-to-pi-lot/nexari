from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from src.config import config

engine = create_async_engine(config.database_url)
Session = async_sessionmaker(engine)
