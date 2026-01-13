import asyncio
import random
from datetime import date, timedelta
from decimal import Decimal
from sqlalchemy import select
from app.db.database import engine, async_session, Base
from app.models import Product, Feature, Sale


# Sample products
PRODUCTS_DATA = [
    ("iPhone 15", "Electronics", Decimal("999.99")),
    ("MacBook Pro", "Electronics", Decimal("1999.99")),
    ("AirPods Pro", "Electronics", Decimal("249.99")),
    ("Samsung TV", "Electronics", Decimal("799.99")),
    ("Winter Jacket", "Clothing", Decimal("149.99")),
    ("Running Shoes", "Clothing", Decimal("89.99")),
    ("Denim Jeans", "Clothing", Decimal("59.99")),
    ("Organic Coffee", "Food", Decimal("14.99")),
    ("Protein Bars", "Food", Decimal("24.99")),
    ("Olive Oil", "Food", Decimal("19.99")),
    ("Standing Desk", "Home", Decimal("399.99")),
    ("Office Chair", "Home", Decimal("299.99")),
]

# Features for products
FEATURES_DATA = {
    "iPhone 15": [("5G Connectivity", "Ultra-fast mobile internet"), ("A17 Chip", "Latest processor")],
    "MacBook Pro": [("M3 Chip", "Apple Silicon"), ("16GB RAM", "High performance memory")],
    "AirPods Pro": [("Noise Cancellation", "Active noise reduction"), ("Spatial Audio", "3D sound")],
    "Winter Jacket": [("Waterproof", "Rain resistant material"), ("Insulated", "Keeps warm in cold")],
    "Standing Desk": [("Adjustable Height", "Electric motor"), ("Memory Settings", "Save preferred heights")],
}


async def seed_database():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session() as session:
        # Check if data exists
        result = await session.execute(select(Product).limit(1))
        if result.scalar():
            print("Database already seeded")
            return

        # Create products
        products = []
        for name, category, price in PRODUCTS_DATA:
            product = Product(name=name, category=category, price=price)
            products.append(product)
            session.add(product)

        await session.flush()  # Get IDs

        # Create product map for features and sales
        product_map = {p.name: p for p in products}

        # Create features
        for product_name, features in FEATURES_DATA.items():
            if product_name in product_map:
                for feat_name, feat_desc in features:
                    feature = Feature(
                        product_id=product_map[product_name].id,
                        name=feat_name,
                        description=feat_desc
                    )
                    session.add(feature)

        # Generate sales data (2022-2026)
        start_date = date(2022, 1, 1)
        end_date = date(2026, 12, 31)
        current = start_date

        while current <= end_date:
            num_sales = random.randint(3, 10)
            for _ in range(num_sales):
                product_data = random.choice(PRODUCTS_DATA)
                product = product_map[product_data[0]]
                price = float(product_data[2])
                quantity = random.randint(1, 5)

                # Add yearly growth trend
                year_factor = 1 + (current.year - 2022) * 0.15
                # Add seasonality (higher in Q4)
                if current.month >= 10:
                    year_factor *= 1.3

                total = Decimal(str(round(price * quantity * year_factor * random.uniform(0.9, 1.1), 2)))

                sale = Sale(
                    product_id=product.id,
                    quantity=quantity,
                    total_amount=total,
                    sale_date=current
                )
                session.add(sale)

            current += timedelta(days=1)

        await session.commit()
        print("Database seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_database())
