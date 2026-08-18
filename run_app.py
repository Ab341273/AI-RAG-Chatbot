#!/usr/bin/env python3
"""
Startup script to initialize everything and run Streamlit app with tools + logging
"""
import subprocess
import sys
import os
from pathlib import Path

from config.Database import Base, engine
from models.sessions import ChatSession
from models.messages import ChatMessage
from services.logging_service import get_logger

logger = get_logger(__name__)

print("=" * 70)
print("🚀 DocuMind Chatbot - Starting up with Tool Calling & Logging")
print("=" * 70)

# Step 1: Check environment
print("\n🔍 Checking environment...")
try:
    from dotenv import load_dotenv
    load_dotenv()

    # Check for OpenRouter (primary) or GROQ (fallback)
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    openrouter_url = os.getenv("OPENROUTER_API_URL")
    openrouter_model = os.getenv("OPENROUTER_MODEL")

    groq_key = os.getenv("GROQ_API_KEY")
    groq_url = os.getenv("GROQ_API_URL")
    groq_model = os.getenv("GROQ_MODEL")

    if openrouter_key and openrouter_url:
        print(f"✅ Using OpenRouter")
        print(f"✅ OPENROUTER_API_KEY: Set")
        print(f"✅ OPENROUTER_URL: {openrouter_url}")
        print(f"✅ OPENROUTER_MODEL: {openrouter_model or 'default'}")
    elif groq_key and groq_url:
        print(f"✅ Using GROQ (OpenRouter not configured)")
        print(f"✅ GROQ_API_KEY: Set")
        print(f"✅ GROQ_API_URL: {groq_url}")
        print(f"✅ GROQ_MODEL: {groq_model or 'default'}")
    else:
        print("❌ Missing API credentials - need either OpenRouter or GROQ in .env")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error checking environment: {e}")
    sys.exit(1)

# Step 2: Initialize database
print("\n📊 Initializing database tables...")
try:
    Base.metadata.create_all(bind=engine)
    print("✅ Database ready")
    logger.info("[STARTUP] Database initialized successfully")
except Exception as e:
    print(f"❌ Error creating tables: {e}")
    logger.error(f"[STARTUP] Database initialization failed: {e}", exc_info=True)
    sys.exit(1)

# Step 3: Verify tools are accessible
print("\n🔧 Verifying tools...")
try:
    from services.tools import calculator, get_current_datetime, get_weather
    from langchain_core.utils.function_calling import convert_to_openai_tool

    tools = [convert_to_openai_tool(t) for t in [calculator, get_current_datetime, get_weather]]
    print(f"✅ Tools loaded: {[t['function']['name'] for t in tools]}")

    # Quick test
    test_result = calculator.invoke({"expression": "2+2"})
    print(f"✅ Calculator test: 2+2 = {test_result}")

    test_time = get_current_datetime.invoke({})
    print(f"✅ DateTime test: {test_time}")

    logger.info("[STARTUP] All tools verified successfully")
except Exception as e:
    print(f"❌ Error verifying tools: {e}")
    logger.error(f"[STARTUP] Tool verification failed: {e}", exc_info=True)
    sys.exit(1)

# Step 4: Launch Streamlit
print("\n" + "=" * 70)
print("🎨 Starting Streamlit app...")
print("=" * 70)
print("📍 App will open at: http://localhost:8501")
print("📝 Check console logs for [INFO] messages from tool calls")
print("=" * 70 + "\n")

logger.info("[STARTUP] All checks passed. Starting Streamlit app...")

try:
    # Get the script path
    script_path = Path(__file__).parent / "streamlit_app.py"

    subprocess.run([
        sys.executable, "-m", "streamlit", "run",
        str(script_path),
        "--logger.level=error"
    ], cwd=Path(__file__).parent)
except KeyboardInterrupt:
    print("\n\n👋 Shutting down...")
    logger.info("[SHUTDOWN] App terminated by user")
except Exception as e:
    print(f"\n❌ Error: {e}")
    logger.error(f"[SHUTDOWN] Error: {e}", exc_info=True)
    sys.exit(1)
