from pathlib import Path
from typing import Any, Dict, List
import shutil  # CHANGE 1: Import shutil to move files to quarantine folder
import re  # PHASE 2: Regex for SAP metadata extraction

from langchain_text_splitters import RecursiveCharacterTextSplitter
from PyPDF2 import PdfReader
from sentence_transformers import SentenceTransformer
import chromadb

from services.logging_service import get_logger  # CHANGE 2: Import logger instead of using print()
from services.database_service import DatabaseService  # Track documents in database
from services.advanced_extraction import extract_text_with_tables, extract_tables_from_text
from services.enhanced_metadata import extract_enhanced_metadata

# CHANGE 3: Initialize logger for this module (will use existing logging_service)
logger = get_logger(__name__)

PDF_FOLDER = Path("data/pdfs")
PDFS_FAILED_FOLDER = Path("data/pdfs_failed")  # CHANGE 4: Add quarantine folder path for failed/corrupt PDFs
#CHROMA_DIR = Path("chroma_db")
BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# PHASE 2: SAP WRICEF field definitions
SAP_FIELDS = {
    "wricef_id": r"WRICEF\s+ID\s*[:=]\s*(.+?)(?:\n|$)",
    "sap_module": r"SAP\s+Module\s*[:=]\s*(.+?)(?:\n|$)",
    "t_code_method": r"T-Code/Method\s*[:=]\s*(.+?)(?:\n|$)",
    "project_code": r"Project\s+Code\s*[:=]\s*(.+?)(?:\n|$)",
    "object_type": r"Object\s+Type\s*[:=]\s*(.+?)(?:\n|$)",
    "badi_name": r"BAdI\s+Name\s*[:=]\s*(.+?)(?:\n|$)",
    "complexity": r"Complexity\s*[:=]\s*(.+?)(?:\n|$)",
    "landscape": r"Landscape\s*[:=]\s*(.+?)(?:\n|$)",
}


def _extract_sap_field(text: str, pattern: str, field_name: str, default: str = "Unknown") -> str:
    """
    PHASE 2: Helper to safely extract a single SAP field from PDF text using regex.

    Kyon ye function:
    - Regex match safe hai (try/except ke andar)
    - Empty string ko default se replace karta hai
    - Whitespace trim karta hai
    - Field name log mein include hota hai debugging ke liye
    """
    try:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            value = match.group(1).strip()
            if value:  # Agar value non-empty hai
                logger.debug(f"Extracted {field_name}: {value}")
                return value
        logger.debug(f"{field_name} not found in PDF, using default: {default}")
        return default
    except Exception as e:
        logger.warning(f"Error extracting {field_name}: {type(e).__name__} — {e}, using default: {default}")
        return default


def extract_module_from_filename(filename: str) -> str:
    """
    Extract SAP module from filename using pattern matching.

    Examples:
    - TSD_CO-CE-001_... → CO
    - TSD_TM-F-0030_... → TM
    - TSD_WM_F_001_... → WM
    - TSD_SD_E_001_... → SD

    Returns module code or "Unknown" if not detected.
    """
    import re

    # Pattern: 1-2 uppercase letters (optionally followed by - or _)
    # Must appear after "TSD_" or at start
    match = re.search(r'(?:TSD[_-])?([A-Z]{1,2})(?:[_-]|$)', filename)
    if match:
        module = match.group(1)
        logger.debug(f"Detected module '{module}' from filename: {filename}")
        return module

    logger.debug(f"Could not detect module from filename: {filename}")
    return "Unknown"


def extract_complexity_from_content(text: str) -> str:
    """
    PHASE 2: Extract complexity level from PDF content.
    Handles formats: "Complexity  High" or "Complexity: High" or "Complexity = High"
    """
    if not text:
        return "Unknown"

    # Search in entire text (fields can appear anywhere)
    # Pattern: "Complexity" followed by spaces/colons, then value
    patterns = [
        r'complexity\s+(?:[:=\s])*\s*(high|critical)',
        r'complexity\s+(?:[:=\s])*\s*(medium)',
        r'complexity\s+(?:[:=\s])*\s*(low|simple)',
    ]

    text_lower = text.lower()

    # Check High
    if re.search(patterns[0], text_lower, re.IGNORECASE):
        return "High"
    # Check Medium
    elif re.search(patterns[1], text_lower, re.IGNORECASE):
        return "Medium"
    # Check Low
    elif re.search(patterns[2], text_lower, re.IGNORECASE):
        return "Low"

    return "Unknown"


