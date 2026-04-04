import logging
import os
import chromadb
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "files"
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8001"))

_model = None
_client = None
_collection = None


def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
        logger.info("Embedding model loaded")
    return _model


def get_collection():
    global _client, _collection
    if _collection is None:
        _client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT
        )
        _collection = _client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
        logger.info(f"ChromaDB collection ready: {COLLECTION_NAME}")
    return _collection


def embed_text(text: str) -> list[float]:
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def store_embedding(
    file_id: str,
    file_description: str,
    metadata: dict
) -> None:
    """
    Generates embedding from file_description
    and upserts in ChromaDB with metadata.
    Safe to call multiple times — upsert updates existing.
    """
    collection = get_collection()
    embedding = embed_text(file_description)

    collection.upsert(
        ids=[file_id],
        embeddings=[embedding],
        documents=[file_description],
        metadatas=[metadata]
    )
    logger.info(f"Stored embedding for: {metadata.get('filename', file_id)}")


def search_similar(
    query: str,
    n_results: int = 5,
    where: dict | None = None
) -> dict:
    """
    Embeds query and finds top n similar files in ChromaDB.
    """
    collection = get_collection()
    query_embedding = embed_text(query)

    query_kwargs: dict = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"]
    }
    if where is not None:
        query_kwargs["where"] = where

    results = collection.query(**query_kwargs)
    logger.info(f"Search complete: found {len(results['ids'][0])} results")
    return dict(results)


def delete_embedding(file_id: str) -> None:
    collection = get_collection()
    collection.delete(ids=[file_id])
    logger.info(f"Deleted embedding: {file_id}")


def get_collection_stats() -> dict:
    collection = get_collection()
    count = collection.count()
    return {
        "collection": COLLECTION_NAME,
        "total_embeddings": count
    }