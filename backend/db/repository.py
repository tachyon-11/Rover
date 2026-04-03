import uuid
import logging
from typing import Optional
from sqlalchemy.orm import Session
from backend.models.file import File

logger = logging.getLogger(__name__)

# Valid status transitions — prevents invalid pipeline jumps
VALID_TRANSITIONS = {
    "pending":   ["parsed", "failed"],
    "parsed":    ["organized", "failed"],
    "organized": ["embedded", "failed"],
    "embedded":  [],
    "failed":    []
}


class FileRepository:
    """
    Repository pattern — ALL database operations live here.
    API layer and consumers never write raw SQL.
    One place to change if we ever swap PostgreSQL.
    """

    def __init__(self, db: Session):
        self.db = db

    # CREATE
    def create(self, file_data: dict) -> File:
        """
        Creates a new file record with status 'pending'.
        Checks for existing file first — idempotent.
        """
        # Idempotency check — don't create duplicate records
        existing = self.get_by_path(file_data["path"])
        if existing:
            logger.info(f"File already exists: {file_data['path']}")
            return existing

        file = File(
            filename=file_data["filename"],
            path=file_data["path"],
            size_bytes=file_data.get("size_bytes"),
            status="pending"
        )
        self.db.add(file)
        self.db.commit()
        self.db.refresh(file)
        logger.info(f"Created file record: {file.filename} [{file.id}]")
        return file

    # READ
    def get_by_id(self, file_id: uuid.UUID) -> Optional[File]:
        return self.db.query(File).filter(File.id == file_id).first()

    def get_by_path(self, path: str) -> Optional[File]:
        """
        Get file by path.
        Used for idempotency check in create().
        """
        return self.db.query(File).filter(
            File.path == path
        ).first()

    def get_all(self) -> list[File]:
        return self.db.query(File).order_by(
            File.created_at.desc()
        ).all()

    def get_by_status(self, status: str) -> list[File]:
        return self.db.query(File).filter(
            File.status == status
        ).all()

    # UPDATE
    def update_status(self, file_id: uuid.UUID, new_status: str) -> Optional[File]:
        """
        Update file processing status.
        Validates transition is allowed before updating.
        """
        file = self.get_by_id(file_id)
        if not file:
            logger.error(f"File not found: {file_id}")
            return None

        # Validate status transition
        allowed = VALID_TRANSITIONS.get(file.status, [])
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {file.status} → {new_status}. "
                f"Allowed: {allowed}"
            )

        file.status = new_status
        self.db.commit()
        self.db.refresh(file)
        logger.info(f"Status updated: {file.filename} → {new_status}")
        return file

    def update_parsed(
        self,
        file_id: uuid.UUID,
        extracted_text: str,
        file_type: str,
        metadata: dict,
        description: str        # ← add this
    ) -> Optional[File]:
        file = self.get_by_id(file_id)
        if not file:
            return None

        file.extracted_text = extracted_text
        file.file_type = file_type
        file.file_metadata = metadata
        file.file_description = description   # ← add this
        file.status = "parsed"
        self.db.commit()
        self.db.refresh(file)
        logger.info(f"Parsed data saved: {file.filename}")
        return file