import logging
import uuid
import ollama
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.repository import FileRepository
from backend.services.embedding_service import search_similar, get_collection_stats
from backend.prompts import PromptType
from backend.prompts import rag as rag_prompt

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/search",
    tags=["Search"]
)

MODEL = "llama3.2"

class SearchRequest(BaseModel):
    query: str
    n_results: int = 5

class FileResult(BaseModel):
    file_id: str
    filename: str
    file_path: str
    file_description: str
    file_type: str
    status: str
    similarity_score: float


class SearchResponse(BaseModel):
    query: str
    answer: str
    sources: list[FileResult]
    total_found: int


@router.post("", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Full RAG semantic search pipeline:
    Step 1 — Embed query, search ChromaDB for top N similar files
    Step 2 — Fetch full file records from PostgreSQL
    Step 3 — Send query + file contents to LLM for grounded answer
    Step 4 — Return answer + source files with similarity scores
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    logger.info(
        f"[{PromptType.RAG.value}] Search query: {request.query}"
    )

    try:
        chroma_results = search_similar(
            query=request.query,
            n_results=request.n_results
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

    ids = chroma_results["ids"][0]
    distances = chroma_results["distances"][0]

    if not ids:
        return SearchResponse(
            query=request.query,
            answer="No relevant files found in your collection.",
            sources=[],
            total_found=0
        )

    repo = FileRepository(db)
    sources = []
    files_for_rag = []

    for file_id, distance in zip(ids, distances):
        try:
            file_record = repo.get_by_id(uuid.UUID(file_id))
            if not file_record:
                continue
            
            similarity_score = round(1 - (distance / 2), 4)

            sources.append(FileResult(
                file_id=str(file_record.id),
                filename=file_record.filename,
                file_path=file_record.path,
                file_description=file_record.file_description or "",
                file_type=file_record.file_type or "unknown",
                status=file_record.status,
                similarity_score=similarity_score
            ))

            files_for_rag.append({
                "filename": file_record.filename,
                "file_path": file_record.path,
                "file_description": file_record.file_description or "",
                "extracted_text": file_record.extracted_text or ""
            })

        except Exception as e:
            logger.error(f"Error fetching file {file_id}: {e}")
            continue

    sources.sort(key=lambda x: x.similarity_score, reverse=True)

    try:
        prompt = rag_prompt.build(
            query=request.query,
            files=files_for_rag
        )

        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = (response.message.content or "").strip()

    except Exception as e:
        logger.error(f"LLM error during RAG: {e}")
        answer = "Could not generate answer — search results shown below."

    return SearchResponse(
        query=request.query,
        answer=answer,
        sources=sources,
        total_found=len(sources)
    )


@router.get("/stats")
def embedding_stats():
    try:
        return get_collection_stats()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Could not get stats: {str(e)}"
        )