"""Initialize documents table in the database."""
import sys
from sqlalchemy import create_engine, text
from config.Database import DATABASE_URL
from models.documents import Base

def init_documents_table():
    """Create documents table if it doesn't exist."""
    try:
        # Create engine
        engine = create_engine(DATABASE_URL)

        # Create all tables defined in Base metadata
        Base.metadata.create_all(bind=engine)

        print("[OK] Documents table initialized successfully!")

        # Verify table exists
        with engine.connect() as connection:
            result = connection.execute(text("SELECT COUNT(*) FROM documents"))
            count = result.scalar()
            print(f"[INFO] Current document count in database: {count}")

    except Exception as e:
        print(f"[ERROR] Failed to initialize documents table: {type(e).__name__} — {e}")
        sys.exit(1)


if __name__ == "__main__":
    init_documents_table()
