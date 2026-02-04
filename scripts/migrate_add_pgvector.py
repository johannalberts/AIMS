"""
Database migration script to add pgvector extension and learning_contents table.
Run this after starting the PostgreSQL database.
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine, text
from app.database import DATABASE_URL
from app.models import SQLModel
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migration():
    """Run database migration."""
    logger.info("Starting database migration...")
    
    # Create engine
    engine = create_engine(DATABASE_URL)
    
    # Enable pgvector extension
    logger.info("Enabling pgvector extension...")
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.commit()
    logger.info("✅ pgvector extension enabled")
    
    # Create/update all tables
    logger.info("Creating/updating database tables...")
    SQLModel.metadata.create_all(engine)
    logger.info("✅ Database tables created/updated")
    
    # Create vector index for efficient similarity search
    logger.info("Creating vector index for learning_contents...")
    with engine.connect() as conn:
        # Check if index exists
        check_index = text("""
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'learning_contents' 
            AND indexname = 'learning_contents_embedding_idx';
        """)
        result = conn.execute(check_index)
        
        if not result.fetchone():
            # Create IVFFlat index for cosine similarity
            # Using lists=100 for ~10,000 vectors (adjust based on expected scale)
            create_index = text("""
                CREATE INDEX learning_contents_embedding_idx 
                ON learning_contents 
                USING ivfflat (embedding vector_cosine_ops) 
                WITH (lists = 100);
            """)
            conn.execute(create_index)
            conn.commit()
            logger.info("✅ Vector index created")
        else:
            logger.info("✅ Vector index already exists")
    
    logger.info("🎉 Migration completed successfully!")


if __name__ == "__main__":
    run_migration()
