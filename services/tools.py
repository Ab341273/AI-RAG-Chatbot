from langchain_core.tools import tool
from datetime import datetime
from zoneinfo import ZoneInfo
import openmeteo_requests
import requests_cache

from retry_requests import retry

@tool
def calculator(expression: str) -> str:
    """
    Performs basic mathematical calculations.
    Example: 10 + 5, 20 * 3, 100 / 4
    """
    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception:
        return "Invalid mathematical expression."
    
    
    #date and time tool  
   



@tool
def get_current_datetime(timezone: str = "Asia/Karachi") -> str:
    """
    Get the current date and time for a given timezone.
    Example timezone: Asia/Karachi
    """
    try:
        current_time = datetime.now(ZoneInfo(timezone))

        return current_time.strftime(
            "%A, %d %B %Y, %I:%M:%S %p"
        )

    except Exception:
        return "Invalid timezone."
    
    
    #weather caling tool 




# Open-Meteo client setup
cache_session = requests_cache.CachedSession(
    ".cache",
    expire_after=3600
)

retry_session = retry(
    cache_session,
    retries=5,
    backoff_factor=0.2
)

openmeteo = openmeteo_requests.Client(
    session=retry_session
)


@tool
def get_weather(latitude: float, longitude: float) -> str:
    """
    Get current and hourly weather information using Open-Meteo.

    Provide latitude and longitude of the location.
    """

    url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": latitude,
        "longitude": longitude,
        "current": [
            "temperature_2m",
            "rain",
        ],
        "hourly": [
            "temperature_2m",
            "rain",
        ],
        "timezone": "auto",
    }

    try:
        responses = openmeteo.weather_api(url, params=params)

        response = responses[0]

        current = response.Current()

        temperature = current.Variables(0).Value()
        rain = current.Variables(1).Value()

        return (
            f"Temperature: {temperature}°C\n"
            f"Rain: {rain} mm"
        )

    except Exception as e:
        return f"Weather tool error: {str(e)}"


# Database tools

@tool
def check_database_documents() -> str:
    """
    Check all documents stored in the database.
    Returns count and list of all ingested documents with their metadata.
    """
    try:
        from services.database_service import DatabaseService

        documents = DatabaseService.get_all_documents()

        if not documents:
            return "No documents found in database."

        result = f"Total documents in database: {len(documents)}\n\n"

        for doc in documents:
            result += f"📄 {doc.doc_id}\n"
            result += f"   Source: {doc.source}\n"
            result += f"   Module: {doc.module}\n"
            result += f"   Chunks: {doc.chunk_count}\n"
            result += f"   Complexity: {doc.complexity}\n"
            result += f"   Landscape: {doc.landscape}\n"
            result += f"   Version: {doc.version}\n"
            result += f"   Ingested: {doc.ingested_at}\n\n"

        return result

    except Exception as e:
        return f"Database error: {str(e)}"


@tool
def get_document_stats() -> str:
    """
    Get statistics about documents in the database.
    Returns total count, count by module, and total chunks.
    """
    try:
        from services.database_service import DatabaseService

        stats = DatabaseService.get_document_stats()

        result = f"📊 Document Statistics\n"
        result += f"Total Documents: {stats['total_documents']}\n"
        result += f"Total Chunks: {stats['total_chunks']}\n\n"

        if stats['by_module']:
            result += "Documents by Module:\n"
            for module, count in sorted(stats['by_module'].items()):
                result += f"  {module}: {count}\n"
        else:
            result += "No modules found.\n"

        return result

    except Exception as e:
        return f"Database error: {str(e)}"


@tool
def search_documents_by_module(module: str) -> str:
    """
    Search for documents by SAP module (e.g., CO, FI, MM, TM, SD, WM).
    Returns all documents belonging to that module.
    """
    try:
        from services.database_service import DatabaseService

        documents = DatabaseService.get_all_documents()

        matching_docs = [doc for doc in documents if doc.module == module.upper()]

        if not matching_docs:
            return f"No documents found for module: {module}"

        result = f"Documents for module {module.upper()}: {len(matching_docs)}\n\n"

        for doc in matching_docs:
            result += f"📄 {doc.doc_id}\n"
            result += f"   Source: {doc.source}\n"
            result += f"   Chunks: {doc.chunk_count}\n"
            result += f"   Complexity: {doc.complexity}\n\n"

        return result

    except Exception as e:
        return f"Database error: {str(e)}"


@tool
def check_database_vs_chroma() -> str:
    """
    Check the mismatch between SQL database documents and ChromaDB embeddings.
    Shows which documents are in the database but not properly embedded.
    """
    try:
        from services.database_service import DatabaseService
        import chromadb
        from pathlib import Path

        # Get database documents
        db_docs = DatabaseService.get_all_documents()
        db_count = len(db_docs)
        db_doc_ids = {doc.doc_id for doc in db_docs}

        # Get ChromaDB documents
        BASE_DIR = Path(__file__).resolve().parent.parent
        CHROMA_DIR = BASE_DIR / "chroma_db"

        if not CHROMA_DIR.exists():
            chroma_docs = set()
            chroma_count = 0
        else:
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_or_create_collection(name="pdf_documents")
            data = collection.get()

            chroma_docs = set()
            if data and data.get("metadatas"):
                for metadata in data.get("metadatas", []):
                    chroma_docs.add(metadata.get("doc_id", "Unknown"))
            chroma_count = len(chroma_docs)

        # Find missing embeddings
        missing = db_doc_ids - chroma_docs

        result = f"📊 Database vs ChromaDB Status\n"
        result += f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        result += f"SQL Database Documents: {db_count}\n"
        result += f"ChromaDB Embeddings: {chroma_count}\n"
        result += f"Missing Embeddings: {len(missing)}\n\n"

        if missing:
            result += "❌ Documents NOT embedded in ChromaDB:\n"
            for doc_id in sorted(missing):
                doc = next((d for d in db_docs if d.doc_id == doc_id), None)
                if doc:
                    result += f"  • {doc.doc_id} (source: {doc.source}, chunks: {doc.chunk_count})\n"
            result += "\n⚠️ Run ingestion again to embed these documents."
        else:
            result += "✅ All documents are properly embedded!"

        return result

    except Exception as e:
        return f"Error: {str(e)}"

    