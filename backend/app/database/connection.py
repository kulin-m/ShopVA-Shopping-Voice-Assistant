from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.database.models import Base, User, Product, ProductSize
import logging
import os
from typing import Dict, Any

logger = logging.getLogger("uvicorn.error")

_db_initialized = False

def create_app_engine(db_url: str):
    """
    Creates the SQLAlchemy Engine with explicit pool configurations suitable for
    Supabase Session Pooler and Render Free limits.
    """
    is_sqlite = "sqlite" in db_url.lower()

    if is_sqlite:
        return create_engine(
            db_url,
            connect_args={"check_same_thread": False},
            pool_pre_ping=True
        )

    # Conservative Pooling Parameters for PostgreSQL / Supabase Session Pooler
    pool_size = int(os.getenv("DB_POOL_SIZE", "2"))
    max_overflow = int(os.getenv("DB_MAX_OVERFLOW", "0"))
    pool_timeout = int(os.getenv("DB_POOL_TIMEOUT", "10"))
    pool_recycle = int(os.getenv("DB_POOL_RECYCLE", "1800"))

    safe_target = db_url.split("@")[-1] if "@" in db_url else "local"
    logger.info(f"[DATABASE] Initializing PostgreSQL engine for target: {safe_target} (pool_size={pool_size}, max_overflow={max_overflow})")

    return create_engine(
        db_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_timeout=pool_timeout,
        pool_recycle=pool_recycle,
        pool_pre_ping=True
    )

# Primary Engine setup
primary_db_url = settings.DATABASE_URL
engine = create_app_engine(primary_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """Request-scoped database session dependency with guaranteed cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_status() -> Dict[str, Any]:
    """Lightweight connection check for /health endpoint without persistent leaks."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}
    except Exception:
        return {"status": "degraded", "database": "unavailable"}

def run_migrations(db_engine=None):
    """Idempotent database migration for SQLite/PostgreSQL tables."""
    target_engine = db_engine or engine
    try:
        inspector = inspect(target_engine)
        tables = inspector.get_table_names()
        if "shopping_items" in tables:
            columns = [c["name"] for c in inspector.get_columns("shopping_items")]
            if "category" not in columns:
                logger.info("[DATABASE] Migrating schema: Adding 'category' column to 'shopping_items'...")
                with target_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE shopping_items ADD COLUMN category VARCHAR(100)"))
        if "users" in tables:
            user_columns = [c["name"] for c in inspector.get_columns("users")]
            with target_engine.begin() as conn:
                if "email" not in user_columns:
                    logger.info("[DATABASE] Migrating schema: Adding 'email' column to 'users'...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
                if "hashed_password" not in user_columns:
                    logger.info("[DATABASE] Migrating schema: Adding 'hashed_password' column to 'users'...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)"))
    except Exception as e:
        logger.error(f"[DATABASE] Migration warning: {e}")

def init_db():
    """
    Process-level database initialization.
    Executes schema creation and catalogue seeding exactly ONCE per application startup.
    Fails safely in production if PostgreSQL is unreachable without silent SQLite fallback.
    """
    global engine, SessionLocal, _db_initialized
    if _db_initialized:
        logger.info("[DATABASE] Database already initialized for this process; skipping.")
        return

    allow_sqlite_fallback = os.getenv("USE_SQLITE_FALLBACK", "false").lower() == "true" or "sqlite" in settings.DATABASE_URL.lower()

    # Step A: Test Primary PostgreSQL Database Connectivity
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        safe_host = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local"
        logger.info(f"[DATABASE] Connected successfully to primary database ({safe_host}).")
    except Exception as e:
        logger.error(f"[DATABASE] Primary database connection failed: {e}")
        if allow_sqlite_fallback:
            logger.warning("[DATABASE] USE_SQLITE_FALLBACK=true enabled. Falling back to local SQLite database.")
            fallback_url = "sqlite:///./voice_shopping.db"
            engine = create_app_engine(fallback_url)
            SessionLocal.configure(bind=engine)
        else:
            logger.critical("[DATABASE] Production database connection failed. Stopping startup to prevent data corruption.")
            raise RuntimeError(f"Production database connection failure: {e}") from e

    # Step B: Schema Creation & Idempotent Migrations
    try:
        Base.metadata.create_all(bind=engine)
        run_migrations(engine)
        logger.info("[DATABASE] Schema initialized successfully.")

        # Step C: Controlled Catalogue Seeding
        db = SessionLocal()
        try:
            # Ensure primary default user exists
            user = db.query(User).filter_by(id="default-user-id").first()
            if not user:
                user = User(id="default-user-id", name="Primary User")
                db.add(user)
                db.commit()
                logger.info("[DATABASE] Created default primary user.")

            # Concurrency-safe Catalogue Seed Check
            product_count = db.query(Product).count()
            if product_count > 0:
                logger.info(f"[DATABASE] Catalogue already initialized: {product_count} products exist; skipping seed.")
            else:
                logger.info("[DATABASE] Database catalogue is empty. Auto-seeding 114 supermarket products...")
                from scripts.import_products import seed_database
                seed_database(existing_db=db)
                product_count = db.query(Product).count()
                logger.info(f"[DATABASE] Production catalogue initialized: {product_count} products.")
        except Exception as err:
            db.rollback()
            logger.error(f"[DATABASE] Error during catalogue check/seed: {err}")
            raise err
        finally:
            db.close()

        _db_initialized = True
        logger.info("[DATABASE] Database initialization complete.")
    except Exception as e_init:
        logger.critical(f"[DATABASE] Critical database initialization failure: {e_init}")
        raise e_init
