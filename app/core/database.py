from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import settings

# One async connection pool for the whole app.
engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=0,
    pool_pre_ping=True,  # test a pooled connection before use; survives DB restarts / idle drops
    echo=settings.sql_echo,
)

async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


def get_session_maker() -> async_sessionmaker:
    """For work that outlives the request (background indexing) and needs its own session.
    A dependency, so tests can point it at the test database."""
    return async_session_maker


async def get_db():
    """FastAPI dependency: one session per request, closed automatically afterwards."""
    async with async_session_maker() as session:
        yield session
