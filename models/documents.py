from sqlalchemy import Column, String, DateTime, Integer
from datetime import datetime
from config.Database import Base


class Document(Base):
    """Track ingested documents in the knowledge base."""

    __tablename__ = "documents"

    # Primary identifier
    doc_id = Column(String(255), primary_key=True, index=True)

    # File information
    source = Column(String(255), nullable=False, index=True)  # Filename
    module = Column(String(50), nullable=True)  # SAP module (CO, TM, FI, etc.)

    # Document metadata
    file_size = Column(Integer, nullable=True)  # File size in bytes
    chunk_count = Column(Integer, default=0)  # Number of chunks created
    version = Column(String(50), nullable=True)  # Document version (e.g., 1.0)
    complexity = Column(String(50), nullable=True)  # Complexity level (High/Medium/Low)
    landscape = Column(String(50), nullable=True)  # Environment (Production/QA/Dev)

    # Tracking
    ingested_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<Document(doc_id='{self.doc_id}', source='{self.source}', module='{self.module}')>"
