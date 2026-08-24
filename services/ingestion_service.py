"""Ingestion service for handling PDF uploads and processing"""
import os
import shutil
from pathlib import Path
from typing import Dict, Any
from ingestion.pipeline import run_pipeline, load_pdf_documents, chunk_documents, embed_chunks, save_to_chroma
from services.logging_service import get_logger

logger = get_logger(__name__)

PDF_FOLDER = Path(__file__).resolve().parent.parent / "data" / "pdfs"


def get_ingestion_status() -> Dict[str, Any]:
    """Get current ingestion status - total docs processed"""
    try:
        if not PDF_FOLDER.exists():
            return {"total_docs": 0, "status": "No PDFs folder"}

        pdf_files = list(PDF_FOLDER.glob("*.pdf")) + list(PDF_FOLDER.glob("*.PDF"))
        pdf_files = list(set(pdf_files))  # Remove duplicates

        return {
            "total_docs": len(pdf_files),
            "status": "ready",
            "files": [f.name for f in sorted(pdf_files)]
        }
    except Exception as e:
        logger.error(f"Error getting ingestion status: {e}")
        return {"total_docs": 0, "status": "error", "error": str(e)}


def handle_pdf_upload(uploaded_files) -> Dict[str, Any]:
    """
    Handle uploaded PDF files and add to ingestion folder

    Args:
        uploaded_files: Streamlit uploaded_file objects

    Returns:
        Dict with status, uploaded count, and any errors
    """
    if not uploaded_files:
        return {"success": False, "message": "No files uploaded"}

    try:
        PDF_FOLDER.mkdir(parents=True, exist_ok=True)
        uploaded_count = 0
        errors = []

        for uploaded_file in uploaded_files:
            try:
                file_path = PDF_FOLDER / uploaded_file.name

                # Save uploaded file
                with open(file_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                uploaded_count += 1
                logger.info(f"Uploaded: {uploaded_file.name}")
            except Exception as e:
                error_msg = f"{uploaded_file.name}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg)

        return {
            "success": True,
            "uploaded_count": uploaded_count,
            "errors": errors,
            "message": f"Uploaded {uploaded_count} file(s)"
        }
    except Exception as e:
        logger.error(f"Error handling uploads: {e}")
        return {"success": False, "message": f"Upload failed: {str(e)}", "errors": [str(e)]}


def run_full_ingestion() -> Dict[str, Any]:
    """
    Run complete ingestion pipeline

    Returns:
        Dict with ingestion results and statistics
    """
    try:
        logger.info("Starting full ingestion pipeline...")

        # Load PDFs
        result = load_pdf_documents()
        pdf_docs = result["docs"]
        counters = result["counters"]

        if not pdf_docs:
            return {
                "success": False,
                "message": "No PDFs found to process",
                "stats": counters
            }

        # Chunk documents
        chunks = chunk_documents(pdf_docs)

        # Embed chunks
        embedding_result = embed_chunks(chunks)
        embedded_chunks = embedding_result["embedded_chunks"]

        # Save to Chroma
        save_result = save_to_chroma(embedded_chunks)

        return {
            "success": True,
            "message": "Ingestion completed successfully",
            "stats": {
                "pdf_docs": len(pdf_docs),
                "chunks_created": len(chunks),
                "chunks_embedded": len(embedded_chunks),
                "chunks_saved": save_result["chunks_saved"],
                "documents_saved": save_result["documents_saved"],
                "documents_saved_to_db": save_result.get("documents_saved_to_db", 0),
                "documents_failed_db": save_result.get("documents_failed_db", 0)
            },
            "counters": counters,
            "save_details": save_result
        }
    except Exception as e:
        logger.error(f"Ingestion pipeline error: {e}", exc_info=True)
        return {
            "success": False,
            "message": f"Ingestion failed: {str(e)}",
            "error": str(e)
        }
