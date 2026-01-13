import asyncpg
from typing import Any
from app.config import Config


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


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS features (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT
);

CREATE TABLE IF NOT EXISTS sales (
    id SERIAL PRIMARY KEY,
    product_id INT REFERENCES products(id) ON DELETE CASCADE,
    quantity INT NOT NULL,
    total_amount DECIMAL(12,2) NOT NULL,
    sale_date DATE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_sales_date ON sales(sale_date);
CREATE INDEX IF NOT EXISTS idx_sales_product ON sales(product_id);
CREATE INDEX IF NOT EXISTS idx_products_category ON products(category);
"""


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
