import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

def generate_uuid():
    return str(uuid.uuid4())

class User(Base):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    email = Column(String(255), unique=True, nullable=True, index=True)
    hashed_password = Column(String(255), nullable=True)
    name = Column(String(100), nullable=False, default="Primary User")
    created_at = Column(DateTime, default=datetime.utcnow)

    shopping_lists = relationship("ShoppingList", back_populates="user", cascade="all, delete-orphan")
    purchase_history = relationship("PurchaseHistory", back_populates="user", cascade="all, delete-orphan")

class Product(Base):
    __tablename__ = "products"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    name = Column(String(200), nullable=False, index=True)
    brand = Column(String(100), nullable=True)
    category = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)

    sizes = relationship("ProductSize", back_populates="product", cascade="all, delete-orphan")

class ProductSize(Base):
    __tablename__ = "product_sizes"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=False)
    size_value = Column(String(50), nullable=False)  # e.g., "650ml", "1L", "250g"
    unit = Column(String(20), nullable=True)         # e.g., "ml", "L", "g"
    is_default = Column(Boolean, default=False)

    product = relationship("Product", back_populates="sizes")

class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    status = Column(String(20), default="ACTIVE")  # "ACTIVE", "COMPLETED"
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="shopping_lists")
    items = relationship("ShoppingItem", back_populates="shopping_list", cascade="all, delete-orphan")

class ShoppingItem(Base):
    __tablename__ = "shopping_items"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    list_id = Column(String(36), ForeignKey("shopping_lists.id"), nullable=False)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=True)
    product_name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)
    unit = Column(String(50), nullable=True)
    size = Column(String(50), nullable=True)         # e.g., "650ml" or "__________"
    is_size_unresolved = Column(Boolean, default=False)
    status = Column(String(20), default="PENDING")   # "PENDING", "PURCHASED"
    created_at = Column(DateTime, default=datetime.utcnow)

    shopping_list = relationship("ShoppingList", back_populates="items")
    product = relationship("Product")

class PurchaseHistory(Base):
    __tablename__ = "purchase_history"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    list_id = Column(String(36), ForeignKey("shopping_lists.id"), nullable=True)
    product_id = Column(String(36), ForeignKey("products.id"), nullable=True)
    product_name = Column(String(200), nullable=False)
    size = Column(String(50), nullable=True)
    purchased_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="purchase_history")
