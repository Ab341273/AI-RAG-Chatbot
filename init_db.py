#!/usr/bin/env python3
"""
Database initialization script - creates all tables and tests connection.
Run this FIRST before running the application.
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from config.Database import engine, Base
from models.sessions import ChatSession
from models.messages import ChatMessage
from models.documents import Document
from services.logging_service import get_logger
from sqlalchemy import text, inspect

logger = get_logger(__name__)


def test_connection():
    """Test database connection."""
    logger.info("Testing database connection...")
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.commit()
            logger.info("✓ Database connection successful!")
            return True
    except Exception as e:
        logger.error(f"✗ Database connection failed: {type(e).__name__} — {e}")
        return False


def create_tables():
    """Create all tables from models."""
    logger.info("Creating database tables...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✓ All tables created successfully!")

        # Verify tables exist
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        logger.info(f"Existing tables: {existing_tables}")

        required_tables = ["sessions", "messages", "documents"]
        missing = [t for t in required_tables if t not in existing_tables]

        if missing:
            logger.error(f"✗ Missing tables: {missing}")
            return False

        logger.info("✓ All required tables exist!")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to create tables: {type(e).__name__} — {e}")
        return False


def main():
    """Initialize database."""
    logger.info("=" * 70)
    logger.info("DATABASE INITIALIZATION")
    logger.info("=" * 70)

    # Step 1: Test connection
    if not test_connection():
        logger.error("Cannot proceed without database connection. Make sure PostgreSQL is running.")
        return False

    # Step 2: Create tables
    if not create_tables():
        logger.error("Failed to create tables.")
        return False

    logger.info("=" * 70)
    logger.info("Database initialization complete!")
    logger.info("=" * 70)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
