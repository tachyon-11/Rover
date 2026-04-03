import os
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.repository import FileRepository
from backend.services.llm_service import batch_organize_files
from backend.services.kafka_producer import publish_file_organized

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organize",
    tags=["Organize"]
)

ORGANIZED_FOLDER = os.getenv("ORGANIZED_FOLDER", "./organized")
BATCH_SIZE = 100


def get_file_type_folder(file_type: str) -> str:
    """Maps MIME type to human readable folder name"""
    type_map = {
        "application/pdf": "Documents",
        "application/msword": "Documents",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "Documents",
        "application/vnd.ms-excel": "Spreadsheets",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "Spreadsheets",
        "application/vnd.ms-powerpoint": "Presentations",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "Presentations",
        "text/plain": "Text",
        "text/csv": "Spreadsheets",
        "text/html": "Documents",
    }
    return type_map.get(file_type, "Documents")


@router.post("")
def trigger_organize(db: Session = Depends(get_db)):
    """
    Manually triggers batch organization of all parsed files.
    """
    repo = FileRepository(db)

    parsed_files = repo.get_by_status("parsed")

    if not parsed_files:
        return {"message": "No parsed files to organize", "organized": 0}

    batch = parsed_files[:BATCH_SIZE]
    logger.info(f"Organizing batch of {len(batch)} files...")

    files_for_llm = [
        {
            "file_id": str(f.id),
            "filename": f.filename,
            "file_type": f.file_type or "unknown",
            "file_description": f.file_description or f.filename
        }
        for f in batch
    ]

    try:
        organization_plan = batch_organize_files(files_for_llm)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"LLM organization failed: {str(e)}"
        )

    results = []
    plan_map = {p["file_id"]: p for p in organization_plan}

    for file_record in batch:
        file_id = str(file_record.id)
        plan = plan_map.get(file_id)

        if not plan:
            logger.warning(f"No plan for file: {file_record.filename}")
            continue

        try:
            new_path_relative = plan["new_path"]
            destination_path = os.path.join(ORGANIZED_FOLDER, new_path_relative)
            destination_dir = os.path.dirname(destination_path)

            os.makedirs(destination_dir, exist_ok=True)

            if os.path.exists(destination_path):
                name, ext = os.path.splitext(os.path.basename(destination_path))
                destination_path = os.path.join(
                    destination_dir,
                    f"{name}_{file_id[:8]}{ext}"
                )

            if os.path.exists(file_record.path):
                shutil.move(file_record.path, destination_path)
                logger.info(f"Moved: {file_record.filename} → {destination_path}")
            else:
                logger.warning(f"Source file not found: {file_record.path}")
                continue

            file_record.path = destination_path
            file_record.status = "organized"
            db.commit()

            publish_file_organized({
                "filename": file_record.filename,
                "path": destination_path,
                "file_id": file_id
            })

            results.append({
                "filename": file_record.filename,
                "new_path": destination_path,
                "status": "organized"
            })

        except Exception as e:
            logger.error(f"Failed to organize {file_record.filename}: {e}")
            db.rollback()
            results.append({
                "filename": file_record.filename,
                "status": "failed",
                "error": str(e)
            })

    return {
        "message": f"Organized {len(results)} files",
        "organized": len([r for r in results if r["status"] == "organized"]),
        "failed": len([r for r in results if r["status"] == "failed"]),
        "results": results
    }


@router.get("/status")
def organization_status(db: Session = Depends(get_db)):
    """
    Returns count of files in each status.
    """
    repo = FileRepository(db)
    return {
        "pending":    len(repo.get_by_status("pending")),
        "parsed":     len(repo.get_by_status("parsed")),
        "organized":  len(repo.get_by_status("organized")),
        "embedded":   len(repo.get_by_status("embedded")),
        "failed":     len(repo.get_by_status("failed"))
    }