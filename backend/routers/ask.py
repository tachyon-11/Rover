import logging
import uuid
import ollama
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.repository import FileRepository
from backend.services.embedding_service import search_similar
from backend.services.conversation_service import (
    generate_session_id,
    get_history,
    save_message,
    clear_conversation,
    get_conversation_stats
)
from backend.prompts import PromptType
from backend.prompts import ask as ask_prompt

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/ask",
    tags=["Ask"]
)

MODEL = "llama3.2"
TOP_K = 5                 
MIN_SIMILARITY = 0.5       

class AskRequest(BaseModel):
    question: str
    session_id: Optional[str] = None   # if None → new conversation


class Citation(BaseModel):
    file_id: str
    filename: str
    file_path: str
    similarity_score: float


class AskResponse(BaseModel):
    answer: str
    session_id: str
    citations: list[Citation]
    question: str
    history_length: int


@router.post("", response_model=AskResponse)
def ask_question(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    if not request.question.strip():
        raise HTTPException(
            status_code=400,
            detail="Question cannot be empty"
        )

    session_id = request.session_id or generate_session_id()
    logger.info(
        f"[{PromptType.ASK.value}] "
        f"Session: {session_id[:8]}... "
        f"Question: {request.question[:50]}"
    )

    history = get_history(session_id)
    logger.info(f"History loaded: {len(history)} messages")

    try:
        chroma_results = search_similar(
            query=request.question,
            n_results=TOP_K
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )

    ids = chroma_results["ids"][0]
    distances = chroma_results["distances"][0]

    repo = FileRepository(db)
    files_for_rag = []
    citations = []

    for file_id, distance in zip(ids, distances):
        similarity_score = round(1 - (distance / 2), 4)

        if similarity_score < MIN_SIMILARITY:
            logger.info(
                f"Skipping low similarity file: "
                f"{similarity_score}"
            )
            continue

        try:
            file_record = repo.get_by_id(uuid.UUID(file_id))
            if not file_record:
                continue

            files_for_rag.append({
                "filename": file_record.filename,
                "file_path": file_record.path,
                "file_description": file_record.file_description or "",
                "extracted_text": file_record.extracted_text or ""
            })

            citations.append(Citation(
                file_id=str(file_record.id),
                filename=file_record.filename,
                file_path=file_record.path,
                similarity_score=similarity_score
            ))

        except Exception as e:
            logger.error(f"Error fetching file {file_id}: {e}")
            continue

    if not files_for_rag:
        answer = (
            "I couldn't find relevant information "
            "about that in your files."
        )
        # Still save to history so conversation flows naturally
        save_message(session_id, "user", request.question)
        save_message(session_id, "assistant", answer)

        return AskResponse(
            answer=answer,
            session_id=session_id,
            citations=[],
            question=request.question,
            history_length=len(history) + 2
        )

    prompt = ask_prompt.build(
        question=request.question,
        files=files_for_rag,
        history=history
    )

    try:
        response = ollama.chat(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}]
        )
        answer = (response.message.content or "").strip()

    except Exception as e:
        logger.error(f"LLM error: {e}")
        answer = (
            "I encountered an error generating an answer. "
            "Please try again."
        )

    save_message(session_id, "user", request.question)
    save_message(session_id, "assistant", answer)

    logger.info(
        f"✅ Answer generated for session: {session_id[:8]}..."
    )

    return AskResponse(
        answer=answer,
        session_id=session_id,
        citations=citations,
        question=request.question,
        history_length=len(history) + 2
    )

@router.get("/{session_id}/history")
def get_conversation_history(session_id: str):
    history = get_history(session_id)
    if not history:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    return {
        "session_id": session_id,
        "messages": history,
        "total": len(history)
    }


@router.delete("/{session_id}")
def clear_session(session_id: str):
    cleared = clear_conversation(session_id)
    if not cleared:
        raise HTTPException(
            status_code=404,
            detail=f"Session not found: {session_id}"
        )
    return {"message": f"Session cleared: {session_id}"}


@router.get("/{session_id}/stats")
def session_stats(session_id: str):
    return get_conversation_stats(session_id)