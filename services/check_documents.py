"""Quick check of document tracking in database."""
import sys
from services.database_service import DatabaseService

try:
    # Get stats
    stats = DatabaseService.get_document_stats()

    print("\n" + "="*70)
    print("DOCUMENT TRACKING STATUS")
    print("="*70)

    print(f"\nTotal Documents: {stats.get('total_documents', 0)}")
    print(f"Total Chunks: {stats.get('total_chunks', 0)}")

    print("\nBy Module:")
    for module, count in sorted(stats.get('by_module', {}).items()):
        print(f"  [{module}] {count} documents")

    # Get all documents
    all_docs = DatabaseService.get_all_documents()
    print(f"\nDocuments List ({len(all_docs)} total):")
    for doc in all_docs[:10]:
        print(f"  - {doc.doc_id}: {doc.source} ({doc.module}) - {doc.chunk_count} chunks")

    if len(all_docs) > 10:
        print(f"  ... and {len(all_docs) - 10} more")

    print("\n" + "="*70)

except Exception as e:
    print(f"Error: {type(e).__name__} — {e}")
    import traceback
    traceback.print_exc()
