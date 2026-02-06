#!/usr/bin/env python3
"""
Migration script to add key_concepts and examples fields to learning_outcomes table.
These fields are for assessment purposes, not teaching content.
"""
import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def migrate():
    """Add key_concepts and examples columns if they don't exist."""
    with engine.connect() as conn:
        # Check if columns exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'learning_outcomes' 
            AND column_name IN ('key_concepts', 'examples')
        """))
        existing_columns = {row[0] for row in result}
        
        # Add key_concepts if it doesn't exist
        if 'key_concepts' not in existing_columns:
            logger.info("Adding key_concepts column to learning_outcomes...")
            conn.execute(text("""
                ALTER TABLE learning_outcomes 
                ADD COLUMN key_concepts TEXT
            """))
            conn.commit()
            logger.info("✓ Added key_concepts column")
        else:
            logger.info("key_concepts column already exists")
        
        # Add examples if it doesn't exist
        if 'examples' not in existing_columns:
            logger.info("Adding examples column to learning_outcomes...")
            conn.execute(text("""
                ALTER TABLE learning_outcomes 
                ADD COLUMN examples TEXT
            """))
            conn.commit()
            logger.info("✓ Added examples column")
        else:
            logger.info("examples column already exists")
        
        logger.info("Migration completed successfully!")


if __name__ == "__main__":
    migrate()
