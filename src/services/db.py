from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine, async_sessionmaker
from src.config import config
from src.services import registry


registry.register_factory(
    svc_type=AsyncEngine,
    factory=lambda: create_async_engine(config.database_url)
)

registry.register_factory(
    svc_type=type[AsyncSession],
    factory=lambda svcs_container: async_sessionmaker(svcs_container.get(AsyncEngine))
)
