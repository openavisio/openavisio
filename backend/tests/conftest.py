import os
from pathlib import Path

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

# Where the app itself talks to Postgres, read before .env.test can shadow it.
# Inside a container that host is `postgres`; .env.test hardcodes `localhost`
# for bare-metal runs, which made every test fail to connect in Docker.
_APP_DATABASE_URL = os.getenv("DATABASE_URL")

# Local test settings (dev DB URL, encryption key). Real env vars win.
# Must run before app imports so settings pick up the values.
load_dotenv(Path(__file__).resolve().parent.parent / ".env.test")

from app.core.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402

_pg_password = os.getenv("POSTGRES_PASSWORD", "devpassword123")

if _APP_DATABASE_URL:
    # same server the app uses, but never the app's database
    TEST_DATABASE_URL = _APP_DATABASE_URL.rsplit("/", 1)[0] + "/vaultdb_test"
else:
    TEST_DATABASE_URL = os.getenv(
        "TEST_DATABASE_URL",
        f"postgresql+asyncpg://openavisio:{_pg_password}@postgres:5432/vaultdb_test",
    )

# Safety guard: never run against the production database
assert "vaultdb_test" in TEST_DATABASE_URL, (
    f"Refusing to run tests against a non-test database.\n"
    f"TEST_DATABASE_URL={TEST_DATABASE_URL}\n"
    f"Database name must contain 'vaultdb_test'."
)


@pytest.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await eng.dispose()


@pytest.fixture
async def db(engine) -> AsyncSession:
    """Transactional DB session — rolls back after each test."""
    connection = await engine.connect()
    transaction = await connection.begin()
    session = AsyncSession(
        bind=connection,
        join_transaction_mode="create_savepoint",
        expire_on_commit=False,
    )
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest.fixture
async def client(db: AsyncSession):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
