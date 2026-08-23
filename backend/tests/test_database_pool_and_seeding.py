import sys
import os
from typing import Optional

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from sqlalchemy.orm import Session
from app.database.connection import (
    SessionLocal,
    init_db,
    create_app_engine,
    get_db_status,
    _db_initialized
)
from app.database.models import Product, ProductSize
from scripts.import_products import seed_database

def test_sqlite_explicit_development_engine():
    engine = create_app_engine("sqlite:///./test_dev.db")
    assert "sqlite" in str(engine.url)

def test_postgresql_pooling_parameters():
    try:
        pg_url = "postgresql://postgres:password@localhost:5432/postgres"
        engine = create_app_engine(pg_url)
        assert engine.pool.size() == 2
    except ModuleNotFoundError:
        # psycopg2 optional in local test environment without Postgres driver
        pytest.skip("psycopg2 driver not installed in local python environment")

def test_catalogue_seed_idempotency():
    init_db()
    db = SessionLocal()
    try:
        initial_count = db.query(Product).count()
        assert initial_count > 0

        # Running seed_database again should skip and maintain count
        seed_database(existing_db=db)
        post_count = db.query(Product).count()
        assert post_count == initial_count
    finally:
        db.close()

def test_health_check_database_status():
    status = get_db_status()
    assert status["status"] in ("ok", "degraded")
    assert status["database"] in ("connected", "unavailable")

def test_init_db_skips_when_already_initialized():
    init_db()
    from app.database.connection import _db_initialized
    assert _db_initialized is True
