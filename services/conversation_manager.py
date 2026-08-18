"""
Conversational Retrieval QA Chain
Combines chat history + document context for intelligent responses
"""

import os
import json
import re
from dotenv import load_dotenv
import httpx
from uuid import UUID

from rag_handler.retriever import retrieve_similar_chunks
from services.database_service import DatabaseService
from services.logging_service import get_logger
from langchain_core.utils.function_calling import convert_to_openai_tool
from services.tools import calculator, get_current_datetime, get_weather

logger = get_logger(__name__)

load_dotenv()

# GROQ API Configuration
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")

# Tool definitions for function calling
TOOLS = [convert_to_openai_tool(t) for t in [calculator, get_current_datetime, get_weather]]
TOOL_MAP = {
    "calculator": calculator,
    "get_current_datetime": get_current_datetime,
    "get_weather": get_weather,
}


class ConversationManager:
    """
    Manages conversational context with memory and document retrieval.

    Features:
    - Loads previous chat messages (Memory)
    - Retrieves relevant documents (RAG)
    - Combines both for context-aware responses
    - Maintains conversation flow
    """

    def __init__(self, session_id: UUID = None):
        """
        Initialize conversation manager for a session.

        Args:
            session_id: UUID of the chat session
        """
        self.session_id = session_id
        self.conversation_history = []

    def load_chat_history(self, limit: int = 5) -> list:
        """
        Load previous messages from database for context.

        Args:
            limit: Number of previous messages to load (default: 5)

        Returns:
            List of previous messages with role and content
        """
        if not self.session_id:
            return []

        try:
            session = DatabaseService.get_session(self.session_id)

            if not session:
                logger.info(f"No session found for ID: {self.session_id}")
                return []

            all_messages = session.messages if session.messages else []
            recent_messages = all_messages[-limit:] if len(all_messages) > limit else all_messages

            self.conversation_history = [
                {
                    "role": msg.role,
                    "content": msg.content
                }
                for msg in recent_messages
            ]

            logger.info(f"[CHAT HISTORY] Loaded {len(self.conversation_history)} messages for session {self.session_id}")
            return self.conversation_history

        except Exception as e:
            logger.error(f"Error loading chat history: {e}", exc_info=True)
            return []

    def build_context_from_documents(self, query: str, k: int = 3) -> str:
        """
        Retrieve relevant document chunks for the query.

        Args:
            query: User's question
            k: Number of chunks to retrieve (default: 3)

        Returns:
            Formatted document context
        """
        results = retrieve_similar_chunks(query, retrieval_k=20, final_k=k)

        if not results:
            logger.info(f"[RETRIEVAL] No documents found for query: {query[:100]}")
            return ""

        rerank_scores = [item.get("rerank_score", 0) for item in results]
        logger.info(
            f"[RETRIEVAL] Query: {query[:100]} | Chunks: {len(results)} | "
            f"Rerank scores: min={min(rerank_scores):.3f}, max={max(rerank_scores):.3f}, avg={sum(rerank_scores)/len(rerank_scores):.3f}"
        )

        return "\n\n".join(
            f"Source: {item['metadata'].get('source', 'unknown')}\nText: {item['document']}"
            for item in results
        )

    def build_context_from_history(self) -> str:
        """
        Build context string from conversation history.

        Returns:
            Formatted conversation history for context
        """
        if not self.conversation_history:
            return ""

        # Pichli conversation ko format karo
        history_text = "Previous conversation:\n"

        for msg in self.conversation_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            history_text += f"{role}: {msg['content']}\n"

        return history_text

    def create_system_prompt(self) -> str:
        """
        Create enhanced system prompt with context awareness.

        Returns:
            System prompt for the LLM
        """
        prompt = (
            "You are a helpful assistant with access to user documents and conversation history.\n"
            "Instructions:\n"
            "1. Use the document context to answer questions accurately\n"
            "2. Remember the conversation history for context\n"
            "3. Be conversational and maintain context from previous messages\n"
            "4. If relevant information is in the documents, cite it\n"
            "5. Answer in the same language as the user's question\n"
        )
        return prompt

    def create_enhanced_prompt(
        self,
        query: str,
        document_context: str,
        history_context: str
    ) -> str:
        """
        Create comprehensive prompt combining query, documents, and history.

        Args:
            query: Current user question
            document_context: Retrieved document chunks
            history_context: Previous conversation context

        Returns:
            Enhanced prompt ready for LLM
        """
        prompt = self.create_system_prompt()

        # Add history if available
        if history_context:
            prompt += f"\n{history_context}\n"

        # Add document context
        if document_context:
            prompt += f"\nRelevant documents:\n{document_context}\n"

        # Add current question
        prompt += f"\nCurrent Question: {query}\n"
        prompt += "Answer:\n"

        return prompt

    def call_groq_with_context(self, prompt: str) -> str:
        """
        Call GROQ API with enhanced context-aware prompt and tool calling support.

        Tool calling flow:
        1. Send prompt with tool schemas
        2. If Groq returns tool_calls, execute them
        3. If Groq fails with tool_use_failed (malformed generation), fallback to regex recovery
        4. Feed tool results back to Groq
        5. Return final answer

        Args:
            prompt: Enhanced prompt with history and documents

        Returns:
            Response from GROQ LLM
        """
        if not GROQ_API_KEY or not GROQ_API_URL:
            raise ValueError("GROQ_API_KEY or GROQ_API_URL is not set in .env")

        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "content": self.create_system_prompt()},
            {"role": "user", "content": prompt},
        ]

        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "tools": TOOLS,
            "tool_choice": "auto",
            "max_tokens": 500,
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                logger.info(f"[GROQ CALL] Model: {GROQ_MODEL} | Tools enabled: True")
                response = client.post(GROQ_API_URL, json=payload, headers=headers)

                # Handle tool_use_failed error with fallback recovery
                if response.status_code == 400:
                    error_data = response.json()
                    if error_data.get("error", {}).get("code") == "tool_use_failed":
                        logger.warning("[GROQ] Tool generation failed, attempting fallback recovery...")
                        failed_gen = error_data["error"].get("failed_generation", "")

                        # Regex parse malformed tool call: <function=NAME{JSON}</function>
                        match = re.match(
                            r"<function=(\w+)(\{.*\})</function>",
                            failed_gen.strip(),
                        )
                        if match:
                            tool_name = match.group(1)
                            args_str = match.group(2)
                            args = json.loads(args_str)

                            logger.info(f"[TOOL FALLBACK] Recovered tool: {tool_name} | Args: {args}")

                            if tool_name in TOOL_MAP:
                                try:
                                    tool_result = TOOL_MAP[tool_name].invoke(args)
                                    logger.info(f"[TOOL EXECUTED] {tool_name} → {str(tool_result)[:200]}")
                                except Exception as tool_err:
                                    logger.error(f"[TOOL ERROR] {tool_name} failed: {tool_err}", exc_info=True)
                                    tool_result = f"Tool error: {str(tool_err)}"

                                # Feed result back to Groq
                                messages.append(
                                    {
                                        "role": "assistant",
                                        "content": None,
                                        "tool_calls": [
                                            {
                                                "id": "fallback_1",
                                                "type": "function",
                                                "function": {
                                                    "name": tool_name,
                                                    "arguments": args_str,
                                                },
                                            }
                                        ],
                                    }
                                )
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": "fallback_1",
                                        "content": str(tool_result),
                                    }
                                )

                                # Second call: remove tools, just get answer
                                payload_without_tools = {
                                    "model": GROQ_MODEL,
                                    "messages": messages,
                                    "max_tokens": 500,
                                }
                                response = client.post(
                                    GROQ_API_URL, json=payload_without_tools, headers=headers
                                )
                                response.raise_for_status()
                        else:
                            logger.error(f"[TOOL FALLBACK] Could not parse malformed generation: {failed_gen}")
                            response.raise_for_status()
                    else:
                        response.raise_for_status()

                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})

                # Handle standard tool_calls (non-error case)
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    logger.info(f"[TOOL CALLS] Detected {len(tool_calls)} tool(s)")

                    for tool_call in tool_calls:
                        tool_name = tool_call.get("function", {}).get("name")
                        arguments = json.loads(
                            tool_call.get("function", {}).get("arguments", "{}")
                        )

                        if tool_name in TOOL_MAP:
                            try:
                                tool_result = TOOL_MAP[tool_name].invoke(arguments)
                                logger.info(
                                    f"[TOOL EXECUTED] {tool_name} | Args: {arguments} → {str(tool_result)[:200]}"
                                )
                            except Exception as tool_err:
                                logger.error(f"[TOOL ERROR] {tool_name} failed: {tool_err}", exc_info=True)
                                tool_result = f"Tool error: {str(tool_err)}"

                            messages.append(
                                {
                                    "role": "assistant",
                                    "content": message.get("content", ""),
                                    "tool_calls": [tool_call],
                                }
                            )
                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.get("id"),
                                    "content": str(tool_result),
                                }
                            )

                    # Second API call to get final answer with tool results
                    payload_without_tools = {
                        "model": GROQ_MODEL,
                        "messages": messages,
                        "max_tokens": 500,
                    }
                    response = client.post(GROQ_API_URL, json=payload_without_tools, headers=headers)
                    response.raise_for_status()
                    data = response.json()
                    message = data.get("choices", [{}])[0].get("message", {})

                final_answer = (message.get("content") or "").strip()
                logger.info(f"[LLM ANSWER] {final_answer[:150]}")
                return final_answer

        except Exception as e:
            logger.error(f"Error calling GROQ API: {e}", exc_info=True)
            raise

    def answer_query_with_context(
        self,
        query: str,
        k: int = 3
    ) -> str:
        """
        Main function: Answer query with full context awareness.

        Flow:
        1. Load chat history from database
        2. Retrieve relevant documents
        3. Create enhanced prompt
        4. Get response from LLM
        5. Return answer

        Args:
            query: User's question
            k: Number of document chunks to retrieve

        Returns:
            Context-aware response from LLM
        """
        # Step 1: Load conversation history (Memory)
        self.load_chat_history(limit=5)

        # Step 2: Build document context (RAG)
        document_context = self.build_context_from_documents(query, k=k)

        # Step 3: Build history context
        history_context = self.build_context_from_history()

        # Step 4: Create enhanced prompt with both contexts
        enhanced_prompt = self.create_enhanced_prompt(
            query=query,
            document_context=document_context,
            history_context=history_context
        )

        # Step 5: Get response from LLM
        response = self.call_groq_with_context(enhanced_prompt)

        return response

    def answer_with_memory_and_docs(
        self,
        session_id: UUID,
        query: str,
        k: int = 3
    ) -> str:
        """
        Complete pipeline: Question → History → Documents → Answer → Save to DB

        Args:
            session_id: Chat session ID
            query: User's question
            k: Number of documents to retrieve

        Returns:
            LLM response
        """
        # Initialize with session
        self.session_id = session_id

        # Get answer with full context
        answer = self.answer_query_with_context(query, k=k)

        # Save to database
        DatabaseService.add_message(session_id, "assistant", answer)

        return answer


# Initialize conversation manager (singleton approach)
def get_conversation_manager(session_id: UUID = None) -> ConversationManager:
    """
    Factory function to get conversation manager instance.

    Args:
        session_id: Optional session ID

    Returns:
        ConversationManager instance
    """
    return ConversationManager(session_id)
