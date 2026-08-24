# Database Setup Guide

Your application wasn't storing data in PostgreSQL due to missing table initialization. Here's how to fix it:

## ✅ What Was Fixed

1. **Document Model** — Now uses the correct SQLAlchemy Base from `config/Database.py`
2. **Error Handling** — Database save failures are now logged and reported, not silently ignored
3. **Database Init Script** — New script to create tables and test connection
4. **Connection Diagnostics** — New tool to troubleshoot database issues

---

## 🚀 Quick Start (Do This First)

### Step 1: Test Database Connection

Run this to check if PostgreSQL is running and accessible:

```bash
python test_db_connection.py
```

**What to look for:**
- ✓ All environment variables set
- ✓ PostgreSQL connection successful
- ✓ SQLAlchemy connection successful
- ✓ All required tables exist (or instructions to create them)

### Step 2: Initialize Database (Create Tables)

If the test shows missing tables, run:

```bash
python init_db.py
```

This will:
- ✓ Test the connection
- ✓ Create all required tables (`sessions`, `messages`, `documents`)
- ✓ Verify tables were created successfully

### Step 3: Run Your Application

Now your application will properly store data:

```bash
# For Streamlit
streamlit run app.py

# For FastAPI (if applicable)
uvicorn main:app --reload
```

---

## 🔍 Troubleshooting

### PostgreSQL is not running

**Error:** `Connection refused` or `could not translate host name`

**Fix:**
1. Start PostgreSQL on Windows:
   - Open Services (services.msc)
   - Find "PostgreSQL" service
   - Right-click → Start

2. Or use command line:
   ```bash
   # If PostgreSQL is installed via chocolatey/scoop
   pg_ctl -D "C:\Program Files\PostgreSQL\data" start
   ```

### Wrong password/username

**Error:** `FATAL: password authentication failed`

**Fix:**
1. Edit `.env` file
2. Verify these are correct:
   ```
   DB_USER=postgres
   DB_PASSWORD=admin
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=rag-engine
   ```

3. If you forgot the password, reset it:
   ```bash
   psql -U postgres
   ALTER USER postgres WITH PASSWORD 'admin';
   ```

### Database doesn't exist

**Error:** `database "rag-engine" does not exist`

**Fix:**
1. Create the database:
   ```bash
   psql -U postgres -c "CREATE DATABASE \"rag-engine\";"
   ```

2. Then run the init script:
   ```bash
   python init_db.py
   ```

### Tables still don't exist after running init_db.py

**Check the logs:**
```bash
python init_db.py  # Look for error messages
```

**Most common cause:** SQLAlchemy cannot import the models. Fix:
1. Ensure all model files exist:
   - `models/sessions.py`
   - `models/messages.py`
   - `models/documents.py`

2. Check imports in `config/Database.py` (they should be automatic via models)

---

## 📊 Verifying Data is Being Stored

After setup, verify data is actually being saved:

### Check PostgreSQL directly

```bash
psql -U postgres -d rag-engine

# Inside psql:
SELECT COUNT(*) FROM documents;
SELECT COUNT(*) FROM sessions;
SELECT COUNT(*) FROM messages;
\q  # Exit
```

### Check application logs

When you run the ingestion pipeline or chat, you should see:
```
✓ Document saved to database: <doc_id> (source: <filename>)
```

Not seeing this? Run `test_db_connection.py` again to diagnose.

---

## 📝 Environment Variables (.env)

Your `.env` file should have:

```ini
# PDF Settings
PDF_FOLDER=data/pdfs
CHROMA_DIR=chroma_db

# LLM API Keys
GROQ_API_KEY=your_key_here
OPENROUTER_API_KEY=your_key_here

# Database Configuration (REQUIRED for data storage)
DB_USER=postgres
DB_PASSWORD=admin
DB_HOST=localhost
DB_PORT=5432
DB_NAME=rag-engine
```

---

## ⚡ What Happens Now

### When you ingest PDFs:
1. PDFs are loaded and chunked
2. Embeddings are generated (Chroma)
3. **Documents are saved to PostgreSQL** ← This now works!
4. Chunks are saved to ChromaDB

### When you chat:
1. Chat session is created in PostgreSQL
2. Each message is saved to PostgreSQL
3. Retriever queries ChromaDB for relevant chunks
4. LLM generates response

Both databases are now working together!

---

## 🔧 Advanced: Manual Table Creation

If `init_db.py` doesn't work, manually create tables:

```bash
psql -U postgres -d rag-engine

-- Create sessions table
CREATE TABLE sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL DEFAULT 'New Chat',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

-- Create messages table
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    INDEX (session_id)
);

-- Create documents table
CREATE TABLE documents (
    doc_id VARCHAR(255) PRIMARY KEY,
    source VARCHAR(255) NOT NULL,
    module VARCHAR(50),
    file_size INTEGER,
    chunk_count INTEGER DEFAULT 0,
    version VARCHAR(50),
    complexity VARCHAR(50),
    landscape VARCHAR(50),
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX (source),
    INDEX (ingested_at)
);

\q
```

---

## ✅ Checklist

- [ ] Run `python test_db_connection.py` and all checks pass
- [ ] Run `python init_db.py` successfully
- [ ] See ✓ Document saved to database logs when running pipeline
- [ ] Can query PostgreSQL and see data
- [ ] Application runs without database errors

Done! Your database is now storing data properly.
