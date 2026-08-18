import os
import json
import re
from dotenv import load_dotenv
import httpx

from rag_handler.retriever import retrieve_similar_chunks
from services.logging_service import get_logger
from services.database_service import DatabaseService
from langchain_core.utils.function_calling import convert_to_openai_tool
from services.tools import calculator, get_current_datetime, get_weather

load_dotenv()

logger = get_logger(__name__)

# Use OpenRouter if available, fallback to GROQ
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_API_URL = os.getenv("OPENROUTER_API_URL")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openai/gpt-4-turbo")

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = os.getenv("GROQ_API_URL")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Determine which API to use
USE_OPENROUTER = bool(OPENROUTER_API_KEY)
API_KEY = OPENROUTER_API_KEY if USE_OPENROUTER else GROQ_API_KEY
API_URL = OPENROUTER_API_URL if USE_OPENROUTER else GROQ_API_URL
MODEL = OPENROUTER_MODEL if USE_OPENROUTER else GROQ_MODEL
PROVIDER = "OpenRouter" if USE_OPENROUTER else "GROQ"

# Tool definitions
TOOLS = [convert_to_openai_tool(t) for t in [calculator, get_current_datetime, get_weather]]
TOOL_MAP = {
    "calculator": calculator,
    "get_current_datetime": get_current_datetime,
    "get_weather": get_weather,
}


def get_document_info() -> str:
    """Get document statistics from database"""
    try:
        stats = DatabaseService.get_document_stats()
        total_docs = stats.get("total_documents", 0)
        total_chunks = stats.get("total_chunks", 0)
        modules = stats.get("by_module", {})

        module_str = ", ".join([f"{m}: {c}" for m, c in sorted(modules.items())]) if modules else "None"

        info = f"Knowledge Base: {total_docs} documents, {total_chunks} chunks. Modules: {module_str}"
        logger.debug(f"[DOCUMENT INFO] {info}")
        return info
    except Exception as e:
        logger.warning(f"Could not fetch document stats: {e}")
        return "Knowledge Base: Status unknown"


def build_context(query: str, k: int = 10) -> str:
    results = retrieve_similar_chunks(query, retrieval_k=30, final_k=10)
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


def make_prompt(query: str, context: str) -> str:
    doc_info = get_document_info()
    return (
        f"You are an AI assistant with access to a knowledge base. {doc_info}\n\n"
        "Use the following retrieved document context to answer the question.\n\n"
        f"Context:\n{context}\n\n"
        f"Question: {query}\n\n"
        "Answer clearly and concisely based on the provided context:"
    )


def call_groq(prompt: str) -> str:
    """
    Call LLM API (OpenRouter or GROQ) with tool calling support and fallback recovery.
    """
    if not API_KEY or not API_URL:
        raise ValueError(f"{PROVIDER} API key or URL not set in .env")

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }

    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": prompt},
    ]

    payload = {
        "model": MODEL,
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 300,
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            logger.info(f"[{PROVIDER} CALL] Model: {MODEL} | Tools enabled: True")
            response = client.post(API_URL, json=payload, headers=headers)

            # Handle tool_use_failed error with fallback recovery
            if response.status_code == 400:
                error_data = response.json()
                if error_data.get("error", {}).get("code") == "tool_use_failed":
                    logger.warning("[GROQ] Tool generation failed, attempting fallback recovery...")
                    failed_gen = error_data["error"].get("failed_generation", "")

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
                                "max_tokens": 300,
                            }
                            response = client.post(
                                API_URL, json=payload_without_tools, headers=headers
                            )
                            response.raise_for_status()
                    else:
                        logger.error(f"[TOOL FALLBACK] Could not parse malformed generation: {failed_gen}")
                        response.raise_for_status()
                else:
                    response.raise_for_status()

            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})

            # Handle standard tool_calls
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

                # Second call: remove tools, just get answer
                payload_without_tools = {
                    "model": MODEL,
                    "messages": messages,
                    "max_tokens": 300,
                }
                response = client.post(API_URL, json=payload_without_tools, headers=headers)
                response.raise_for_status()
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})

            final_answer = (message.get("content") or "").strip()
            logger.info(f"[LLM ANSWER] {final_answer[:150]}")
            return final_answer

    except Exception as e:
        logger.error(f"Error calling {PROVIDER} API: {e}", exc_info=True)
        raise


def rewrite_query(query: str) -> str:
    prompt = f"""
You are a query rewriting assistant for a legal RAG system.

Rewrite the user's question into a clear, standalone search query
that can be used to retrieve relevant legal documents.

Rules:
- Do not answer the question.
- Do not add facts that are not present.
- Preserve the original meaning.
- Remove unnecessary conversational wording.
- Make the query specific and suitable for semantic search.

User query:
{query}

Return only the rewritten search query.
"""
    return call_groq(prompt)


def answer_query(query: str, k: int = 3) -> str:
    rewritten_query = rewrite_query(query)
    logger.info(f"[QUERY REWRITE] Original: {query[:100]} → Rewritten: {rewritten_query[:100]}")
    context = build_context(rewritten_query, k=k)
    prompt = make_prompt(rewritten_query, context)
    return call_groq(prompt)