import asyncpg
from typing import Any
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import Config


# SQLAlchemy Base for ORM models
class Base(DeclarativeBase):
    pass


# Async engine for SQLAlchemy
engine = create_async_engine(
    Config.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://"),
    echo=False
)

# Session factory
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session() -> AsyncSession:
    async with async_session() as session:
        yield session


# Raw SQL Database class (for LLM-generated queries)
class Database:
    def __init__(self):
        self.pool: asyncpg.Pool | None = None

    async def connect(self):
        self.pool = await asyncpg.create_pool(Config.DATABASE_URL)

    async def disconnect(self):
        if self.pool:
            await self.pool.close()

    async def execute_query(self, sql: str) -> list[dict[str, Any]]:
        if not self.pool:
            raise RuntimeError("Database not connected")

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(sql)
            return [dict(row) for row in rows]

    async def execute(self, sql: str):
        if not self.pool:
            raise RuntimeError("Database not connected")

        async with self.pool.acquire() as conn:
            await conn.execute(sql)


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

TABLE sales:
- id (INT, PRIMARY KEY): Unique sale identifier
- product_id (INT, FK -> products.id): Reference to product sold
- quantity (INT): Number of units sold
- total_amount (DECIMAL): Total sale amount
- sale_date (DATE): Date of sale (2022-2026)

RELATIONSHIPS:
- products 1:N features
- products 1:N sales
"""
