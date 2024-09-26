import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import MetaData, Table, select, insert

# Adjust these imports to match your project structure
from src.db.models import Base

# Connection strings
SQLITE_URL = "sqlite+aiosqlite:///data.db"
POSTGRES_URL = "postgresql+asyncpg://nexari:Uf1BVvenzrhcwfmNRpxBQwMlL5YcpOKfprXXki5yGf9HwNXLAIExEm4xy33yRgxH@localhost:5432/nexari_db"

# Create engines
sqlite_engine = create_async_engine(SQLITE_URL)
postgres_engine = create_async_engine(POSTGRES_URL)


async def transfer_data():
    metadata = Base.metadata

    # Create tables in PostgreSQL
    async with postgres_engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

        # Create sessions
    SQLiteSession = async_sessionmaker(bind=sqlite_engine)
    PostgresSession = async_sessionmaker(bind=postgres_engine, class_=AsyncSession)

    sqlite_session = SQLiteSession()
    postgres_session = PostgresSession()

    # Transfer data for each table
    for table_name in metadata.tables:
        print(f"Transferring data for table: {table_name}")

        # Get the table objects
        sqlite_table = await sqlite_session.run_sync(lambda sqlite_session_sync: Table(table_name, metadata, autoload_with=sqlite_session_sync))
        postgres_table = await postgres_session.run_sync(lambda postgres_session_sync: Table(table_name, metadata, autoload_with=postgres_session_sync))

        # Fetch all data from SQLite
        sqlite_data = (await sqlite_session.execute(select(sqlite_table))).fetchall()

        # Insert data into PostgreSQL
        if sqlite_data:
            async with postgres_session.begin():
                await postgres_session.execute(insert(postgres_table), list(map(lambda row: row._mapping, sqlite_data)))

                # Close sessions
    await sqlite_session.close()
    await postgres_session.close()

    print("Data transfer complete!")


# Run the transfer
asyncio.run(transfer_data())
