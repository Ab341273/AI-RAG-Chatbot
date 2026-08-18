from rag_handler.retriever import retrieve_similar_chunks

results = retrieve_similar_chunks(" wintroduction of rc4", k=3)
for i, item in enumerate(results, start=1):
    print(i, item["metadata"], item["document"][:200])