def extract_landscape_from_content(text: str) -> str:
    """
    PHASE 2: Extract landscape/environment from PDF content.
    Handles formats: "Landscape  S/4HANA Private Cloud" or "Landscape: Production"
    """
    if not text:
        return "Unknown"

    text_lower = text.lower()

    # Look for landscape mentions
    landscape_match = re.search(r'landscape\s+(?:[:=\s])*\s*([^;\n]+)', text_lower, re.IGNORECASE)
    if landscape_match:
        landscape_value = landscape_match.group(1).strip()

        # Normalize the value
        if 'production' in landscape_value or 's/4hana' in landscape_value:
            return "Production"
        elif 'qa' in landscape_value or 'quality' in landscape_value or 'test' in landscape_value:
            return "QA"
        elif 'dev' in landscape_value or 'development' in landscape_value:
            return "Development"
        else:
            # Return the actual value if it's meaningful
            return landscape_value[:30] if landscape_value else "Unknown"

    # Fallback patterns
    if re.search(r'environment\s+(?:[:=\s])*\s*production', text_lower, re.IGNORECASE):
        return "Production"

    return "Unknown"


def extract_version_from_content(text: str) -> str:
    """
    PHASE 2: Extract version number from PDF content.
    Look for "Version: 1.0" or "v1.0".
    """
    if not text:
        return "Unknown"

    first_section = text[:300]

    # Look for version patterns
    version_match = re.search(r'(?:version|v)\s*[:=]?\s*(\d+\.\d+)', first_section, re.IGNORECASE)
    if version_match:
        return version_match.group(1)

    return "Unknown"


def extract_sap_metadata(text: str, filename: str = "") -> Dict[str, str]:
    """
    HYBRID EXTRACTION: Filename + Smart Content Parsing

    Phase 1: Filename-based extraction (Fast, 100% reliable)
    Phase 2: Content-based extraction (Smart parsing of first 500 chars)

    Returns dict with fields: wricef_id, sap_module, t_code_method, project_code,
    object_type, badi_name, complexity, landscape.
    """
    logger.debug("Starting HYBRID SAP metadata extraction")

    # PHASE 1: Text patterns
    metadata = {}
    for field_name, pattern in SAP_FIELDS.items():
        metadata[field_name] = _extract_sap_field(text, pattern, field_name)

    # PHASE 2: Filename-based extraction (Most reliable)
    if filename:
        extracted_module = extract_module_from_filename(filename)
        if extracted_module != "Unknown":
            metadata["sap_module"] = extracted_module
            logger.debug(f"Module extracted from filename: {extracted_module}")

    # PHASE 2: Smart content parsing (Enhancement)
    logger.debug("Phase 2: Starting smart content parsing...")

    # Complexity extraction
    if metadata.get("complexity") == "Unknown":
        complexity = extract_complexity_from_content(text)
        if complexity != "Unknown":
            metadata["complexity"] = complexity
            logger.debug(f"Complexity extracted from content: {complexity}")

    # Landscape extraction
    if metadata.get("landscape") == "Unknown":
        landscape = extract_landscape_from_content(text)
        if landscape != "Unknown":
            metadata["landscape"] = landscape
            logger.debug(f"Landscape extracted from content: {landscape}")

    # Version extraction (bonus)
    version = extract_version_from_content(text)
    if version != "Unknown":
        metadata["version"] = version
        logger.debug(f"Version extracted: {version}")

    # Log extracted metadata at INFO level (for audit)
    logger.info(
        f"SAP metadata extracted [HYBRID]: "
        f"WRICEF_ID={metadata['wricef_id']}, "
        f"Module={metadata['sap_module']}, "
        f"Complexity={metadata['complexity']}, "
        f"Landscape={metadata['landscape']}"
    )

    return metadata


