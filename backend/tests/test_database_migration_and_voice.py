"""
test_database_migration_and_voice.py
Tests database schema migration for category column and HTTP endpoints.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database.models import Base, User, Product, ShoppingList, ShoppingItem
from app.database.connection import get_db, run_migrations
from app.main import app

mig_engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestSession = sessionmaker(bind=mig_engine)

def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture(autouse=True)
def setup_migrated_db():
    Base.metadata.drop_all(bind=mig_engine)
    
    # Simulate legacy database created BEFORE 'category' column existed
    with mig_engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE shopping_lists (
                id VARCHAR(36) PRIMARY KEY,
                user_id VARCHAR(36) NOT NULL,
                status VARCHAR(20) DEFAULT 'ACTIVE',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE shopping_items (
                id VARCHAR(36) PRIMARY KEY,
                list_id VARCHAR(36) NOT NULL,
                product_id VARCHAR(36),
                product_name VARCHAR(200) NOT NULL,
                quantity INTEGER DEFAULT 1,
                unit VARCHAR(50),
                size VARCHAR(50),
                is_size_unresolved BOOLEAN DEFAULT 0,
                status VARCHAR(20) DEFAULT 'PENDING',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            INSERT INTO users (id, name) VALUES ('default-user-id', 'Default User')
        """))
        conn.execute(text("""
            INSERT INTO shopping_lists (id, user_id, status) VALUES ('list-1', 'default-user-id', 'ACTIVE')
        """))
        conn.execute(text("""
            INSERT INTO shopping_items (id, list_id, product_name, quantity) VALUES ('item-legacy-1', 'list-1', 'Legacy Milk', 2)
        """))

    yield
    Base.metadata.drop_all(bind=mig_engine)

def test_migration_adds_missing_category_column():
    """Verify that run_migrations idempotently adds category column to legacy table."""
    inspector = inspect(mig_engine)
    cols_before = [c["name"] for c in inspector.get_columns("shopping_items")]
    assert "category" not in cols_before

    # Run migration
    run_migrations(mig_engine)

    inspector_after = inspect(mig_engine)
    cols_after = [c["name"] for c in inspector_after.get_columns("shopping_items")]
    assert "category" in cols_after

    # Verify run_migrations is idempotent when executed again
    run_migrations(mig_engine)
    inspector_again = inspect(mig_engine)
    cols_again = [c["name"] for c in inspector_again.get_columns("shopping_items")]
    assert "category" in cols_again

def test_get_shopping_list_returns_200_after_migration():
    """Verify GET /api/shopping-list returns HTTP 200 and legacy item has fallback category."""
    run_migrations(mig_engine)

    app.dependency_overrides[get_db] = override_get_db
    local_client = TestClient(app)

    response = local_client.get("/api/shopping-list?user_id=default-user-id")
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
    
    data = response.json()
    assert "items" in data
    assert len(data["items"]) == 1
    
    legacy_item = data["items"][0]
    assert legacy_item["product_name"] == "Legacy Milk"
    assert legacy_item["quantity"] == 2
    assert legacy_item["category"] in ("Other", None)
