from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker, AsyncEngine
from sqlalchemy.orm import DeclarativeBase

from app.config import Config


# SQLAlchemy Base for ORM models
class Base(DeclarativeBase):
    pass


def get_async_url(url: str, db_type: str) -> str:
    """Convert database URL to async SQLAlchemy format."""
    if db_type == "postgresql":
        return url.replace("postgresql://", "postgresql+asyncpg://")
    elif db_type == "mysql":
        return url.replace("mysql://", "mysql+aiomysql://")
    elif db_type == "sqlite":
        return url.replace("sqlite://", "sqlite+aiosqlite://")
    return url


# Async engine for SQLAlchemy
engine = create_async_engine(
    get_async_url(Config.DATABASE_URL, Config.DATABASE_TYPE),
    echo=False
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


# Raw SQL Database class (for LLM-generated queries)
class Database:
    """Database class that works with any SQLAlchemy-supported database."""

    def __init__(self):
        self.engine: AsyncEngine | None = None
        self.db_type = Config.DATABASE_TYPE

    async def connect(self):
        """Create database engine."""
        self.engine = create_async_engine(
            get_async_url(Config.DATABASE_URL, self.db_type),
            echo=False
        )

    async def disconnect(self):
        """Close database engine."""
        if self.engine:
            await self.engine.dispose()

    async def execute_query(self, sql: str, params: dict | None = None) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts.

        Args:
            sql: SQL query (can use :param_name for parameterized queries)
            params: Optional dict of parameter values
        """
        if not self.engine:
            await self.connect()

        async with self.engine.connect() as conn:
            if params:
                result = await conn.execute(text(sql), params)
            else:
                result = await conn.execute(text(sql))
            rows = result.fetchall()

            # Convert to list of dicts with Decimal handling
            output = []
            for row in rows:
                row_dict = {}
                for key, value in row._mapping.items():
                    row_dict[key] = float(value) if isinstance(value, Decimal) else value
                output.append(row_dict)
            return output

    async def execute(self, sql: str):
        """Execute a non-SELECT query (INSERT, UPDATE, etc.)."""
        if not self.engine:
            await self.connect()

        async with self.engine.begin() as conn:
            await conn.execute(text(sql))


db = Database()