def load_pdf_documents(pdf_folder: Path = PDF_FOLDER) -> Dict[str, Any]:
    # CHANGE 5: Initialize counters to track success/failure/skipped files
    docs: List[Dict[str, Any]] = []
    counters = {
        "total_discovered": 0,
        "success": 0,
        "failed": 0,
    }
    failed_files = []  # CHANGE 6: Track which files failed and why (for summary at end)

    if not pdf_folder.exists():
        raise FileNotFoundError(f"PDF folder not found: {pdf_folder}")

    # CHANGE 7: Case-insensitive PDF discovery (.pdf aur .PDF dono ko catch karo)
    # MATURE FIX: Windows filesystem case-insensitive hai
    # glob("*.pdf") और glob("*.PDF") दोनों same files match कर सकते हैं
    # Use set to deduplicate, then convert to sorted list
    # Example: "file.pdf" matches both "*.pdf" and "*.PDF" on Windows
    all_pdf_paths_set = set(pdf_folder.glob("*.pdf")) | set(pdf_folder.glob("*.PDF"))
    all_pdf_paths = sorted(list(all_pdf_paths_set))

    # CHANGE 8: If no PDFs found, log WARNING aur empty list return karo (crash nahi karna)
    if not all_pdf_paths:
        logger.warning(f"No PDF files found in {pdf_folder}")
        return {"docs": docs, "counters": counters, "failed_files": failed_files}

    counters["total_discovered"] = len(all_pdf_paths)
    logger.info(f"Discovered {counters['total_discovered']} PDF(s) in {pdf_folder}")

    # CHANGE 9: Per-file try/except block taake ek file fail ho to baaki continue ho
    for path in all_pdf_paths:
        logger.info(f"Processing {path.name}")
        try:
            # CHANGE 10: Step 1 - File size check (0-byte file ko immediately reject karo, efficient hai)
            file_size = path.stat().st_size
            if file_size == 0:
                error_msg = "zero-byte file"
                logger.error(f"{path.name}: {error_msg}")
                failed_files.append({"file": path.name, "reason": error_msg})
                counters["failed"] += 1
                _move_to_quarantine(path, error_msg)
                continue

            # CHANGE 11: Step 2 - Magic-bytes check (PDF header validation)
            # Valid PDF files start with %PDF signature. Ye check expensive PdfReader call se pehle karo.
            with open(path, "rb") as f:
                header = f.read(4)
                if not header.startswith(b"%PDF"):
                    error_msg = "not a valid PDF (invalid header)"
                    logger.error(f"{path.name}: {error_msg}")
                    failed_files.append({"file": path.name, "reason": error_msg})
                    counters["failed"] += 1
                    _move_to_quarantine(path, error_msg)
                    continue

            # CHANGE 12: Step 3 - Advanced extraction with table support (Marker)
            extraction_result = extract_text_with_tables(path)
            text = extraction_result["text"]
            extraction_method = extraction_result["method"]

            # CHANGE 13: Extract tables if present
            tables = []
            if extraction_result.get("tables_preserved"):
                tables = extract_tables_from_text(text)
                logger.info(f"{path.name}: extracted {len(tables)} tables")

            # CHANGE 14: Check if extracted text is empty/whitespace (warning, nahi error)
            if not text or text.isspace():
                logger.warning(f"{path.name}: no extractable text (method: {extraction_method})")

            # CHANGE 15: File successfully processed - append to docs aur counter increment karo
            # PHASE 2: Extract enhanced SAP metadata from text (table-aware)
            sap_metadata = extract_enhanced_metadata(text, filename=path.name, tables=tables)
            sap_metadata["extraction_method"] = extraction_method

            # PHASE 2: Use WRICEF_ID as primary doc_id (if available, else use filename)
            doc_id = sap_metadata.get("wricef_id", path.stem)
            if doc_id == "Unknown":
                doc_id = path.stem
                logger.warning(f"{path.name}: WRICEF_ID not found, using filename as doc_id")

            docs.append(
                {
                    "doc_id": doc_id,
                    "source": path.name,
                    "type": "pdf",
                    "content": text,
                    # PHASE 2: Add SAP fields to document record (with defaults for missing fields)
                    "wricef_id": sap_metadata.get("wricef_id", "Unknown"),
                    "sap_module": sap_metadata.get("sap_module", "Unknown"),
                    "t_code_method": sap_metadata.get("t_code_method", "Unknown"),
                    "project_code": sap_metadata.get("project_code", "Unknown"),
                    "object_type": sap_metadata.get("object_type", "Unknown"),
                    "badi_name": sap_metadata.get("badi_name", "Unknown"),
                    "complexity": sap_metadata.get("complexity", "Unknown"),
                    "landscape": sap_metadata.get("landscape", "Unknown"),
                }
            )
            counters["success"] += 1
            logger.info(f"{path.name}: successfully processed (WRICEF_ID: {doc_id})")

        # CHANGE 17: Catch any PDF reading exceptions (PyPDF2 errors or other unexpected errors)
        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"{path.name}: failed to read PDF — {error_msg}")
            failed_files.append({"file": path.name, "reason": error_msg})
            counters["failed"] += 1
            _move_to_quarantine(path, error_msg)
            continue

    # CHANGE 18: Return dict containing docs, counters, aur failed_files (na sirf docs)
    # Run_pipeline mein summary print karne ke liye ye sab data chahiye
    return {"docs": docs, "counters": counters, "failed_files": failed_files}


