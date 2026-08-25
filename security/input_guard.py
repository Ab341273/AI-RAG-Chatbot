"""Input guard for query validation"""

from security.security_patterns import SecurityLevel, classify_query
from security.constants import (
    MAX_QUERY_LENGTH, MIN_QUERY_LENGTH,
    GREETING_KEYWORDS, REJECTION_MESSAGES
)
from services.logging_service import get_logger

logger = get_logger(__name__)

class InputGuard:
    """Validates user queries for security and scope"""

    @staticmethod
    def validate(query: str) -> tuple[bool, str, SecurityLevel]:
        """
        Validate query safety and scope.
        Returns: (is_valid, response/message, security_level)
        """
        if not query or not isinstance(query, str):
            return False, REJECTION_MESSAGES["out_of_scope"], SecurityLevel.OUT_OF_SCOPE

        query = query.strip()

        # Length checks
        if len(query) < MIN_QUERY_LENGTH:
            return False, REJECTION_MESSAGES["too_short"], SecurityLevel.OUT_OF_SCOPE

        if len(query) > MAX_QUERY_LENGTH:
            logger.warning(f"[SECURITY] Query exceeds max length: {len(query)}")
            return False, REJECTION_MESSAGES["too_long"], SecurityLevel.OUT_OF_SCOPE

        # Check for greetings
        query_lower = query.lower()
        if query_lower in GREETING_KEYWORDS or any(keyword in query_lower for keyword in GREETING_KEYWORDS):
            logger.info(f"[SECURITY] Greeting detected: {query[:50]}")
            if "thanks" in query_lower or "thank you" in query_lower:
                return True, "GREETING:thanks", SecurityLevel.GREETING
            elif "how are you" in query_lower:
                return True, "GREETING:how_are_you", SecurityLevel.GREETING
            else:
                return True, "GREETING:default", SecurityLevel.GREETING

        # Classify query
        security_level = classify_query(query)

        if security_level == SecurityLevel.INJECTION:
            logger.warning(f"[SECURITY] ⚠️ INJECTION ATTEMPT: {query[:100]}")
            return False, REJECTION_MESSAGES["injection"], SecurityLevel.INJECTION

        if security_level == SecurityLevel.SECRET_REQUEST:
            logger.warning(f"[SECURITY] ⚠️ SECRET REQUEST: {query[:100]}")
            return False, REJECTION_MESSAGES["secret"], SecurityLevel.SECRET_REQUEST

        if security_level == SecurityLevel.JAILBREAK:
            logger.warning(f"[SECURITY] ⚠️ JAILBREAK ATTEMPT: {query[:100]}")
            return False, REJECTION_MESSAGES["jailbreak"], SecurityLevel.JAILBREAK

        if security_level == SecurityLevel.MALICIOUS_CODE:
            logger.warning(f"[SECURITY] ⚠️ CODE GENERATION REQUEST: {query[:100]}")
            return False, REJECTION_MESSAGES["code"], SecurityLevel.MALICIOUS_CODE

        # OUT_OF_SCOPE queries are allowed - let RAG decide relevance
        # The retriever will return low scores if not relevant
        logger.info(f"[SECURITY] ✅ VALID QUERY: {query[:100]}")
        return True, "", SecurityLevel.SAFE
