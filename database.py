from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from config import settings

# create a async database engine connection pool
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=0,
    echo=True,
)

# create a session
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


# create a database that takes in a session
async def get_db():
    async with async_session_maker() as session:
        yield session
