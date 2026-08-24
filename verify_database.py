#!/usr/bin/env python3
"""
Verify that data is actually saved in the database.
Run this after ingesting PDFs to check if data reached the database.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from services.database_service import DatabaseService
from services.logging_service import get_logger

logger = get_logger(__name__)


def verify_database():
    """Verify database has actual data."""
    print("\n" + "=" * 70)
    print("DATABASE VERIFICATION")
    print("=" * 70 + "\n")

    try:
        # Check 1: Documents
        print("1️⃣  CHECKING DOCUMENTS TABLE...")
        all_docs = DatabaseService.get_all_documents()
        print(f"   Total documents: {len(all_docs)}\n")

        if all_docs:
            print("   Documents in database:")
            for doc in all_docs:
                print(f"   ✓ {doc.doc_id}")
                print(f"     Source: {doc.source}")
                print(f"     Module: {doc.module}")
                print(f"     Chunks: {doc.chunk_count}")
                print(f"     Complexity: {doc.complexity}")
                print(f"     Ingested: {doc.ingested_at}\n")
        else:
            print("   ❌ NO DOCUMENTS FOUND IN DATABASE!\n")

        # Check 2: Document stats
        print("2️⃣  CHECKING DOCUMENT STATS...")
        stats = DatabaseService.get_document_stats()
        print(f"   Total documents: {stats['total_documents']}")
        print(f"   Total chunks: {stats['total_chunks']}")
        print(f"   By module: {stats['by_module']}\n")

        # Check 3: Sessions
        print("3️⃣  CHECKING SESSIONS TABLE...")
        from services.database_service import SessionLocal
        from models.sessions import ChatSession

        db = SessionLocal()
        try:
            session_count = db.query(ChatSession).count()
            print(f"   Total sessions: {session_count}\n")
        finally:
            db.close()

        # Check 4: Messages
        print("4️⃣  CHECKING MESSAGES TABLE...")
        from models.messages import ChatMessage

        db = SessionLocal()
        try:
            message_count = db.query(ChatMessage).count()
            print(f"   Total messages: {message_count}\n")
        finally:
            db.close()

        # Summary
        print("=" * 70)
        if all_docs:
            print("✅ DATABASE HAS DATA!")
            print("=" * 70)
            return True
        else:
            print("❌ DATABASE IS EMPTY!")
            print("=" * 70)
            print("\nNext steps:")
            print("1. Upload PDFs in Streamlit app (Sidebar → Upload PDFs)")
            print("2. Click 'Ingest' button")
            print("3. Run this script again to verify\n")
            return False

    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__} — {e}\n")
        return False


if __name__ == "__main__":
    success = verify_database()
    sys.exit(0 if success else 1)
