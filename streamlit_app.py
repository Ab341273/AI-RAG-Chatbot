import time
import uuid

import streamlit as st

from config.Database import Base, engine
from rag_handler.chat import answer_query
from services.conversation_manager import get_conversation_manager
from services.database_service import DatabaseService
from services.logging_service import get_logger
from services.ingestion_service import handle_pdf_upload, run_full_ingestion, get_ingestion_status

Base.metadata.create_all(bind=engine)

logger = get_logger(__name__)

APP_NAME = "Askify"
APP_TAGLINE = "Smart answers powered by your documents"

st.set_page_config(
    page_title=APP_NAME,
    page_icon="✨",
    layout="centered",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styling — glassmorphism theme
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    * {
        font-family: 'Inter', sans-serif;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
        background-color: #0f0f12;
        color: #e0e0e0;
    }

    footer { visibility: hidden; }

    .stApp {
        background-color: #0f0f12;
    }

    section[data-testid="stSidebar"] {
        background-color: #1a1a1e !important;
        border-right: 1px solid #2a2a2f;
    }

    .block-container {
        padding-top: 1.5rem;
        max-width: 900px;
    }

    /* Header */
    .app-header {
        padding-bottom: 1rem;
        border-bottom: 1px solid #2a2a2f;
        margin-bottom: 1.5rem;
    }
    .app-title {
        font-size: 1.8rem;
        font-weight: 700;
        color: #ffffff;
        margin: 0 0 0.4rem 0;
        letter-spacing: -0.4px;
    }
    .app-subtitle {
        font-size: 0.8rem;
        color: #606066;
        margin: 0;
    }

    /* Chat bubbles */
    .bubble-row {
        display: flex;
        gap: 12px;
        margin-bottom: 12px;
    }
    .bubble-row.user { flex-direction: row-reverse; }

    .avatar {
        width: 32px; height: 32px;
        min-width: 32px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 16px;
        background-color: #2a2a2f;
    }
    .avatar.user { background-color: #5a67ff; }
    .avatar.bot { background-color: #2a2a2f; color: #909099; }

    .bubble {
        max-width: 85%;
        padding: 12px 16px;
        border-radius: 12px;
        font-size: 0.95rem;
        line-height: 1.5;
        color: #e0e0e0;
    }
    .bubble.user {
        background-color: #5a67ff;
        color: #ffffff;
    }
    .bubble.bot {
        background-color: #1a1a1e;
        border: 1px solid #2a2a2f;
        color: #e0e0e0;
    }
    .bubble p { margin: 0 0 8px 0; }
    .bubble p:last-child { margin-bottom: 0; }

    @keyframes fadeSlideIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }

    /* Typing indicator */
    .typing-dots span {
        display: inline-block;
        width: 7px; height: 7px;
        margin-right: 4px;
        border-radius: 50%;
        background: #b9b3e8;
        animation: bounceDot 1.2s infinite ease-in-out;
    }
    .typing-dots span:nth-child(2) { animation-delay: 0.15s; }
    .typing-dots span:nth-child(3) { animation-delay: 0.3s; }
    @keyframes bounceDot {
        0%, 80%, 100% { transform: translateY(0); opacity: 0.5; }
        40% { transform: translateY(-6px); opacity: 1; }
    }

    /* Chat input */
    div[data-testid="stChatInput"] {
        background-color: transparent !important;
        border: none !important;
        border-bottom: 1px solid #2a2a2f !important;
        border-radius: 0 !important;
        transition: all 0.2s ease;
        padding: 0 !important;
    }
    div[data-testid="stChatInput"]:focus-within {
        border-bottom-color: #5a67ff !important;
    }
    div[data-testid="stChatInput"] textarea {
        color: #e0e0e0 !important;
        background-color: #1a1a1e !important;
    }
    div[data-testid="stChatInput"] textarea::placeholder {
        color: #606066 !important;
    }

    button[data-testid="stChatInputSubmitButton"] {
        background-color: #5a67ff !important;
        border: none !important;
        border-radius: 8px !important;
        color: #ffffff !important;
        transition: all 0.2s ease !important;
    }
    button[data-testid="stChatInputSubmitButton"]:hover {
        background-color: #6b78ff !important;
        transform: scale(1.05);
    }

    /* Sidebar buttons */
    section[data-testid="stSidebar"] button {
        background-color: transparent !important;
        border: none !important;
        color: #e0e0e0 !important;
        border-radius: 8px !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: rgba(90, 103, 255, 0.1) !important;
        color: #5a67ff !important;
    }

    /* Remove expander borders */
    section[data-testid="stSidebar"] [data-testid="stExpander"] {
        border: none !important;
    }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: #2a2a2f;
        border-radius: 10px;
    }

    .empty-state {
        text-align: center;
        padding: 80px 20px;
        color: #606066;
    }
    .empty-state .icon { font-size: 3rem; margin-bottom: 16px; }
    .empty-state div {
        font-size: 1rem;
        color: #909099;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "session_id" not in st.session_state:
    st.session_state.session_id = None

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"### {APP_NAME}")
    st.caption("Smart AI assistant for your documents")
    st.divider()

    with st.expander("📄 Upload PDFs", expanded=False):
        uploaded_files = st.file_uploader(
            "Choose PDF files",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader"
        )

        if uploaded_files:
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Upload", use_container_width=True):
                    with st.spinner("Uploading files..."):
                        upload_result = handle_pdf_upload(uploaded_files)
                        if upload_result["success"]:
                            st.success(f"✅ {upload_result['uploaded_count']} file(s) uploaded")
                        else:
                            st.error(upload_result["message"])
                        if upload_result.get("errors"):
                            for error in upload_result["errors"]:
                                st.caption(f"❌ {error}")

            with col2:
                if st.button("Ingest", use_container_width=True):
                    with st.spinner("Ingesting PDFs..."):
                        ingest_result = run_full_ingestion()
                        if ingest_result["success"]:
                            stats = ingest_result["stats"]
                            st.success("✅ Ingestion Complete!")
                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric("PDFs", stats.get("pdf_docs", 0))
                                st.metric("Chunks", stats.get("chunks_created", 0))
                            with col_b:
                                st.metric("Embedded", stats.get("chunks_embedded", 0))
                                st.metric("Saved", stats.get("documents_saved", 0))
                        else:
                            st.error(ingest_result["message"])

        status = get_ingestion_status()
        st.caption(f"📊 PDFs available: {status.get('total_docs', 0)}")

    st.divider()

    if st.button("➕ New chat", use_container_width=True):
        new_session = DatabaseService.create_session(title="New Chat")
        st.session_state.session_id = new_session.id
        st.session_state.messages = []

    st.markdown("**Recent chats:**")
    try:
        all_sessions = DatabaseService.get_all_sessions()

        for session in all_sessions[:10]:
            session_title = session.title[:30] + "..." if len(session.title) > 30 else session.title
            if st.button(f"💬 {session_title}", use_container_width=True, key=f"session_{session.id}"):
                try:
                    st.session_state.session_id = session.id
                    db_session = DatabaseService.get_session(session.id)
                    if db_session:
                        st.session_state.messages = [
                            {"role": msg.role, "content": msg.content}
                            for msg in (db_session.messages or [])
                        ]
                except Exception as e:
                    st.error(f"Error loading chat: {str(e)}")
    except Exception as e:
        st.warning("Could not load recent chats")

    st.divider()

    with st.expander("⚙️  Retrieval settings"):
        k = st.slider("Context chunks (k)", min_value=1, max_value=8, value=3)

    st.divider()
    st.caption(f"Messages: {len(st.session_state.messages)}")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <div class="app-header">
        <p class="app-title">{APP_NAME}</p>
        <p class="app-subtitle">{APP_TAGLINE}</p>
    </div>
    """,
    unsafe_allow_html=True,
)


def render_bubble(role: str, content: str) -> str:
    if role == "user":
        return f"""
        <div class="bubble-row user">
            <div class="avatar user">🧑</div>
            <div class="bubble user"><p>{content}</p></div>
        </div>
        """
    return f"""
    <div class="bubble-row bot">
        <div class="avatar bot">✨</div>
        <div class="bubble bot">{content}</div>
    </div>
    """


# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------
if not st.session_state.messages:
    st.markdown(
        """
        <div class="empty-state">
            <div class="icon">💬</div>
            <div>Ask your query...</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    for msg in st.session_state.messages:
        st.markdown(render_bubble(msg["role"], msg["content"]), unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
prompt = st.chat_input("Type your message...")

if prompt:
    if st.session_state.session_id is None:
        session_title = prompt[:50] if len(prompt) > 0 else "New Chat"
        new_session = DatabaseService.create_session(title=session_title)
        st.session_state.session_id = new_session.id
        logger.info(f"[STREAMLIT] New session created: {st.session_state.session_id} | Title: {session_title}")

    logger.info(f"[STREAMLIT] User message: {prompt[:100]} | Session: {st.session_state.session_id}")

    DatabaseService.add_message(st.session_state.session_id, "user", prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.markdown(render_bubble("user", prompt), unsafe_allow_html=True)

    typing_placeholder = st.empty()
    typing_placeholder.markdown(
        """
        <div class="bubble-row bot">
            <div class="avatar bot">✨</div>
            <div class="bubble bot">
                <div class="typing-dots"><span></span><span></span><span></span></div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        conv_manager = get_conversation_manager(st.session_state.session_id)
        answer = conv_manager.answer_query_with_context(
            query=prompt,
            k=k
        )
        logger.info(f"[STREAMLIT] Response generated successfully | Length: {len(answer)}")
    except Exception as exc:
        answer = f"⚠️ Something went wrong while generating a response: {exc}"
        logger.error(f"[STREAMLIT] Error generating response: {exc}", exc_info=True)

    DatabaseService.add_message(st.session_state.session_id, "assistant", answer)

    typed_text = ""
    for i in range(0, len(answer), 3):
        typed_text = answer[: i + 3]
        typing_placeholder.markdown(
            f"""
            <div class="bubble-row bot">
                <div class="avatar bot">✨</div>
                <div class="bubble bot"><p>{typed_text}▌</p></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        time.sleep(0.012)

    typing_placeholder.markdown(render_bubble("assistant", f"<p>{answer}</p>"), unsafe_allow_html=True)
    st.session_state.messages.append({"role": "assistant", "content": f"<p>{answer}</p>"})
