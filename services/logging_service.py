"""
Centralized logging service for the chatbot project.
Provides a single logger instance used across all modules.
"""

import logging
import os

_logger = None


def get_logger(name: str = __name__) -> logging.Logger:
    """
    Get or create a logger instance.

    Args:
        name: Logger name (typically __name__ of calling module)

    Returns:
        Configured logger instance with proper level and handlers
    """
    global _logger

    if _logger is None:
        # FIX: Configure root logger so all child loggers inherit settings
        # Pehle: "_logger" (chatbot) configured था, लेकिन "ingestion.pipeline" logger return हो रहा था
        # Ab: Root logger configure करेंगे, सब loggers को inherit करेंगे

        root_logger = logging.getLogger()  # Root logger
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        root_logger.setLevel(getattr(logging, log_level))

        # Add handler to root logger (सब child loggers को inherit करेंगे)
        if not root_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "[%(levelname)s] %(name)s | %(message)s"
            )
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

        # Also initialize main chatbot logger for backward compatibility
        _logger = logging.getLogger("chatbot")
        _logger.setLevel(getattr(logging, log_level))

    # अब module-specific logger return करो (ingestion.pipeline, rag_handler, etc)
    # ये root logger से inherit करेगा
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()))
    return logger
