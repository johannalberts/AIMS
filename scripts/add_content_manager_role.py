#!/usr/bin/env python3
"""
Add CONTENT_MANAGER role to the UserRole enum in database.
This script adds the new role value to the existing enum type.
"""
from sqlalchemy import create_engine, text
import os

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://aims_user:aims_password@localhost:5432/aims_db")
engine = create_engine(DATABASE_URL)

def migrate():
    """Add CONTENT_MANAGER to UserRole enum."""
    print("Adding CONTENT_MANAGER role to database...")
    
    with engine.connect() as conn:
        # Check if the role already exists
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT 1 FROM pg_enum 
                WHERE enumlabel = 'content_manager' 
                AND enumtypid = (
                    SELECT oid FROM pg_type WHERE typname = 'userrole'
                )
            );
        """))
        exists = result.scalar()
        
        if exists:
            print("✓ CONTENT_MANAGER role already exists in database")
        else:
            # Add the new enum value
            conn.execute(text("""
                ALTER TYPE userrole ADD VALUE 'content_manager';
            """))
            conn.commit()
            print("✓ Successfully added CONTENT_MANAGER role to database")
    
    print("\nMigration complete!")

if __name__ == "__main__":
    migrate()
