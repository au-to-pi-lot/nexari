from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from src.config import config

engine: AsyncEngine = create_async_engine(config.database_url)
Session: type[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)
