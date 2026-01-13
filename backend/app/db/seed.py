import asyncio
import random
from datetime import date, timedelta
from app.db.database import db, SCHEMA_SQL

# Sample products
PRODUCTS = [
    ("iPhone 15", "Electronics", 999.99),
    ("MacBook Pro", "Electronics", 1999.99),
    ("AirPods Pro", "Electronics", 249.99),
    ("Samsung TV", "Electronics", 799.99),
    ("Winter Jacket", "Clothing", 149.99),
    ("Running Shoes", "Clothing", 89.99),
    ("Denim Jeans", "Clothing", 59.99),
    ("Organic Coffee", "Food", 14.99),
    ("Protein Bars", "Food", 24.99),
    ("Olive Oil", "Food", 19.99),
    ("Standing Desk", "Home", 399.99),
    ("Office Chair", "Home", 299.99),
]

# Features for products
FEATURES = {
    "iPhone 15": [("5G Connectivity", "Ultra-fast mobile internet"), ("A17 Chip", "Latest processor")],
    "MacBook Pro": [("M3 Chip", "Apple Silicon"), ("16GB RAM", "High performance memory")],
    "AirPods Pro": [("Noise Cancellation", "Active noise reduction"), ("Spatial Audio", "3D sound")],
    "Winter Jacket": [("Waterproof", "Rain resistant material"), ("Insulated", "Keeps warm in cold")],
    "Standing Desk": [("Adjustable Height", "Electric motor"), ("Memory Settings", "Save preferred heights")],
}


async def seed_database():
    await db.connect()

    # Create tables
    await db.execute(SCHEMA_SQL)

    # Check if data exists
    existing = await db.execute_query("SELECT COUNT(*) as count FROM products")
    if existing[0]["count"] > 0:
        print("Database already seeded")
        await db.disconnect()
        return

    # Insert products
    for name, category, price in PRODUCTS:
        await db.execute(f"""
            INSERT INTO products (name, category, price)
            VALUES ('{name}', '{category}', {price})
        """)

    # Get product IDs
    products = await db.execute_query("SELECT id, name FROM products")
    product_map = {p["name"]: p["id"] for p in products}

    # Insert features
    for product_name, features in FEATURES.items():
        if product_name in product_map:
            for feat_name, feat_desc in features:
                await db.execute(f"""
                    INSERT INTO features (product_id, name, description)
                    VALUES ({product_map[product_name]}, '{feat_name}', '{feat_desc}')
                """)

    # Generate sales data (2022-2026)
    start_date = date(2022, 1, 1)
    end_date = date(2026, 12, 31)
    current = start_date

    while current <= end_date:
        # Random sales for random products each day
        num_sales = random.randint(3, 10)
        for _ in range(num_sales):
            product = random.choice(PRODUCTS)
            product_id = product_map[product[0]]
            price = product[2]
            quantity = random.randint(1, 5)

            # Add yearly growth trend
            year_factor = 1 + (current.year - 2022) * 0.15
            # Add seasonality (higher in Q4)
            if current.month >= 10:
                year_factor *= 1.3

            total = round(price * quantity * year_factor * random.uniform(0.9, 1.1), 2)

            await db.execute(f"""
                INSERT INTO sales (product_id, quantity, total_amount, sale_date)
                VALUES ({product_id}, {quantity}, {total}, '{current}')
            """)

        current += timedelta(days=1)

    print("Database seeded successfully!")
    await db.disconnect()


if __name__ == "__main__":
    asyncio.run(seed_database())