def _move_to_quarantine(path: Path, reason: str) -> None:
    """
    CHANGE 19: Helper function to move failed/corrupt PDF to quarantine folder.
    Kyon: Failed files ko source folder se alag rakh do taake dobara run pe try na ho.
    Ye function try/except mein hai, taake agar move fail ho (permission issue etc) to sirf log karo,
    pipeline ko crash mat karo.
    """
    try:
        PDFS_FAILED_FOLDER.mkdir(parents=True, exist_ok=True)
        shutil.move(str(path), str(PDFS_FAILED_FOLDER / path.name))
        logger.info(f"{path.name}: moved to quarantine folder ({reason})")
    except Exception as e:
        logger.error(f"{path.name}: could not move to quarantine — {type(e).__name__}: {e}")


def chunk_documents(
    docs: List[Dict[str, Any]],
    chunk_size: int = 200,
    chunk_overlap: int = 100,
) -> List[Dict[str, Any]]:
    """
    PHASE 2: Split documents into chunks, preserve SAP metadata in each chunk.

    Kyon preserve metadata:
    - Chunks inherit SAP fields from parent document
    - RAG queries filter by SAP_MODULE, COMPLEXITY etc
    - Audit trail: know which WRICEF_ID chunk came from
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    chunks: List[Dict[str, Any]] = []
    for doc in docs:
        logger.debug(f"Chunking document: {doc['doc_id']} (source: {doc['source']})")
        pieces = splitter.split_text(doc["content"])
        logger.info(f"{doc['doc_id']}: created {len(pieces)} chunks")

        for idx, piece in enumerate(pieces, start=1):
            # FIX: Include filename in chunk_id to ensure uniqueness
            # Kyon: Multiple PDFs can have same WRICEF_ID (CO-CE-002_v1.pdf, CO-CE-002_v2.pdf)
            # Agar sirf WRICEF_ID use karenge to duplicate chunk_ids ban jayengi
            # Solution: Use filename stem (without .pdf) + WRICEF_ID + index
            filename_stem = Path(doc["source"]).stem
            unique_chunk_id = f"{filename_stem}__{doc['doc_id']}__{idx}"

            chunks.append(
                {
                    "doc_id": doc["doc_id"],
                    "source": doc["source"],
                    "chunk_id": unique_chunk_id,
                    "content": piece,
                    # PHASE 2: Preserve SAP metadata in chunks (for filtering in RAG)
                    "wricef_id": doc.get("wricef_id", "Unknown"),
                    "sap_module": doc.get("sap_module", "Unknown"),
                    "complexity": doc.get("complexity", "Unknown"),
                    "landscape": doc.get("landscape", "Unknown"),
                    "version": doc.get("version", "Unknown"),
                }
            )

    logger.info(f"Total chunks created from {len(docs)} documents: {len(chunks)}")
    return chunks


def embed_chunks(
    chunks: List[Dict[str, Any]],
    model_name: str = EMBEDDING_MODEL,
) -> Dict[str, Any]:
    """
    PHASE 2: Generate embeddings for chunks using SentenceTransformer.

    Returns dict with:
    - embedded_chunks: chunks with embeddings added
    - embedding_stats: track which chunks/documents got embedded

    Kyon return dict:
    - Track embedding success/failure per document
    - Log detailed info about embedding process
    - Return stats for summary reporting
    """
    logger.info(f"Starting embedding generation using model: {model_name}")
    logger.info(f"Embedding {len(chunks)} chunks...")

    try:
        model = SentenceTransformer(model_name)
        logger.debug(f"Model loaded successfully: {model_name}")
    except Exception as e:
        logger.error(f"Failed to load embedding model {model_name}: {type(e).__name__} — {e}")
        raise

    texts = [chunk["content"] for chunk in chunks]

    try:
        embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        logger.debug(f"Generated embeddings shape: {embeddings.shape}")
    except Exception as e:
        logger.error(f"Embedding generation failed: {type(e).__name__} — {e}")
        raise

    if len(embeddings) != len(chunks):
        error_msg = f"Embedding count ({len(embeddings)}) does not match chunk count ({len(chunks)})"
        logger.error(error_msg)
        raise ValueError(error_msg)

    # PHASE 2: Track which documents got embedded
    embedded_docs = set()
    for chunk, emb in zip(chunks, embeddings):
        chunk["embedding"] = emb.tolist() if hasattr(emb, "tolist") else emb
        embedded_docs.add(chunk["doc_id"])

    logger.info(f"Successfully embedded {len(embeddings)} chunks from {len(embedded_docs)} unique documents")

    # Log which documents were embedded
    for doc_id in sorted(embedded_docs):
        doc_chunks = [c for c in chunks if c["doc_id"] == doc_id]
        logger.debug(f"Document {doc_id}: {len(doc_chunks)} chunks embedded")

    return {
        "embedded_chunks": chunks,
        "embedding_stats": {
            "total_chunks": len(chunks),
            "unique_documents": len(embedded_docs),
            "embedded_doc_ids": sorted(list(embedded_docs)),
        }
    }


def save_to_chroma(
    chunks: List[Dict[str, Any]],
    persist_dir: Path = CHROMA_DIR,
    collection_name: str = "pdf_documents",
) -> Dict[str, Any]:
    """
    PHASE 2: Save embedded chunks to Chroma vector database.

    Returns dict with save stats for logging/auditing.

    Kyon structured metadata:
    - Preserve SAP fields in Chroma metadata (for filtering)
    - WRICEF_ID, complexity, landscape queryable
    - Source traceability
    """
    logger.info(f"Preparing to save {len(chunks)} chunks to Chroma")

    try:
        persist_dir.mkdir(parents=True, exist_ok=True)
        logger.debug(f"Chroma directory ready: {persist_dir}")

        client = chromadb.PersistentClient(path=str(persist_dir))
        collection = client.get_or_create_collection(name=collection_name)
        logger.debug(f"Chroma collection '{collection_name}' ready")
    except Exception as e:
        logger.error(f"Failed to initialize Chroma: {type(e).__name__} — {e}")
        raise

    # PHASE 2: Prepare metadata with SAP fields (for queryable Chroma)
    metadatas = []
    for chunk in chunks:
        metadata = {
            "doc_id": chunk["doc_id"],
            "source": chunk["source"],
            "wricef_id": chunk.get("wricef_id", "Unknown"),
            "sap_module": chunk.get("sap_module", "Unknown"),
            "complexity": chunk.get("complexity", "Unknown"),
            "landscape": chunk.get("landscape", "Unknown"),
            "version": chunk.get("version", "Unknown"),
        }
        metadatas.append(metadata)

    try:
        # FIX: Batch upsert to respect ChromaDB max batch size (5461)
        # Kyon: ChromaDB has memory limits - ek saath sab insert nahi kar sakte
        batch_size = 5000
        total_saved = 0

        for i in range(0, len(chunks), batch_size):
            batch_chunks = chunks[i:i + batch_size]
            batch_metadatas = metadatas[i:i + batch_size]

            collection.upsert(
                ids=[chunk["chunk_id"] for chunk in batch_chunks],
                metadatas=batch_metadatas,
                documents=[chunk["content"] for chunk in batch_chunks],
                embeddings=[chunk["embedding"] for chunk in batch_chunks],
            )
            total_saved += len(batch_chunks)
            logger.info(f"Batch saved: {total_saved}/{len(chunks)} chunks")

        logger.info(f"Successfully saved all {len(chunks)} chunks to Chroma collection '{collection_name}' (batched upsert)")
    except Exception as e:
        logger.error(f"Failed to add chunks to Chroma: {type(e).__name__} — {e}")
        raise
    finally:
        try:
            client.close()
            logger.debug("Chroma client closed")
        except Exception as e:
            logger.warning(f"Error closing Chroma client: {type(e).__name__} — {e}")

    # PHASE 2: Return save statistics
    saved_doc_ids = set(chunk["doc_id"] for chunk in chunks)

    # Track documents in database
    unique_sources = {}
    for chunk in chunks:
        source = chunk.get("source")
        doc_id = chunk.get("doc_id")
        if source and doc_id:
            if doc_id not in unique_sources:
                unique_sources[doc_id] = {
                    "source": source,
                    "module": chunk.get("sap_module", "Unknown"),
                    "version": chunk.get("version", "Unknown"),
                    "complexity": chunk.get("complexity", "Unknown"),
                    "landscape": chunk.get("landscape", "Unknown"),
                    "chunks": 0
                }
            unique_sources[doc_id]["chunks"] += 1

    # Save documents to database (with upsert logic for duplicates)
    saved_to_db_count = 0
    failed_db_saves = []

    for doc_id, info in unique_sources.items():
        try:
            # Try to add document
            # If duplicate exists, it will be handled by the service layer
            result = DatabaseService.add_document(
                doc_id=doc_id,
                source=info["source"],
                module=info["module"],
                chunk_count=info["chunks"],
                version=info["version"],
                complexity=info["complexity"],
                landscape=info["landscape"]
            )
            saved_to_db_count += 1
        except Exception as e:
            # Log database save failures explicitly
            error_msg = f"{type(e).__name__}: {e}"
            logger.error(f"✗ Failed to save document {doc_id} to database — {error_msg}")
            failed_db_saves.append({"doc_id": doc_id, "error": error_msg})

    if failed_db_saves:
        logger.warning(f"⚠ {len(failed_db_saves)} documents failed to save to database (but were saved to ChromaDB)")
        for failure in failed_db_saves:
            logger.warning(f"  - {failure['doc_id']}: {failure['error']}")

    return {
        "chunks_saved": len(chunks),
        "documents_saved": len(unique_sources),
        "documents_saved_to_db": saved_to_db_count,
        "documents_failed_db": len(failed_db_saves),
        "failed_db_saves": failed_db_saves,
        "saved_doc_ids": sorted(list(unique_sources.keys())),
        "collection_name": collection_name,
        "persist_dir": str(persist_dir),
    }


def run_pipeline() -> None:
    # CHANGE 20: Load PDF documents (ab ye dict return karta hai, na sirf docs list)
    result = load_pdf_documents()
    pdf_docs = result["docs"]
    counters = result["counters"]
    failed_files = result["failed_files"]

    # CHANGE 21: Log ke through print() hatao (structured logging use karo)
    logger.info(f"Loaded {len(pdf_docs)} PDFs")

    # CHANGE 22: Agar koi PDF successfully load nahi hua, pipeline continue na karo
    # (agar fail counter 0 se zyada hai to at least partial success to hai)
    if len(pdf_docs) == 0:
        logger.error("No valid PDFs to process. Pipeline aborted.")
        _print_summary(counters, failed_files)
        return

    chunks = chunk_documents(pdf_docs)
    logger.info(f"Created {len(chunks)} chunks")

    # PHASE 2: embed_chunks now returns dict with stats
    embedding_result = embed_chunks(chunks)
    embedded_chunks = embedding_result["embedded_chunks"]
    embedding_stats = embedding_result["embedding_stats"]

    logger.info(f"Embedded {embedding_stats['total_chunks']} chunks from {embedding_stats['unique_documents']} documents")
    logger.debug(f"Embedded documents: {embedding_stats['embedded_doc_ids']}")

    # PHASE 2: save_to_chroma now returns dict with stats
    save_result = save_to_chroma(embedded_chunks)

    logger.info(f"Saved to Chroma: {save_result['chunks_saved']} chunks, {save_result['documents_saved']} documents")
    logger.debug(f"Saved documents: {save_result['saved_doc_ids']}")

    # PHASE 2: Check if all embedded documents were saved
    if set(embedding_stats["embedded_doc_ids"]) == set(save_result["saved_doc_ids"]):
        logger.info("✓ All embedded documents successfully saved to Chroma")
    else:
        missing_docs = set(embedding_stats["embedded_doc_ids"]) - set(save_result["saved_doc_ids"])
        logger.error(f"✗ Some documents not saved to Chroma: {missing_docs}")

    # CHANGE 23: End mein summary print karo (total/success/failed counts aur failed files list)
    _print_summary(counters, failed_files, embedding_stats, save_result)


def _print_summary(
    counters: Dict[str, int],
    failed_files: List[Dict[str, str]],
    embedding_stats: Dict[str, Any] = None,
    save_stats: Dict[str, Any] = None,
) -> None:
    """
    CHANGE 24: Helper function to print ingestion summary at end of run.
    PHASE 2: Now includes embedding and Chroma save statistics.

    Kyon: Production mein ye audit trail important hai - total files, success/failed counts,
    embedding stats (which PDFs got embedded), save stats (which PDFs in Chroma).
    Logs mein ye data rehta hai, dobara debugging mein use ho sakta hai.
    """
    logger.info("=" * 70)
    logger.info("INGESTION PIPELINE SUMMARY")
    logger.info("=" * 70)

    # PDF Loading phase
    logger.info("Phase 1: PDF Discovery & Loading")
    logger.info("-" * 70)
    logger.info(f"  Total discovered: {counters['total_discovered']}")
    logger.info(f"  Success: {counters['success']}")
    logger.info(f"  Failed (quarantined): {counters['failed']}")

    if failed_files:
        logger.info(f"  Failed files ({len(failed_files)}):")
        for f in failed_files:
            logger.info(f"    - {f['file']}: {f['reason']}")

    # Embedding phase (Phase 2)
    if embedding_stats:
        logger.info("Phase 2: Embedding")
        logger.info("-" * 70)
        logger.info(f"  Total chunks embedded: {embedding_stats['total_chunks']}")
        logger.info(f"  Unique documents embedded: {embedding_stats['unique_documents']}")
        logger.info(f"  Document IDs: {embedding_stats['embedded_doc_ids']}")

    # Chroma save phase (Phase 2)
    if save_stats:
        logger.info("Phase 3: Vector Store & Database")
        logger.info("-" * 70)
        logger.info(f"  Chunks saved to Chroma: {save_stats['chunks_saved']}")
        logger.info(f"  Documents saved to Chroma: {save_stats['documents_saved']}")
        logger.info(f"  Documents saved to PostgreSQL: {save_stats.get('documents_saved_to_db', 'N/A')}")
        if save_stats.get('documents_failed_db', 0) > 0:
            logger.warning(f"  ⚠ Documents failed to save to PostgreSQL: {save_stats['documents_failed_db']}")
            for failure in save_stats.get('failed_db_saves', []):
                logger.warning(f"    - {failure['doc_id']}: {failure['error']}")
        logger.info(f"  Document IDs: {save_stats['saved_doc_ids']}")
        logger.info(f"  Collection: {save_stats['collection_name']}")
        logger.info(f"  Location: {save_stats['persist_dir']}")

    logger.info("=" * 70)
    logger.info("Pipeline execution complete!")
    logger.info("=" * 70)


def test_module_retrieval(test_query: str = "How to create purchase order?", module_id: str = "MM"):
    """
    PHASE 3: Test module-based retrieval with filtering.

    Demonstrates how to:
    1. Generate embedding for query
    2. Retrieve from Chroma with module filter
    3. Prevent hallucination by filtering to specific module

    Kyon ye important hai:
    - Ingestion done (PDFs chunked, embedded, saved)
    - Ab retrieval phase: query karte waqt module filter laga do
    - Ye LLM ko accurate context deta hai
    - Hallucination automatically kam ho jata hai

    Args:
        test_query: Test query to retrieve
        module_id: SAP module to filter by (CO, FI, MM, TM, etc.)
    """
    from sentence_transformers import SentenceTransformer
    from services.module_retrieval_service import ModuleRetrievalService

    logger.info("=" * 70)
    logger.info("PHASE 3: Testing Module-Based Retrieval")
    logger.info("=" * 70)

    try:
        # Initialize retrieval service
        retrieval_service = ModuleRetrievalService()
        logger.info(f"ModuleRetrievalService initialized")

        # Get collection stats
        stats = retrieval_service.get_collection_stats()
        logger.info(f"Collection stats: {stats}")

        # First, clear and re-ingest documents with proper module extraction
        logger.info("Re-ingesting documents with proper module extraction...")
        result = load_pdf_documents()
        pdf_docs = result["docs"]
        chunks = chunk_documents(pdf_docs)
        embedding_result = embed_chunks(chunks)
        save_result = save_to_chroma(embedding_result["embedded_chunks"])
        logger.info(f"Re-ingestion complete: {save_result['documents_saved']} documents saved with proper module metadata")

        # Generate embedding for query
        logger.info(f"Generating embedding for query: '{test_query}'")
        model = SentenceTransformer(EMBEDDING_MODEL)
        query_embedding = model.encode([test_query], convert_to_numpy=True)[0].tolist()
        logger.debug(f"Query embedding generated (dimension: {len(query_embedding)})")

        # Retrieve with module filter
        logger.info(f"Retrieving documents from module: {module_id}")
        results = retrieval_service.query_by_module(
            query_text=test_query,
            query_embedding=query_embedding,
            module_id=module_id,
            n_results=3,
        )

        # Display results
        logger.info("=" * 70)
        logger.info("RETRIEVAL RESULTS")
        logger.info("=" * 70)
        logger.info(f"Query: {results['query']}")
        logger.info(f"Module: {results['module_name']} ({results['module_id']})")
        logger.info(f"Results found: {results['count']}")
        logger.info(f"Result quality: {results['quality']}")
        logger.info("-" * 70)

        # Show retrieved chunks
        for idx, (doc_id, content, metadata, distance) in enumerate(
            zip(
                results["ids"],
                results["documents"],
                results["metadatas"],
                results["distances"],
            ),
            1,
        ):
            logger.info(f"\nResult {idx}:")
            logger.info(f"  Chunk ID: {doc_id}")
            logger.info(f"  WRICEF_ID: {metadata.get('wricef_id', 'Unknown')}")
            logger.info(f"  Module: {metadata.get('sap_module', 'Unknown')}")
            logger.info(f"  Complexity: {metadata.get('complexity', 'Unknown')}")
            logger.info(f"  Distance (relevance): {distance:.4f}")
            logger.info(f"  Content preview: {content[:200]}...")

        logger.info("=" * 70)

        # Close service
        retrieval_service.close()
        logger.info("Module retrieval test completed successfully!")

    except Exception as e:
        logger.error(f"Module retrieval test failed: {type(e).__name__} — {e}", exc_info=True)
        raise


if __name__ == "__main__":
    # Ingestion pipeline
    run_pipeline()

    # Optional: Test retrieval with module filtering
    # Uncomment to test retrieval
    # test_module_retrieval(test_query="How to create purchase order?", module_id="MM")
    # test_module_retrieval(test_query="How to post in GL?", module_id="FI")
    # test_module_retrieval(test_query="Cost center allocation?", module_id="CO")