"""Security patterns for detecting malicious queries"""

import re
from enum import Enum

class SecurityLevel(Enum):
    SAFE = "safe"
    GREETING = "greeting"
    OUT_OF_SCOPE = "out_of_scope"
    INJECTION = "injection"
    SECRET_REQUEST = "secret_request"
    JAILBREAK = "jailbreak"
    MALICIOUS_CODE = "malicious_code"

# Injection patterns - strict matching
INJECTION_PATTERNS = [
    r"\bignore\b.*\b(previous|prior|all|your|these)\b.*\b(instruction|prompt|rule|command)",
    r"\bforget\b.*\b(instruction|rule|prompt)",
    r"\bsystem\s*prompt",
    r"\byou\s+(are|be)\s+(now|acting as|a)\b",
    r"\bfrom\s+now\s+on",
    r"\bnew\s+(instruction|rule|role)",
    r"\boverride",
    r"\bdisregard",
    r"\byour\s+real\s+(purpose|role|instruction)",
]

# Secret/credential patterns
SECRET_PATTERNS = [
    r"api\s*key",
    r"secret\s*key",
    r"\bpassword\b",
    r"\btoken\b",
    r"credential",
    r"environment\s*variable",
    r"\.env",
    r"private\s*key",
    r"access\s*key",
    r"secret\b",
    r"confidential",
]

# Code generation & creative writing patterns
CODE_PATTERNS = [
    r"write.*code",
    r"generate.*code",
    r"create.*script",
    r"python\s+code",
    r"javascript\s+code",
    r"sql\s+query",
    r"endpoint",
    r"api\s+endpoint",
    r"function\s+(to|for)",
    r"write.*poem",
    r"write.*song",
    r"write.*story",
    r"write.*poetry",
    r"write.*lyrics",
    r"create.*poem",
    r"create.*song",
    r"create.*story",
    r"generate.*poem",
    r"generate.*story",
    r"likhdo",
    r"likho.*gana",
    r"likho.*poem",
    r"likho.*code",
    r"likho.*story",
]

# Jailbreak patterns
JAILBREAK_PATTERNS = [
    r"unrestricted",
    r"without\s+(filter|restriction|limit)",
    r"no\s+restriction",
    r"ignore.*safety",
    r"bypass",
    r"unlimit",
    r"pretend\b",
    r"role\s*play",
]

# Document-related keywords
DOC_KEYWORDS = [
    "document", "pdf", "file", "content", "explain", "what", "how",
    "describe", "find", "search", "information", "detail", "module",
    "process", "procedure", "report", "data", "section", "chapter",
    "page", "text", "extract", "summarize", "quote", "reference"
]

def is_injection_attempt(query: str) -> bool:
    """Detect prompt injection attempts"""
    query_lower = query.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False

def is_secret_request(query: str) -> bool:
    """Detect requests for secrets/credentials"""
    query_lower = query.lower()
    for pattern in SECRET_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False

def is_code_generation_request(query: str) -> bool:
    """Detect code generation requests"""
    query_lower = query.lower()
    for pattern in CODE_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False

def is_jailbreak_attempt(query: str) -> bool:
    """Detect jailbreak attempts"""
    query_lower = query.lower()
    for pattern in JAILBREAK_PATTERNS:
        if re.search(pattern, query_lower):
            return True
    return False

def is_document_related(query: str) -> bool:
    """Check if query is document-related"""
    query_lower = query.lower()
    return any(keyword in query_lower for keyword in DOC_KEYWORDS)

def classify_query(query: str) -> SecurityLevel:
    """Classify query security level"""
    query_lower = query.lower()

    # Check for injections first (most dangerous)
    if is_injection_attempt(query):
        return SecurityLevel.INJECTION

    if is_secret_request(query):
        return SecurityLevel.SECRET_REQUEST

    if is_jailbreak_attempt(query):
        return SecurityLevel.JAILBREAK

    if is_code_generation_request(query):
        return SecurityLevel.MALICIOUS_CODE

    # Check if document-related
    if not is_document_related(query):
        return SecurityLevel.OUT_OF_SCOPE

    return SecurityLevel.SAFE
