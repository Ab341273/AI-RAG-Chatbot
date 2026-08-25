"""Security event logging (safe - no sensitive data)"""

from services.logging_service import get_logger
from security.security_patterns import SecurityLevel
from datetime import datetime

logger = get_logger(__name__)

class SecurityLogger:
    """Logs security events without exposing sensitive data"""

    @staticmethod
    def log_blocked_query(query: str, reason: SecurityLevel):
        """Log blocked query attempts"""
        timestamp = datetime.now().isoformat()

        if reason == SecurityLevel.INJECTION:
            logger.warning(f"[SECURITY] {timestamp} | INJECTION_BLOCKED | Query length: {len(query)}")
        elif reason == SecurityLevel.SECRET_REQUEST:
            logger.warning(f"[SECURITY] {timestamp} | SECRET_REQUEST_BLOCKED | Query length: {len(query)}")
        elif reason == SecurityLevel.JAILBREAK:
            logger.warning(f"[SECURITY] {timestamp} | JAILBREAK_BLOCKED | Query length: {len(query)}")
        elif reason == SecurityLevel.MALICIOUS_CODE:
            logger.warning(f"[SECURITY] {timestamp} | MALICIOUS_CODE_BLOCKED | Query length: {len(query)}")
        elif reason == SecurityLevel.OUT_OF_SCOPE:
            logger.info(f"[SECURITY] {timestamp} | OUT_OF_SCOPE | Query length: {len(query)}")

    @staticmethod
    def log_valid_query(query: str):
        """Log valid queries"""
        timestamp = datetime.now().isoformat()
        logger.info(f"[SECURITY] {timestamp} | VALID_QUERY | Length: {len(query)}")

    @staticmethod
    def log_greeting(greeting_type: str):
        """Log greeting interactions"""
        timestamp = datetime.now().isoformat()
        logger.info(f"[SECURITY] {timestamp} | GREETING | Type: {greeting_type}")

    @staticmethod
    def log_tool_call(tool_name: str, success: bool):
        """Log tool calls"""
        timestamp = datetime.now().isoformat()
        status = "SUCCESS" if success else "FAILED"
        logger.info(f"[SECURITY] {timestamp} | TOOL_CALL | {tool_name} | {status}")
