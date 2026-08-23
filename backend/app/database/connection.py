from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.database.models import Base, User, Product
import logging
import os

logger = logging.getLogger("uvicorn.error")

def get_engine(db_url: str):
    is_sqlite = "sqlite" in db_url
    connect_args = {"check_same_thread": False} if is_sqlite else {}
    return create_engine(db_url, connect_args=connect_args, pool_pre_ping=True)

# Primary Engine setup
primary_db_url = settings.DATABASE_URL
engine = get_engine(primary_db_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def run_migrations(db_engine=None):
    """Idempotent database migration for SQLite/PostgreSQL tables."""
    target_engine = db_engine or engine
    try:
        inspector = inspect(target_engine)
        tables = inspector.get_table_names()
        if "shopping_items" in tables:
            columns = [c["name"] for c in inspector.get_columns("shopping_items")]
            if "category" not in columns:
                logger.info("Migrating database schema: Adding missing 'category' column to 'shopping_items'...")
                with target_engine.begin() as conn:
                    conn.execute(text("ALTER TABLE shopping_items ADD COLUMN category VARCHAR(100)"))
                logger.info("Migration successful: 'category' column added to 'shopping_items'.")
        if "users" in tables:
            user_columns = [c["name"] for c in inspector.get_columns("users")]
            with target_engine.begin() as conn:
                if "email" not in user_columns:
                    logger.info("Migrating database schema: Adding 'email' column to 'users'...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN email VARCHAR(255)"))
                if "hashed_password" not in user_columns:
                    logger.info("Migrating database schema: Adding 'hashed_password' column to 'users'...")
                    conn.execute(text("ALTER TABLE users ADD COLUMN hashed_password VARCHAR(255)"))
    except Exception as e:
        logger.error(f"Error running database schema migration: {e}")

def init_db():
    """Initializes tables with fallback to SQLite if remote PostgreSQL is unreachable and auto-seeds catalog."""
    global engine, SessionLocal
    try:
        # Test connection
        with engine.connect() as conn:
            pass
        logger.info(f"Connected successfully to primary database ({settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'local'}).")
    except Exception as e:
        logger.warning(f"Primary database connection failed ({e}). Falling back to local SQLite database.")
        fallback_url = "sqlite:///./voice_shopping.db"
        engine = get_engine(fallback_url)
        SessionLocal.configure(bind=engine)

    try:
        Base.metadata.create_all(bind=engine)
        run_migrations(engine)

        db = SessionLocal()
        try:
            user = db.query(User).filter_by(id="default-user-id").first()
            if not user:
                user = User(id="default-user-id", name="Primary User")
                db.add(user)
                db.commit()
                logger.info("Created default primary user in database.")

            # Auto-seed catalogue if database products table is empty
            product_count = db.query(Product).count()
            if product_count == 0:
                logger.info("Database catalogue is empty. Auto-seeding 114 supermarket products...")
                try:
                    from scripts.import_products import seed_database
                    seed_database()
                    logger.info("Auto-seeded supermarket catalogue successfully.")
                except Exception as e_seed:
                    logger.error(f"Error auto-seeding catalogue: {e_seed}")
        except Exception as err:
            db.rollback()
            logger.error(f"Error initializing DB user/catalogue: {err}")
        finally:
            db.close()
    except Exception as e_init:
        logger.error(f"Critical DB initialization error: {e_init}")
