import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

load_dotenv()

# Check if running in Streamlit Cloud or local
def is_streamlit_cloud():
    try:
        import streamlit as st
        host = st.secrets.get("DB_HOST", "")
        # If host is localhost/127.0.0.1, it's local dev - disable SSL
        # Otherwise it's cloud - enable SSL
        return host and "localhost" not in host.lower() and "127.0.0.1" not in host
    except:
        return False

# Get database configuration
if is_streamlit_cloud():
    import streamlit as st
    # Streamlit Cloud
    DB_USER = st.secrets["DB_USER"]
    DB_PASSWORD = st.secrets["DB_PASSWORD"]
    DB_HOST = st.secrets["DB_HOST"]
    DB_PORT = st.secrets.get("DB_PORT", "5432")
    DB_NAME = st.secrets["DB_NAME"]
else:
    # Local development
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_HOST = os.getenv("DB_HOST")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise ValueError(
        "Missing database configuration"
    )

ssl_mode = "require" if is_streamlit_cloud() else "disable"

DATABASE_URL = (
    f"postgresql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?sslmode={ssl_mode}"
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()