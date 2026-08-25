from pathlib import Path
from typing import Any, Dict, List
from functools import lru_cache

import chromadb
from sentence_transformers import SentenceTransformer, CrossEncoder

from services.logging_service import get_logger

logger = get_logger(__name__)


BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"

COLLECTION_NAME = "pdf_documents"

EMBEDDING_MODEL = "all-MiniLM-L6-v2"

RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"

# [OPTIMIZATION] Retrieval parameters tuned for speed
# How many chunks to retrieve from ChromaDB
RETRIEVAL_K = 8  # Previously 3 - balance between coverage and speed

# How many chunks to finally send to the LLM
FINAL_K = 3  # Previously 2 - better coverage without much overhead


@lru_cache(maxsize=1)
def create_embedding_model(
    model_name: str = EMBEDDING_MODEL,
) -> SentenceTransformer:
    logger.info(f"[EMBEDDING MODEL] Loading: {model_name}")
    model = SentenceTransformer(model_name)
    logger.info(f"[EMBEDDING MODEL] Loaded successfully")
    return model


@lru_cache(maxsize=1)
def create_reranker(
    model_name: str = RERANKER_MODEL,
) -> CrossEncoder:
    logger.info(f"[RERANKER MODEL] Loading: {model_name}")
    reranker = CrossEncoder(model_name)
    logger.info(f"[RERANKER MODEL] Loaded successfully")
    return reranker


def load_chroma_collection(
    persist_dir: Path = CHROMA_DIR,
    collection_name: str = COLLECTION_NAME,
) -> chromadb.api.models.Collection:

    persist_dir.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(persist_dir)
    )

    return client.get_or_create_collection(
        name=collection_name
    )


def embed_query(
    query: str,
    model: SentenceTransformer,
) -> List[float]:

    embedding = model.encode(
        [query],
        convert_to_numpy=True
    )[0]

    return embedding.tolist()


def retrieve_similar_chunks(
    query: str,
    retrieval_k: int = RETRIEVAL_K,
    final_k: int = FINAL_K,
    model_name: str = EMBEDDING_MODEL,
    persist_dir: Path = CHROMA_DIR,
    collection_name: str = COLLECTION_NAME,
) -> List[Dict[str, Any]]:

    # --------------------------------------------------
    # 1. Load embedding model
    # --------------------------------------------------

    model = create_embedding_model(model_name)

    # --------------------------------------------------
    # 2. Convert user query into embedding
    # --------------------------------------------------

    query_embedding = embed_query(
        query,
        model
    )

    # --------------------------------------------------
    # 3. Load ChromaDB collection
    # --------------------------------------------------

    collection = load_chroma_collection(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    # --------------------------------------------------
    # 4. Retrieve candidates from ChromaDB
    # --------------------------------------------------

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=retrieval_k,
        include=[
            "documents",
            "metadatas",
            "distances",
        ],
    )

    docs = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    # --------------------------------------------------
    # 5. Prepare documents for reranking
    # --------------------------------------------------

    candidates = []

    for doc, metadata, distance in zip(
        docs,
        metadatas,
        distances
    ):

        candidates.append(
            {
                "document": doc,
                "metadata": metadata,
                "distance": distance,
            }
        )

    if not candidates:
        logger.info(f"[RETRIEVAL] No candidates found in ChromaDB for query: {query[:100]}")
        return []

    logger.info(f"[RETRIEVAL] Retrieved {len(candidates)} candidates from ChromaDB")

    # [OPTIMIZATION TEST] Reranker DISABLED temporarily
    # Comment back in if you want reranking
    # This helps identify if reranker is the bottleneck (33s issue)

    # reranker = create_reranker()
    # pairs = [
    #     [query, candidate["document"]]
    #     for candidate in candidates
    # ]
    # scores = reranker.predict(pairs)
    # for candidate, score in zip(candidates, scores):
    #     candidate["rerank_score"] = float(score)
    # candidates.sort(key=lambda x: x["rerank_score"], reverse=True)

    # [OPTIMIZATION] Without reranker: use ChromaDB distance as score
    for candidate in candidates:
        candidate["rerank_score"] = 1.0 - candidate["distance"]  # Convert distance to similarity

    final_results = candidates[:final_k]

    if final_results:
        rerank_scores = [c["rerank_score"] for c in final_results]
        logger.info(
            f"[RETRIEVAL] After reranking: {len(final_results)} chunks returned | "
            f"Rerank scores: min={min(rerank_scores):.3f}, max={max(rerank_scores):.3f}, avg={sum(rerank_scores)/len(rerank_scores):.3f}"
        )

    return final_results