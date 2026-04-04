import os
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.db.database import get_db
from backend.db.repository import FileRepository
from backend.services.llm_service import (
    generate_folder_taxonomy,
    assign_files_to_taxonomy
)
from backend.services.kafka_producer import publish_file_organized

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/organize",
    tags=["Organize"]
)

ORGANIZED_FOLDER = os.getenv("ORGANIZED_FOLDER", "./organized")
CHUNK_SIZE = 10

FILE_TYPE_MAP = {
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
    "image/jpeg": "Images",
    "image/png": "Images",
    "image/gif": "Images",
}


def scan_existing_folders(base_path: str) -> list[str]:
    """
    Scans organized/ folder and returns
    existing folder structure as a list of paths.
    Gives LLM context of what already exists.
    """
    existing = []
    if not os.path.exists(base_path):
        return existing

    for root, dirs, files in os.walk(base_path):
        # Skip hidden folders like .DS_Store
        dirs[:] = [d for d in dirs if not d.startswith('.')]
        for d in dirs:
            folder_path = os.path.relpath(
                os.path.join(root, d),
                base_path
            )
            existing.append(folder_path)

    return sorted(existing)


@router.post("")
def trigger_organize(db: Session = Depends(get_db)):
    """
    Manually triggers batch organization of all parsed files.

    Two pass approach:
    Pass 1 — Generate master folder taxonomy using ALL descriptions
             + existing folder structure
    Pass 2 — Assign files to taxonomy in chunks of 10
             Each chunk has full taxonomy as context
    """
    repo = FileRepository(db)

    parsed_files = repo.get_by_status("parsed")

    if not parsed_files:
        return {
            "message": "No parsed files to organize",
            "organized": 0
        }

    logger.info(f"Found {len(parsed_files)} parsed files to organize")

    existing_folders = scan_existing_folders(ORGANIZED_FOLDER)
    logger.info(f"Found {len(existing_folders)} existing folders")

    files_data = [
        {
            "file_id": str(f.id),
            "filename": f.filename,
            "file_type": f.file_type or "unknown",
            "file_description": f.file_description or f.filename,
            "path": f.path
        }
        for f in parsed_files
    ]

    try:
        taxonomy = generate_folder_taxonomy(
            files=files_data,
            existing_folders=existing_folders
        )
        logger.info(f"Master taxonomy: {[f.category for f in taxonomy.folders]}")
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Taxonomy generation failed: {str(e)}"
        )

    all_plans = []

    for i in range(0, len(files_data), CHUNK_SIZE):
        chunk = files_data[i:i + CHUNK_SIZE]
        logger.info(
            f"Assigning chunk {i//CHUNK_SIZE + 1} "
            f"({len(chunk)} files)..."
        )

        try:
            chunk_plan = assign_files_to_taxonomy(
                files=chunk,
                taxonomy=taxonomy,
                file_type_map=FILE_TYPE_MAP
            )
            all_plans.extend(chunk_plan.files)
        except Exception as e:
            logger.error(f"Chunk {i//CHUNK_SIZE + 1} failed: {e}")
            continue

    plan_map = {p.file_id: p for p in all_plans}
    results = []

    for file_record in parsed_files:
        file_id = str(file_record.id)
        plan = plan_map.get(file_id)

        if not plan:
            logger.warning(f"No plan for: {file_record.filename}")
            continue

        try:
            clean_path = plan.new_path.lstrip('/')

            destination_path = os.path.join(
                ORGANIZED_FOLDER,
                clean_path
            )
            destination_dir = os.path.dirname(destination_path)
            os.makedirs(destination_dir, exist_ok=True)

            if os.path.exists(destination_path):
                name, ext = os.path.splitext(
                    os.path.basename(destination_path)
                )
                destination_path = os.path.join(
                    destination_dir,
                    f"{name}_{file_id[:8]}{ext}"
                )

            if os.path.exists(file_record.path):
                shutil.move(file_record.path, destination_path)
                logger.info(
                    f"Moved: {file_record.filename} → {plan.new_path}"
                )
            else:
                logger.warning(
                    f"Source not found: {file_record.path}"
                )
                continue

            file_record.path = destination_path
            file_record.status = "organized"
            db.commit()

            publish_file_organized({
                "filename": file_record.filename,
                "path": destination_path,
                "file_id": file_id,
            })

            results.append({
                "filename": file_record.filename,
                "new_path": plan.new_path,
                "status": "organized"
            })

        except Exception as e:
            logger.error(
                f"Failed to organize {file_record.filename}: {e}"
            )
            db.rollback()
            results.append({
                "filename": file_record.filename,
                "status": "failed",
                "error": str(e)
            })

    organized = len([r for r in results if r["status"] == "organized"])
    failed = len([r for r in results if r["status"] == "failed"])

    return {
        "message": f"Organized {organized} files",
        "organized": organized,
        "failed": failed,
        "taxonomy": [
            {
                "category": f.category,
                "subcategories": f.subcategories
            }
            for f in taxonomy.folders
        ],
        "results": results
    }


@router.get("/status")
def organization_status(db: Session = Depends(get_db)):
    """Returns count of files in each status."""
    repo = FileRepository(db)
    return {
        "pending":   len(repo.get_by_status("pending")),
        "parsed":    len(repo.get_by_status("parsed")),
        "organized": len(repo.get_by_status("organized")),
        "embedded":  len(repo.get_by_status("embedded")),
        "failed":    len(repo.get_by_status("failed"))
    }