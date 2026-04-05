import logging
import uuid
from datetime import datetime
from typing import Optional
import ollama
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.repository import FileRepository
from backend.services.embedding_service import search_similar, get_collection_stats
from backend.services.cache_service import (
    get_cached_result,
    set_cached_result,
    invalidate_search_cache,
    get_cache_stats
)
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
    cached: bool = False

@router.post("", response_model=SearchResponse)
def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db)
):
    """
    Full RAG semantic search pipeline with Redis caching:
    Step 1 — Check Redis cache (returns instantly if hit)
    Step 2 — Embed query, search ChromaDB
    Step 3 — Fetch full records from PostgreSQL
    Step 4 — RAG: LLM generates grounded answer
    Step 5 — Cache result in Redis for 30 mins
    Step 6 — Return answer + source files
    """
    if not request.query.strip():
        raise HTTPException(
            status_code=400,
            detail="Query cannot be empty"
        )

    logger.info(
        f"[{PromptType.RAG.value}] "
        f"Search query: {request.query}"
    )

    cached = get_cached_result(request.query, request.n_results)
    if cached:
        cached["cached"] = True
        return SearchResponse(**cached)

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
            total_found=0,
            cached=False
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

    result = SearchResponse(
        query=request.query,
        answer=answer,
        sources=sources,
        total_found=len(sources),
        cached=False
    )

    set_cached_result(
        query=request.query,
        n_results=request.n_results,
        result=result.model_dump()
    )

    return result

@router.get("/metadata")
def metadata_search(
    file_type: Optional[str] = Query(None, description="e.g. application/pdf"),
    status: Optional[str] = Query(None, description="pending/parsed/organized/embedded"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD"),
    db: Session = Depends(get_db)
):
    from backend.models.file import File
    from sqlalchemy import and_

    query = db.query(File)
    filters = []

    if file_type:
        filters.append(File.file_type == file_type)

    if status:
        filters.append(File.status == status)

    if date_from:
        try:
            date_from_dt = datetime.strptime(date_from, "%Y-%m-%d")
            filters.append(File.created_at >= date_from_dt)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_from must be in YYYY-MM-DD format"
            )

    if date_to:
        try:
            date_to_dt = datetime.strptime(date_to, "%Y-%m-%d")
            filters.append(File.created_at <= date_to_dt)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="date_to must be in YYYY-MM-DD format"
            )

    if filters:
        query = query.filter(and_(*filters))

    files = query.order_by(File.created_at.desc()).all()

    return {
        "total": len(files),
        "filters_applied": {
            "file_type": file_type,
            "status": status,
            "date_from": date_from,
            "date_to": date_to
        },
        "results": [
            {
                "file_id": str(f.id),
                "filename": f.filename,
                "file_path": f.path,
                "file_type": f.file_type,
                "status": f.status,
                "file_description": f.file_description,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in files
        ]
    }

@router.delete("/cache")
def clear_cache():
    """Clears all cached search results."""
    deleted = invalidate_search_cache()
    return {"message": f"Cache cleared: {deleted} entries deleted"}


@router.get("/stats")
def search_stats():
    """Returns ChromaDB and Redis cache statistics."""
    return {
        "chromadb": get_collection_stats(),
        "cache": get_cache_stats()
    }