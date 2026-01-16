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

    async def execute_query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a SELECT query and return results as list of dicts."""
        if not self.engine:
            await self.connect()

        async with self.engine.connect() as conn:
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


SCHEMA_DESCRIPTION = """
Database Schema:

TABLE products:
- id (INT, PRIMARY KEY): Unique product identifier
- name (VARCHAR): Product name
- category (VARCHAR): Product category ('Electronics', 'Clothing', 'Food', 'Home')
- price (DECIMAL): Unit price
- created_at (TIMESTAMP): When product was added

TABLE features:
- id (INT, PRIMARY KEY): Unique feature identifier
- product_id (INT, FK -> products.id): Reference to product
- name (VARCHAR): Feature name
- description (TEXT): Feature description
- created_at (TIMESTAMP): When feature was added

TABLE sales:
- id (INT, PRIMARY KEY): Unique sale identifier
- product_id (INT, FK -> products.id): Reference to product sold
- quantity (INT): Number of units sold
- total_amount (DECIMAL): Total sale amount
- sale_date (DATE): Date of sale (2022-2026)
- created_at (TIMESTAMP): When sale was recorded

RELATIONSHIPS:
- products 1:N features
- products 1:N sales
"""
