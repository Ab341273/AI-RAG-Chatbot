"""Security constants and messages"""

MAX_QUERY_LENGTH = 5000
MIN_QUERY_LENGTH = 1
MAX_OUTPUT_LENGTH = 5000

# Friendly greeting responses
GREETING_KEYWORDS = ["hello", "hi", "hey", "greetings", "how are you", "thanks", "thank you", "halo"]

GREETING_RESPONSES = {
    "default": "👋 Hi there! I'm Askify, your document assistant. Ask me anything about your uploaded PDFs! 📚",
    "thanks": "😊 You're welcome! Happy to help with your documents!",
    "how_are_you": "✨ I'm doing great! Ready to help you explore your documents. What would you like to know?",
}

# Friendly rejection messages
REJECTION_MESSAGES = {
    "injection": "I can only help with document-related questions. Please ask about your PDFs! 📄",
    "secret": "I cannot provide secrets, credentials, or system information. I'm here to help with your documents! 🔒",
    "code": "I'm a document assistant - I don't write code, poems, songs, or stories. Ask me about your uploaded documents instead! 📚 Example: 'What does the TM document say about warehouse management?'",
    "jailbreak": "I'm designed to help with your documents only. What would you like to know about them? 📄",
    "out_of_scope": "I specialize in document analysis. 📚 Try asking me: 'What does the document say about...?' or 'Explain the TM process from the PDF'",
    "too_long": "Your query is too long (max 5000 characters). Please make it shorter! ✂️",
    "too_short": "Your query is too short. Please provide more details! 📝",
}

# Not found in documents
NOT_FOUND_MESSAGE = "I couldn't find this information in the provided documents. Try asking about different aspects of the PDFs! 🔍"

# Rate limit message
RATE_LIMIT_MESSAGE = "⏱️ You've made many requests. Please wait a moment before trying again!"
