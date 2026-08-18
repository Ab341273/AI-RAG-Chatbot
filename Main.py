import os
from ingestion.pipeline import run_pipeline
from services.logging_service import get_logger

if __name__ == "__main__":
    # FIX: Set LOG_LEVEL environment variable before importing logger
    # Ye ensure करता है कि सब loggers INFO level पर logs दिखाएं
    os.environ.setdefault("LOG_LEVEL", "INFO")

    logger = get_logger(__name__)

    logger.info("🚀 Starting PDF → Chunks → Embeddings → Chroma pipeline...")
    try:
        run_pipeline()
        logger.info("✅ Pipeline finished successfully!")
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {type(e).__name__} — {e}", exc_info=True)
        raise
