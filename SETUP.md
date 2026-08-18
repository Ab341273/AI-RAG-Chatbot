# Setup Guide - DocuMind Chatbot with Tool Calling

## Quick Start (3 Steps)

### 1️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 2️⃣ Configure Environment
Copy `.env.example` to `.env` and fill in your values:
```bash
cp .env.example .env
```

**Required:**
- `GROQ_API_KEY` - Get from https://console.groq.com
- `GROQ_API_URL` - Usually: `https://api.groq.com/openai/v1/chat/completions`
- `GROQ_MODEL` - Default: `llama-3.3-70b-versatile`

**Database (PostgreSQL):**
- `DB_HOST`, `DB_USER`, `DB_PASSWORD`, `DB_NAME`, `DB_PORT`

### 3️⃣ Run the App
```bash
python run_app.py
```

Browser opens automatically at: **http://localhost:8501**

---

## What Happens on Startup

The `run_app.py` script now does:

1. ✅ **Environment Check** - Verifies GROQ API keys are set
2. ✅ **Database Init** - Creates tables for sessions & messages
3. ✅ **Tool Verification** - Tests all 3 tools (calculator, datetime, weather)
4. ✅ **Starts Streamlit** - Launches the web app

If any step fails, you'll see a clear error message.

---

## Features with Logging

### Tool Calling
Ask the chatbot:
- **Time**: "kya time hai?" → Uses `get_current_datetime` tool
- **Math**: "25 + 15?" → Uses `calculator` tool
- **Weather**: "Karachi ka weather?" → Uses `get_weather` tool (requires coordinates)

### Logging
Check **console output** for `[INFO]` messages showing:
```
[INFO] [CHAT HISTORY] Loaded 5 messages
[INFO] [RETRIEVAL] Retrieved 20 candidates | Rerank scores: min=0.89, max=0.95
[INFO] [TOOL EXECUTED] get_current_datetime → Wednesday, 12 August 2026, 02:39:29 PM
[INFO] [LLM ANSWER] Filhaal time 2:39 PM hai
```

---

## Troubleshooting

### "GROQ_API_KEY not set"
- Check `.env` file exists in project root
- Verify `GROQ_API_KEY=gsk_...` is present

### "Database connection failed"
- Ensure PostgreSQL is running: `psql -U postgres`
- Check `DB_HOST`, `DB_USER`, `DB_PASSWORD` in `.env`

### "Tool test failed"
- Models download on first use (may take a minute)
- Internet connection required for model downloads
- Check `models/` folder gets created

### "Streamlit not found"
```bash
pip install streamlit
```

---

## Project Structure

```
ai-chatbot/
├── services/
│   ├── logging_service.py      ← Centralized logger
│   ├── tools.py                ← 3 tools (calculator, datetime, weather)
│   ├── conversation_manager.py ← Main chat logic with tool calling
│   └── database_service.py     ← Database operations
├── rag_handler/
│   ├── chat.py                 ← API chat with tool calling
│   ├── retriever.py            ← RAG retrieval + reranking
├── streamlit_app.py            ← Web UI
├── app.py                       ← FastAPI endpoints
├── run_app.py                  ← Main startup script
├── requirements.txt
├── .env.example                ← Config template
└── SETUP.md                    ← This file
```

---

## Architecture

```
User Message
    ↓
Streamlit UI (streamlit_app.py)
    ↓
ConversationManager (conversation_manager.py)
    ├─→ Load Chat History (from DB)
    ├─→ Retrieve Documents (RAG + reranking)
    ├─→ Build Enhanced Prompt
    ├─→ Send to Groq with Tool Schemas
    │   ├─→ If tool_calls: Execute tools + feed back
    │   ├─→ If tool_use_failed: Fallback recovery + execute
    │   └─→ Get Final Answer
    └─→ Save to Database
    ↓
Streamlit displays response
```

---

## Logging Output Examples

### Time Query
```
[INFO] [STREAMLIT] User message: kya time hai? | Session: abc123
[INFO] [CHAT HISTORY] Loaded 0 messages
[INFO] [RETRIEVAL] No documents found
[INFO] [GROQ CALL] Model: llama-3.3-70b-versatile | Tools enabled: True
[INFO] [TOOL EXECUTED] get_current_datetime → Wednesday, 12 August 2026, 02:40:00 PM
[INFO] [LLM ANSWER] Filhaal 2:40 PM hai
```

### Document Query
```
[INFO] [RETRIEVAL] Query: tell me about graduat | Chunks: 3 | Rerank: min=0.890, max=0.950
[INFO] [LLM ANSWER] Based on the documents, the graduate education policy...
```

---

## Next Steps

1. Add your PDF documents to `data/pdfs/`
2. Run ingestion: `python ingestion/pipeline.py` (loads PDFs to ChromaDB)
3. Start chatbot: `python run_app.py`
4. Ask questions and watch the logs!

---

**Questions?** Check `.env.example` and console logs for hints.
