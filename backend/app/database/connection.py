from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings
from app.database.models import Base, User
import logging

logger = logging.getLogger("uvicorn.error")

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

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
    """Initializes tables, applies schema migrations, and ensures default user exists."""
    Base.metadata.create_all(bind=engine)
    run_migrations()

    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id="default-user-id").first()
        if not user:
            user = User(id="default-user-id", name="Primary User")
            db.add(user)
            db.commit()
            logger.info("Created default primary user in database.")
    except Exception as e:
        db.rollback()
        logger.error(f"Error initializing DB user: {e}")
    finally:
        db.close()
