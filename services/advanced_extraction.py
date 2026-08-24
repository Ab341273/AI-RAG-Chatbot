"""Advanced PDF extraction with table support using Tabula"""
import io
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List
from PyPDF2 import PdfReader
from services.logging_service import get_logger

logger = get_logger(__name__)

try:
    import tabula
    TABULA_AVAILABLE = True
except ImportError:
    logger.warning("Tabula not available, using PyPDF2 only")
    TABULA_AVAILABLE = False


def extract_text_with_tables(pdf_path: Path) -> Dict[str, Any]:
    """
    Extract text and tables from PDF using Tabula

    Returns:
        Dict with extracted_text, tables, metadata
    """
    try:
        logger.info(f"Starting extraction for {pdf_path.name}")

        # Phase 1: Extract tables using Tabula
        tables = []
        if TABULA_AVAILABLE:
            try:
                tables = _extract_tables_tabula(pdf_path)
                logger.info(f"Extracted {len(tables)} tables using Tabula")
            except Exception as e:
                logger.warning(f"Tabula extraction failed: {e}")

        # Phase 2: Extract text using PyPDF2
        text = _extract_text_pypdf(pdf_path)

        # Phase 3: Merge tables into text for better context
        if tables:
            text = _merge_tables_with_text(text, tables)

        return {
            "text": text,
            "tables": tables,
            "tables_preserved": len(tables) > 0,
            "metadata": {},
            "status": "success",
            "method": "tabula+pypdf2" if tables else "pypdf2"
        }

    except Exception as e:
        logger.error(f"Extraction failed for {pdf_path.name}: {e}")
        return _fallback_extraction(pdf_path)


def _extract_tables_tabula(pdf_path: Path) -> List[Dict[str, Any]]:
    """Extract tables from PDF using Tabula"""
    try:
        # Read all tables from PDF
        tables_list = tabula.read_pdf(
            str(pdf_path),
            pages="all",
            multiple_tables=True,
            guess=True,
            lattice=True
        )

        extracted_tables = []
        for idx, table_df in enumerate(tables_list):
            if table_df is not None and not table_df.empty:
                table_dict = {
                    "index": idx,
                    "type": "tabula_table",
                    "columns": table_df.columns.tolist(),
                    "rows": table_df.values.tolist(),
                    "content": table_df.to_string(),
                    "csv": table_df.to_csv(index=False)
                }
                extracted_tables.append(table_dict)

        logger.debug(f"Extracted {len(extracted_tables)} tables from {pdf_path.name}")
        return extracted_tables

    except Exception as e:
        logger.debug(f"Tabula extraction error: {e}")
        return []


def _extract_text_pypdf(pdf_path: Path) -> str:
    """Extract text from PDF using PyPDF2"""
    try:
        reader = PdfReader(pdf_path)
        text = "\n".join(
            page.extract_text() or "" for page in reader.pages
        )
        logger.debug(f"Extracted {len(text)} characters using PyPDF2")
        return text
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {e}")
        return ""


def _merge_tables_with_text(text: str, tables: List[Dict[str, Any]]) -> str:
    """Merge table data with extracted text for better context"""
    merged = text

    for idx, table in enumerate(tables):
        # Add table as CSV format for better LLM understanding
        csv_data = table.get('csv', '')
        if csv_data:
            merged += f"\n\n--- TABLE {idx + 1} (Structured Data) ---\n"
            merged += csv_data
            merged += "\n"

        # Also add formatted table content
        content = table.get('content', '')
        if content:
            merged += f"\n--- TABLE {idx + 1} (Formatted) ---\n"
            merged += content
            merged += "\n"

    return merged


def _fallback_extraction(pdf_path: Path) -> Dict[str, Any]:
    """Fallback extraction using PyPDF2 only"""
    try:
        text = _extract_text_pypdf(pdf_path)

        return {
            "text": text,
            "tables": [],
            "tables_preserved": False,
            "metadata": {},
            "status": "fallback",
            "method": "pypdf2"
        }
    except Exception as e:
        logger.error(f"Fallback extraction failed: {e}")
        return {
            "text": "",
            "tables": [],
            "tables_preserved": False,
            "metadata": {},
            "status": "failed",
            "method": "none",
            "error": str(e)
        }


def extract_tables_from_text(text: str) -> List[Dict[str, Any]]:
    """
    Parse table structures from extracted text
    Handles both Tabula markdown format and CSV format
    """
    tables = []
    lines = text.split("\n")

    # Look for TABLE markers from Tabula extraction
    for idx, line in enumerate(lines):
        if line.startswith("TABLE "):
            table_content = []
            col_line = ""

            # Extract columns
            if idx + 1 < len(lines) and "Columns:" in lines[idx + 1]:
                col_line = lines[idx + 1]

            # Extract data
            for j in range(idx + 2, min(idx + 50, len(lines))):
                if lines[j].startswith("TABLE "):
                    break
                if lines[j].strip():
                    table_content.append(lines[j])

            if table_content:
                tables.append({
                    "type": "extracted_table",
                    "content": "\n".join(table_content),
                    "columns_line": col_line
                })

    return tables
