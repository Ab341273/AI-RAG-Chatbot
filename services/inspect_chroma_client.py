import inspect
from chromadb.config import Settings
import chromadb

print('chromadb version:', chromadb.__version__)
client = chromadb.Client(settings=Settings(persist_directory='chroma_db'))
print('client type:', type(client))
print('has persist:', hasattr(client, 'persist'))
print('methods:')
for name, value in inspect.getmembers(client, predicate=inspect.isroutine):
    if not name.startswith('_'):
        print(name)
