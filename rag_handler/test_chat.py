from rag_handler.chat import answer_query

query = "strong pokemon"
answer = answer_query(query, k=3)
print("Query:", query)
print("Answer:", answer)