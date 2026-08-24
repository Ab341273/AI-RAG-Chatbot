"""
Conversation Manager with Tool Calling
"""

import os
from uuid import UUID
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
import json

from rag_handler.retriever import retrieve_similar_chunks
from services.database_service import DatabaseService
from services.logging_service import get_logger
from services import tools as services_tools

logger = get_logger(__name__)
load_dotenv()

# API Configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = os.getenv("OPENROUTER_API_URL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemma-4-31b-it:free")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = os.getenv("GROQ_API_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-70b-versatile")

USE_OPENROUTER = bool(OPENROUTER_API_KEY)

# Tool definitions for LLM
TOOLS_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "check_database_documents",
            "description": "Check all documents stored in the database. Returns count and metadata of all ingested documents.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_document_stats",
            "description": "Get statistics about documents in the database including total count, chunks, and count by module.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_documents_by_module",
            "description": "Search for documents by SAP module (e.g., CO, FI, MM, TM, SD, WM).",
            "parameters": {
                "type": "object",
                "properties": {
                    "module": {"type": "string", "description": "SAP module code (e.g., 'CO', 'FI', 'TM')"}
                },
                "required": ["module"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_database_vs_chroma",
            "description": "Check mismatch between SQL database documents and ChromaDB embeddings. Shows which documents are in the database but not properly embedded.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

# Tool functions map for execution
TOOL_FUNCTIONS = {
    "check_database_documents": services_tools.check_database_documents.func,
    "get_document_stats": services_tools.get_document_stats.func,
    "search_documents_by_module": services_tools.search_documents_by_module.func,
    "check_database_vs_chroma": services_tools.check_database_vs_chroma.func,
}

# Initialize LLM
if USE_OPENROUTER:
    llm = ChatOpenAI(
        model=OPENROUTER_MODEL,
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_URL,
        temperature=0.7,
        max_tokens=1000,
    )
    logger.info(f"[LLM] Initialized OpenRouter: {OPENROUTER_MODEL}")
else:
    llm = ChatOpenAI(
        model=GROQ_MODEL,
        api_key=GROQ_API_KEY,
        base_url=GROQ_URL,
        temperature=0.7,
        max_tokens=1000,
    )
    logger.info(f"[LLM] Initialized GROQ: {GROQ_MODEL}")

# Bind tools to LLM
llm_with_tools = llm.bind_tools(TOOLS_DEFINITIONS)
logger.info(f"[TOOLS] Loaded {len(TOOL_FUNCTIONS)} tools")


class ConversationManager:
    """Simple conversation manager with document retrieval and memory"""

    def __init__(self, session_id: UUID = None):
        self.session_id = session_id

    def load_chat_history(self, limit: int = 5) -> str:
        """Load previous messages from database for context"""
        if not self.session_id:
            return ""

        try:
            session = DatabaseService.get_session(self.session_id)
            if not session or not session.messages:
                return ""

            # Get last N messages
            messages = session.messages[-limit:] if len(session.messages) > limit else session.messages

            history = "Previous conversation:\n"
            for msg in messages:
                role = "User" if msg.role == "user" else "Assistant"
                history += f"{role}: {msg.content}\n"

            logger.info(f"[HISTORY] Loaded {len(messages)} previous messages")
            return history

        except Exception as e:
            logger.warning(f"[HISTORY] Could not load: {e}")
            return ""

    def build_context(self, query: str) -> str:
        """Retrieve relevant documents"""
        results = retrieve_similar_chunks(query, retrieval_k=20, final_k=5)

        if not results:
            return ""

        return "\n\n".join(
            f"Source: {item['metadata'].get('source', 'unknown')}\nText: {item['document']}"
            for item in results
        )

    def call_llm(self, prompt: str) -> str:
        """Call LLM with tool calling loop"""
        try:
            logger.info(f"[LLM] Processing: {prompt[:100]}")

            messages = [HumanMessage(content=prompt)]

            # Tool calling loop (max 3 iterations)
            for iteration in range(3):
                logger.info(f"[LLM] Iteration {iteration + 1}")

                # Call LLM with tools
                response = llm_with_tools.invoke(messages)

                # Check if LLM wants to call a tool
                if hasattr(response, 'tool_calls') and response.tool_calls:
                    tool_calls = response.tool_calls
                    logger.info(f"[LLM] Calling {len(tool_calls)} tool(s)")

                    # Add AI message to conversation
                    messages.append(response)

                    # Execute each tool call
                    for tool_call in tool_calls:
                        tool_name = tool_call.get("name") or tool_call.get("type")
                        tool_input = tool_call.get("args", {})

                        logger.info(f"[TOOL] Executing: {tool_name}")

                        if tool_name in TOOL_FUNCTIONS:
                            try:
                                # Execute the tool
                                tool_result = TOOL_FUNCTIONS[tool_name](**tool_input)
                                logger.info(f"[TOOL] {tool_name} result: {str(tool_result)[:100]}")
                            except Exception as e:
                                tool_result = f"Error executing {tool_name}: {str(e)}"
                                logger.error(f"[TOOL] Error: {e}")
                        else:
                            tool_result = f"Tool {tool_name} not found"
                            logger.warning(f"[TOOL] Unknown tool: {tool_name}")

                        # Add tool result to messages
                        messages.append(ToolMessage(
                            content=str(tool_result),
                            tool_call_id=tool_call.get("id", "")
                        ))
                else:
                    # LLM didn't call a tool, return the response
                    answer = response.content
                    logger.info(f"[LLM] Final answer: {answer[:100]}")
                    return answer

            # Max iterations reached, return last response
            return response.content

        except Exception as e:
            logger.error(f"[LLM] Error: {e}", exc_info=True)
            return f"Sorry, error: {str(e)}"

    def answer_query_with_context(self, query: str, k: int = 3) -> str:
        """Answer query with document context and chat history"""
        try:
            logger.info(f"[QUERY] {query[:100]}")

            # Load chat history
            history = self.load_chat_history(limit=5)

            # Get document context
            context = self.build_context(query)

            # Build prompt with history and context
            prompt = f"""You are a helpful assistant with access to documents and tools.

{history}

Context from documents:
{context}

User Question: {query}

Use available tools if needed (e.g., to check document status, search by module, get stats).
Answer clearly based on the provided context, conversation history, and any tool results:"""

            # Get answer from LLM
            answer = self.call_llm(prompt)

            # Save to database
            if self.session_id:
                try:
                    DatabaseService.add_message(self.session_id, "assistant", answer)
                    logger.info(f"[DB] Saved message for session {self.session_id}")
                except Exception as e:
                    logger.warning(f"[DB] Could not save: {e}")

            return answer

        except Exception as e:
            logger.error(f"[ERROR] {e}", exc_info=True)
            return f"Sorry, I encountered an error: {str(e)}"

    def answer_with_memory_and_docs(self, session_id: UUID, query: str, k: int = 3) -> str:
        """Answer with session context"""
        self.session_id = session_id
        return self.answer_query_with_context(query, k=k)


def get_conversation_manager(session_id: UUID = None) -> ConversationManager:
    """Get conversation manager instance"""
    return ConversationManager(session_id)
