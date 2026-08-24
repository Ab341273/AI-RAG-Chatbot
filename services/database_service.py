from sqlalchemy.orm import Session
from sqlalchemy import func
from models.sessions import ChatSession
from models.messages import ChatMessage
from models.documents import Document
from config.Database import SessionLocal
import uuid
from services.logging_service import get_logger

logger = get_logger(__name__)


class DatabaseService:
    """Service to handle database operations for chat sessions and messages"""

    @staticmethod
    def create_session(title: str = "New Chat") -> ChatSession:
        """Create a new chat session"""
        db: Session = SessionLocal()
        try:
            session = ChatSession(title=title)
            db.add(session)
            db.commit()
            db.refresh(session)
            return session
        finally:
            db.close()

    @staticmethod
    def add_message(session_id: uuid.UUID, role: str, content: str) -> ChatMessage:
        """Add a message to a chat session"""
        db: Session = SessionLocal()
        try:
            message = ChatMessage(
                session_id=session_id,
                role=role,
                content=content
            )
            db.add(message)
            db.commit()
            db.refresh(message)
            return message
        finally:
            db.close()

    @staticmethod
    def get_session(session_id: uuid.UUID) -> ChatSession:
        """Get a chat session by ID with eager loading of messages"""
        from sqlalchemy.orm import joinedload
        db: Session = SessionLocal()
        try:
            # Eagerly load messages to avoid lazy load issues
            session = db.query(ChatSession).options(
                joinedload(ChatSession.messages)
            ).filter(
                ChatSession.id == session_id
            ).first()

            # Force load messages before closing session
            if session and session.messages:
                _ = len(session.messages)

            return session
        finally:
            db.close()

    @staticmethod
    def get_session_messages(session_id: uuid.UUID) -> list[ChatMessage]:
        """Get all messages from a chat session"""
        db: Session = SessionLocal()
        try:
            messages = db.query(ChatMessage).filter(
                ChatMessage.session_id == session_id
            ).order_by(ChatMessage.created_at).all()
            return messages
        finally:
            db.close()

    @staticmethod
    def get_all_sessions() -> list[ChatSession]:
        """Get all chat sessions with eagerly loaded messages"""
        from sqlalchemy.orm import joinedload
        db: Session = SessionLocal()
        try:
            # Eagerly load messages for all sessions
            sessions = db.query(ChatSession).options(
                joinedload(ChatSession.messages)
            ).order_by(
                ChatSession.updated_at.desc()
            ).all()

            # Force load all messages before closing session
            for session in sessions:
                if session.messages:
                    _ = len(session.messages)

            return sessions
        finally:
            db.close()

    @staticmethod
    def delete_session(session_id: uuid.UUID) -> bool:
        """Delete a chat session (cascades to messages)"""
        db: Session = SessionLocal()
        try:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()
            if session:
                db.delete(session)
                db.commit()
                return True
            return False
        finally:
            db.close()

    @staticmethod
    def update_session_title(session_id: uuid.UUID, title: str) -> ChatSession:
        """Update a chat session title"""
        db: Session = SessionLocal()
        try:
            session = db.query(ChatSession).filter(
                ChatSession.id == session_id
            ).first()
            if session:
                session.title = title
                db.commit()
                db.refresh(session)
            return session
        finally:
            db.close()

    # ==================== DOCUMENT TRACKING ====================

    @staticmethod
    def add_document(doc_id: str, source: str, module: str = None, file_size: int = None, chunk_count: int = 0,
                     version: str = None, complexity: str = None, landscape: str = None) -> Document:
        """Add a document to the knowledge base tracking"""
        db: Session = SessionLocal()
        try:
            # Check if document already exists
            existing = db.query(Document).filter(Document.doc_id == doc_id).first()
            if existing:
                # Update existing document
                existing.chunk_count = chunk_count
                existing.version = version or existing.version
                existing.complexity = complexity or existing.complexity
                existing.landscape = landscape or existing.landscape
                db.commit()
                db.refresh(existing)
                logger.debug(f"Updated document in database: {doc_id}")
                return existing

            # Create new document
            document = Document(
                doc_id=doc_id,
                source=source,
                module=module,
                file_size=file_size,
                chunk_count=chunk_count,
                version=version,
                complexity=complexity,
                landscape=landscape
            )
            db.add(document)
            db.commit()
            db.refresh(document)
            logger.info(f"✓ Document saved to database: {doc_id} (source: {source})")
            return document
        except Exception as e:
            logger.error(f"✗ Failed to save document {doc_id}: {type(e).__name__} — {e}")
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def get_total_document_count() -> int:
        """Get total number of documents in knowledge base"""
        db: Session = SessionLocal()
        try:
            count = db.query(Document).count()
            return count
        finally:
            db.close()

    @staticmethod
    def get_document_stats() -> dict:
        """Get document statistics from ChromaDB (actual source of truth)"""
        try:
            # Query ChromaDB directly for accurate count
            import chromadb
            from pathlib import Path

            BASE_DIR = Path(__file__).resolve().parent.parent
            CHROMA_DIR = BASE_DIR / "chroma_db"

            if not CHROMA_DIR.exists():
                return {
                    "total_documents": 0,
                    "by_module": {},
                    "total_chunks": 0
                }

            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            collection = client.get_or_create_collection(name="pdf_documents")

            # Get all metadata from ChromaDB
            data = collection.get()

            if not data or not data.get("metadatas"):
                return {
                    "total_documents": 0,
                    "by_module": {},
                    "total_chunks": 0
                }

            # Count unique documents and by module
            unique_docs = set()
            module_counts = {}

            for metadata in data.get("metadatas", []):
                doc_id = metadata.get("doc_id", "Unknown")
                unique_docs.add(doc_id)

                module = metadata.get("sap_module", "Unknown")
                module_counts[module] = module_counts.get(module, 0) + 1

            return {
                "total_documents": len(unique_docs),
                "by_module": module_counts,
                "total_chunks": len(data.get("ids", []))
            }
        except Exception as e:
            logger.warning(f"Could not get ChromaDB stats: {e}")
            # Fallback to database
            db: Session = SessionLocal()
            try:
                total = db.query(Document).count()
                modules = db.query(Document.module, func.count(Document.module)).group_by(Document.module).all()
                module_counts = {module: count for module, count in modules if module}
                total_chunks = db.query(func.sum(Document.chunk_count)).scalar() or 0

                return {
                    "total_documents": total,
                    "by_module": module_counts,
                    "total_chunks": total_chunks
                }
            finally:
                db.close()

    @staticmethod
    def get_all_documents() -> list[Document]:
        """Get all documents from knowledge base"""
        db: Session = SessionLocal()
        try:
            documents = db.query(Document).order_by(Document.ingested_at.desc()).all()
            return documents
        finally:
            db.close()
