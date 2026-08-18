import time
import uuid

import streamlit as st

from rag_handler.chat import answer_query
from services.conversation_manager import get_conversation_manager
from services.database_service import DatabaseService
from services.logging_service import get_logger

logger = get_logger(__name__)

APP_NAME = "DocuMind"
APP_TAGLINE = "Ask anything about your documents"

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
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500&display=swap');

    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }

    footer { visibility: hidden; }

    .stApp {
        background: radial-gradient(circle at 15% 20%, #2a1b4d 0%, transparent 45%),
                    radial-gradient(circle at 85% 15%, #1b3a4d 0%, transparent 45%),
                    radial-gradient(circle at 50% 90%, #3d1b4d 0%, transparent 50%),
                    linear-gradient(160deg, #0b0e1a 0%, #0f1424 50%, #0b0e1a 100%);
        background-attachment: fixed;
    }

    .stApp::before, .stApp::after {
        content: "";
        position: fixed;
        border-radius: 50%;
        filter: blur(90px);
        z-index: 0;
        pointer-events: none;
        opacity: 0.55;
    }
    .stApp::before {
        width: 420px; height: 420px;
        background: linear-gradient(135deg, #7f5af0, #2cb67d);
        top: -140px; left: -140px;
        animation: floatBlob 14s ease-in-out infinite;
    }
    .stApp::after {
        width: 380px; height: 380px;
        background: linear-gradient(135deg, #ff5da2, #5a67ff);
        bottom: -120px; right: -120px;
        animation: floatBlob 16s ease-in-out infinite reverse;
    }
    @keyframes floatBlob {
        0%, 100% { transform: translate(0, 0) scale(1); }
        50% { transform: translate(40px, 30px) scale(1.08); }
    }

    section[data-testid="stSidebar"] {
        background: rgba(255, 255, 255, 0.04);
        backdrop-filter: blur(18px);
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }

    .block-container { padding-top: 2rem; max-width: 760px; }

    /* Header */
    .app-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 18px 22px;
        margin-bottom: 22px;
        border-radius: 20px;
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        backdrop-filter: blur(20px);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.25);
        animation: fadeSlideIn 0.5s ease-out;
    }
    .app-logo {
        width: 46px; height: 46px;
        border-radius: 14px;
        display: flex; align-items: center; justify-content: center;
        font-size: 22px;
        background: linear-gradient(135deg, #7f5af0, #2cb67d);
        box-shadow: 0 4px 18px rgba(127, 90, 240, 0.45);
    }
    .app-title { font-size: 1.35rem; font-weight: 800; color: #f5f3ff; margin: 0; letter-spacing: -0.3px; }
    .app-subtitle { font-size: 0.85rem; color: #a3a3c2; margin: 0; }

    /* Chat bubbles */
    .bubble-row {
        display: flex;
        gap: 10px;
        margin-bottom: 16px;
        animation: fadeSlideIn 0.35s ease-out;
    }
    .bubble-row.user { flex-direction: row-reverse; }

    .avatar {
        width: 34px; height: 34px;
        min-width: 34px;
        border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        font-size: 16px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.3);
    }
    .avatar.user { background: linear-gradient(135deg, #5a67ff, #7f5af0); }
    .avatar.bot { background: linear-gradient(135deg, #2cb67d, #16bdca); }

    .bubble {
        max-width: 78%;
        padding: 13px 17px;
        border-radius: 18px;
        font-size: 0.95rem;
        line-height: 1.55;
        color: #eceaf6;
        backdrop-filter: blur(16px);
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
    }
    .bubble.user {
        background: linear-gradient(135deg, rgba(127,90,240,0.35), rgba(90,103,255,0.25));
        border: 1px solid rgba(160, 140, 255, 0.35);
        border-top-right-radius: 6px;
    }
    .bubble.bot {
        background: rgba(255, 255, 255, 0.06);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-top-left-radius: 6px;
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
        background: rgba(255, 255, 255, 0.06);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 18px;
        box-shadow: 0 8px 26px rgba(0,0,0,0.3);
        transition: box-shadow 0.25s ease, border-color 0.25s ease;
    }
    div[data-testid="stChatInput"]:hover,
    div[data-testid="stChatInput"]:focus-within {
        border-color: rgba(127, 90, 240, 0.55);
        box-shadow: 0 8px 30px rgba(127, 90, 240, 0.28);
    }
    div[data-testid="stChatInput"] textarea { color: #eceaf6 !important; }

    button[data-testid="stChatInputSubmitButton"] {
        background: linear-gradient(135deg, #7f5af0, #2cb67d) !important;
        border-radius: 12px !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
    }
    button[data-testid="stChatInputSubmitButton"]:hover {
        transform: scale(1.08);
        box-shadow: 0 0 16px rgba(127, 90, 240, 0.6);
    }
    button[data-testid="stChatInputSubmitButton"]:active {
        transform: scale(0.92);
    }

    /* Sidebar buttons */
    section[data-testid="stSidebar"] button {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        color: #eceaf6 !important;
        border-radius: 12px !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] button:hover {
        border-color: rgba(127,90,240,0.6) !important;
        box-shadow: 0 0 14px rgba(127,90,240,0.35);
    }

    ::-webkit-scrollbar { width: 8px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(127, 90, 240, 0.4);
        border-radius: 10px;
    }

    .empty-state {
        text-align: center;
        padding: 60px 20px;
        color: #8a86ad;
        animation: fadeSlideIn 0.6s ease-out;
    }
    .empty-state .icon { font-size: 2.6rem; margin-bottom: 10px; }
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
    st.markdown(f"### ✨ {APP_NAME}")
    st.caption("Retrieval-augmented assistant over your PDFs")
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
        <div class="app-logo">✨</div>
        <div>
            <p class="app-title">{APP_NAME}</p>
            <p class="app-subtitle">{APP_TAGLINE}</p>
        </div>
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
            <div>Start the conversation — ask a question about your documents.</div>
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
