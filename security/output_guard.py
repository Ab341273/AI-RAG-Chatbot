"""Output guard for answer sanitization"""

import re
from services.logging_service import get_logger

logger = get_logger(__name__)

class OutputGuard:
    """Sanitizes LLM output to remove sensitive information"""

    # Patterns for secrets that shouldn't be in output
    SECRET_PATTERNS = [
        r"(?i)(api[_\s]key|secret[_\s]key)[\s:]*['\"]?[\w\-]+['\"]?",
        r"(?i)password[\s:]*['\"]?[\w\-]+['\"]?",
        r"(?i)token[\s:]*['\"]?[\w\-]+['\"]?",
        r"(?i)(access|private)[_\s]key[\s:]*['\"]?[\w\-]+['\"]?",
        r"sqlite_master",
        r"\.env",
        r"environment\s+variable",
    ]

    @staticmethod
    def sanitize(text: str) -> str:
        """Remove sensitive information from text"""
        if not text:
            return text

        sanitized = text

        # Remove potential secrets
        for pattern in OutputGuard.SECRET_PATTERNS:
            sanitized = re.sub(pattern, "[REDACTED]", sanitized)

        return sanitized

    @staticmethod
    def validate_scope(answer: str, query: str) -> tuple[bool, str]:
        """
        Check if answer seems reasonable.
        Returns: (is_valid, message)
        """
        if not answer or len(answer) < 5:
            return False, "Answer too short or empty"

        return True, ""

    @staticmethod
    def add_source_disclaimer(answer: str) -> str:
        """Add disclaimer about document sources (optional)"""
        if not answer:
            return answer

        return answer

    @staticmethod
    def process_output(answer: str, query: str) -> tuple[str, bool]:
        """
        Complete output processing pipeline.
        Returns: (processed_answer, is_valid)
        """
        if not answer:
            return "", False

        # Sanitize sensitive information
        sanitized = OutputGuard.sanitize(answer)

        # Validate scope
        is_valid, validation_msg = OutputGuard.validate_scope(sanitized, query)
        if not is_valid:
            logger.warning(f"[OUTPUT] Validation failed: {validation_msg}")

        # Add source disclaimer
        final_answer = OutputGuard.add_source_disclaimer(sanitized)

        return final_answer, is_valid
