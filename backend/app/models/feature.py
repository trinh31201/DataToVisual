from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Feature(Base):
    __tablename__ = "features"

    id = Column(Integer, primary_key=True)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Relationships
    product = relationship("Product", back_populates="features")
