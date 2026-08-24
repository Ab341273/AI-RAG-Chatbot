"""Enhanced metadata extraction with table awareness"""
import re
from typing import Dict, Any, List
from services.logging_service import get_logger

logger = get_logger(__name__)

# Enhanced patterns for table-aware extraction
SAP_PATTERNS = {
    "wricef_id": [
        r"(?:WRICEF|ID|Document ID)[:\s]+([A-Z]{2}[-_][A-Z]{2}[-_]\d{3}[-\w]*)",
        r"([A-Z]{2}[-_][A-Z]{2}[-_]\d{3}(?:[-_][A-Z])?)[\s|]",
        r"\|?\s*([A-Z]{2}[-_][A-Z]{2}[-_]\d{3}[-\w]*)\s*\|",
    ],
    "sap_module": [
        r"(?:Module|SAP Module)[:\s]+([A-Z]{2})",
        r"^(CO|TM|SD|WM)[-_]",
        r"\|(CO|TM|SD|WM)\|",
    ],
    "complexity": [
        r"(?:Complexity|Level)[:\s]+(Low|Medium|High|Critical)",
        r"\|(Low|Medium|High|Critical)\|",
    ],
    "landscape": [
        r"(?:Landscape|Environment)[:\s]+(DEV|QA|PROD|TEST|SANDBOX)",
        r"\|(DEV|QA|PROD|TEST|SANDBOX)\|",
    ],
}


def extract_enhanced_metadata(
    text: str,
    filename: str = "",
    tables: List[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    Extract metadata with table awareness

    Args:
        text: Extracted document text
        filename: Original filename
        tables: Extracted tables from document

    Returns:
        Dict with all extracted metadata
    """
    logger.debug(f"Extracting enhanced metadata from {filename}")

    metadata = {
        "wricef_id": "Unknown",
        "sap_module": "Unknown",
        "complexity": "Unknown",
        "landscape": "Unknown",
        "version": "Unknown",
        "t_code_method": "Unknown",
        "project_code": "Unknown",
        "object_type": "Unknown",
        "badi_name": "Unknown",
        "extraction_source": "unknown"
    }

    # Phase 1: Text-based extraction (all patterns)
    metadata = _extract_from_text(text, metadata)

    # Phase 2: Table-based extraction (if tables exist)
    if tables:
        metadata = _extract_from_tables(tables, metadata)

    # Phase 3: Filename-based extraction (override if found)
    metadata = _extract_from_filename(filename, metadata)

    # Phase 4: Cross-validation
    metadata = _validate_metadata(metadata)

    logger.info(
        f"Metadata extracted: "
        f"ID={metadata['wricef_id']}, "
        f"Module={metadata['sap_module']}, "
        f"Source={metadata['extraction_source']}"
    )

    return metadata


def _extract_from_text(
    text: str,
    metadata: Dict[str, str]
) -> Dict[str, str]:
    """Extract metadata from document text using multiple patterns"""

    for field, patterns in SAP_PATTERNS.items():
        if metadata[field] != "Unknown":
            continue

        for pattern in patterns:
            try:
                matches = re.findall(pattern, text, re.IGNORECASE | re.MULTILINE)
                if matches:
                    metadata[field] = matches[0].upper()
                    logger.debug(f"Text match for {field}: {metadata[field]}")
                    break
            except Exception as e:
                logger.debug(f"Pattern error for {field}: {e}")

    metadata["extraction_source"] = "text"
    return metadata


def _extract_from_tables(
    tables: List[Dict[str, Any]],
    metadata: Dict[str, str]
) -> Dict[str, str]:
    """Extract metadata from table structures"""

    for table in tables:
        table_text = table.get("content", "")
        table_csv = table.get("csv", "")

        # Combine content and CSV for better matching
        combined_text = table_text + "\n" + table_csv

        for field, patterns in SAP_PATTERNS.items():
            if metadata[field] != "Unknown":
                continue

            for pattern in patterns:
                try:
                    # Try both table content and CSV
                    matches = re.findall(
                        pattern,
                        combined_text,
                        re.IGNORECASE | re.MULTILINE
                    )
                    if matches:
                        metadata[field] = matches[0].upper()
                        logger.debug(f"Table match for {field}: {metadata[field]}")
                        metadata["extraction_source"] = "table"
                        break
                except Exception as e:
                    logger.debug(f"Table pattern error: {e}")

        # Also try cell-by-cell matching for table rows
        if "rows" in table:
            for row in table.get("rows", []):
                for cell in row:
                    cell_str = str(cell).upper()
                    # Check if cell contains module code
                    if cell_str in ["CO", "TM", "SD", "WM"] and metadata["sap_module"] == "Unknown":
                        metadata["sap_module"] = cell_str
                        metadata["extraction_source"] = "table_cell"
                    # Check for ID patterns
                    if re.match(r"[A-Z]{2}-[A-Z]{2}-\d{3}", cell_str) and metadata["wricef_id"] == "Unknown":
                        metadata["wricef_id"] = cell_str
                        metadata["extraction_source"] = "table_cell"

    return metadata


def _extract_from_filename(
    filename: str,
    metadata: Dict[str, str]
) -> Dict[str, str]:
    """Extract metadata from filename as fallback"""

    if not filename:
        return metadata

    # Parse filename format: TSD_CO-CE-002_description.pdf
    parts = filename.replace(".pdf", "").split("_")

    # Extract module (CO, TM, SD, WM)
    for part in parts:
        if part.upper() in ["CO", "TM", "SD", "WM"]:
            metadata["sap_module"] = part.upper()
            logger.debug(f"Module from filename: {part.upper()}")
            break

    # Extract WRICEF ID pattern
    for part in parts:
        if re.match(r"[A-Z]{2}-[A-Z]{2}-\d{3}", part.upper()):
            metadata["wricef_id"] = part.upper()
            logger.debug(f"WRICEF from filename: {part.upper()}")
            break

    metadata["extraction_source"] = "filename"
    return metadata


def _validate_metadata(metadata: Dict[str, str]) -> Dict[str, str]:
    """Validate and clean extracted metadata"""

    # Validate module codes
    valid_modules = {"CO", "TM", "SD", "WM"}
    if metadata["sap_module"] not in valid_modules:
        metadata["sap_module"] = "Unknown"

    # Validate complexity levels
    valid_complexity = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    if metadata["complexity"].upper() not in valid_complexity:
        metadata["complexity"] = "Unknown"

    # Validate landscape codes
    valid_landscapes = {"DEV", "QA", "PROD", "TEST", "SANDBOX"}
    if metadata["landscape"].upper() not in valid_landscapes:
        metadata["landscape"] = "Unknown"

    return metadata
