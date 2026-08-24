#!/usr/bin/env python3
"""Recreate documents table with all correct columns"""

import sys
from pathlib import Path
from sqlalchemy import text

sys.path.insert(0, str(Path(__file__).parent))

from config.Database import engine

def recreate_table():
    print("\n" + "=" * 70)
    print("RECREATING DOCUMENTS TABLE")
    print("=" * 70 + "\n")

    try:
        with engine.connect() as conn:
            # Drop old table
            print("1️⃣  Dropping old table...")
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))
            conn.commit()
            print("   ✅ Done!\n")

            # Create new table with ALL columns
            print("2️⃣  Creating new table with all columns...")
            sql = """
            CREATE TABLE documents (
                doc_id VARCHAR(255) PRIMARY KEY,
                source VARCHAR(255) NOT NULL,
                module VARCHAR(50),
                file_size INTEGER,
                chunk_count INTEGER DEFAULT 0,
                version VARCHAR(50),
                complexity VARCHAR(50),
                landscape VARCHAR(50),
                ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            conn.execute(text(sql))
            conn.commit()
            print("   ✅ Done!\n")

            # Verify
            print("3️⃣  Verifying columns...")
            result = conn.execute(text("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name='documents'
                ORDER BY ordinal_position
            """))
            columns = [row[0] for row in result]
            for col in columns:
                print(f"   ✓ {col}")

            print("\n" + "=" * 70)
            print("✅ TABLE RECREATED SUCCESSFULLY!")
            print("=" * 70 + "\n")
            return True

    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        return False

if __name__ == "__main__":
    success = recreate_table()
    sys.exit(0 if success else 1)
