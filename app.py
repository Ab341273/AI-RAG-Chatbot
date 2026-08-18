from fastapi import FastAPI
from pydantic import BaseModel
from typing import List
from uuid import UUID
from datetime import datetime

from rag_handler.chat import answer_query
from services.conversation_manager import get_conversation_manager
from services.database_service import DatabaseService
from services.logging_service import get_logger

logger = get_logger(__name__)

app = FastAPI()


class ChatRequest(BaseModel):
    query: str
    k: int = 3


class ChatResponse(BaseModel):
    query: str
    answer: str


class MessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    created_at: datetime


class SessionResponse(BaseModel):
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []


class CreateSessionRequest(BaseModel):
    title: str = "New Chat"


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    logger.info(f"[API /chat] Query: {request.query[:100]} | K: {request.k}")
    try:
        answer = answer_query(request.query, k=request.k)
        logger.info(f"[API /chat] Success | Answer length: {len(answer)}")
        return ChatResponse(query=request.query, answer=answer)
    except Exception as e:
        logger.error(f"[API /chat] Error: {e}", exc_info=True)
        raise


@app.post("/sessions", response_model=SessionResponse)
def create_session(request: CreateSessionRequest):
    """Create a new chat session"""
    logger.info(f"[API /sessions POST] Creating session: {request.title}")
    session = DatabaseService.create_session(title=request.title)
    logger.info(f"[API /sessions POST] Created session: {session.id}")
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[]
    )


@app.get("/sessions", response_model=List[SessionResponse])
def get_all_sessions():
    """Get all chat sessions"""
    logger.info("[API /sessions GET] Fetching all sessions")
    sessions = DatabaseService.get_all_sessions()
    logger.info(f"[API /sessions GET] Found {len(sessions)} sessions")
    return [
        SessionResponse(
            id=s.id,
            title=s.title,
            created_at=s.created_at,
            updated_at=s.updated_at,
            messages=[
                MessageResponse(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at
                )
                for m in s.messages
            ]
        )
        for s in sessions
    ]


@app.get("/sessions/{session_id}", response_model=SessionResponse)
def get_session(session_id: UUID):
    """Get a specific session with all its messages"""
    logger.info(f"[API /sessions/{{id}} GET] Fetching session: {session_id}")
    session = DatabaseService.get_session(session_id)
    if not session:
        logger.warning(f"[API /sessions/{{id}} GET] Session not found: {session_id}")
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")

    logger.info(f"[API /sessions/{{id}} GET] Found session with {len(session.messages)} messages")
    return SessionResponse(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        messages=[
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                created_at=m.created_at
            )
            for m in session.messages
        ]
    )


@app.post("/sessions/{session_id}/messages", response_model=MessageResponse)
def add_message(session_id: UUID, request: ChatRequest):
    """
    Add a user message to a session and get AI response.

    Uses Conversational Retrieval Chain:
    - Loads chat history from database
    - Retrieves relevant documents
    - Generates context-aware response
    - Saves both messages to database
    """
    logger.info(f"[API /sessions/{{id}}/messages POST] Session: {session_id} | Query: {request.query[:100]}")

    DatabaseService.add_message(session_id, "user", request.query)
    conv_manager = get_conversation_manager(session_id)

    try:
        answer = conv_manager.answer_query_with_context(
            query=request.query,
            k=request.k
        )
        logger.info(f"[API /sessions/{{id}}/messages POST] Response generated | Length: {len(answer)}")
    except Exception as e:
        logger.error(f"[API /sessions/{{id}}/messages POST] Error: {e}", exc_info=True)
        raise

    assistant_msg = DatabaseService.add_message(session_id, "assistant", answer)

    return MessageResponse(
        id=assistant_msg.id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        created_at=assistant_msg.created_at
    )


@app.delete("/sessions/{session_id}")
def delete_session(session_id: UUID):
    """Delete a chat session"""
    logger.info(f"[API /sessions/{{id}} DELETE] Deleting session: {session_id}")
    success = DatabaseService.delete_session(session_id)
    if not success:
        logger.warning(f"[API /sessions/{{id}} DELETE] Session not found: {session_id}")
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Session not found")
    logger.info(f"[API /sessions/{{id}} DELETE] Session deleted successfully")
    return {"message": "Session deleted successfully"}