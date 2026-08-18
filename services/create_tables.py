from config.Database import Base, engine

# Models import karna IMPORTANT hai
from models.sessions import ChatSession
from models.messages import ChatMessage 


Base.metadata.create_all(bind=engine)

print("Database tables created successfully!")