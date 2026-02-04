"""
Database configuration and session management.
"""
import os
import logging
from typing import Generator
from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Database URL from environment
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://aims_user:aims_password@localhost:5432/aims_db"
)

# Create engine
engine = create_engine(
    DATABASE_URL,
    echo=True,  # Set to False in production
    pool_pre_ping=True,  # Verify connections before using
)


def create_db_and_tables():
    """Create all database tables. Ensures pgvector extension is enabled first."""
    # Enable pgvector extension before creating tables
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            conn.commit()
        logger.info("✅ pgvector extension enabled")
    except Exception as e:
        logger.warning(f"Could not enable pgvector extension (may already exist): {e}")
    
    # Create tables
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Get database session for dependency injection."""
    with Session(engine) as session:
        yield session
