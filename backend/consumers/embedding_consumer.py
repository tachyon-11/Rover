import json
import logging
import os
import uuid
from kafka import KafkaConsumer
from dotenv import load_dotenv
from backend.db.database import SessionLocal
from backend.db.repository import FileRepository
from backend.services.embedding_service import store_embedding

load_dotenv()

logger = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv(
    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
)


def embed_file(file_record, db) -> bool:
    if not file_record.file_description:
        logger.warning(f"No description for: {file_record.filename}")
        return False

    store_embedding(
        file_id=str(file_record.id),
        file_description=file_record.file_description,
        metadata={
            "filename": file_record.filename,
            "file_type": file_record.file_type or "unknown",
            "file_path": file_record.path,
            "status": file_record.status
        }
    )

    if file_record.status != "embedded":
        file_record.status = "embedded"
        db.commit()

    logger.info(f"✅ Embedded: {file_record.filename}")
    return True


def start_embedding_consumer():
    """
    Reads from file.parsed topic.
    Embeds as soon as description is ready.
    """
    logger.info("Starting embedding consumer...")

    consumer = KafkaConsumer(
        "file.parsed",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="embedding-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",
        enable_auto_commit=False,
    )

    logger.info("Embedding consumer connected, waiting for messages...")

    for message in consumer:
        file_data = message.value
        logger.info(f"Received: {file_data.get('filename')}")

        db = SessionLocal()
        try:
            repo = FileRepository(db)

            file_id = file_data.get("file_id")
            if not file_id:
                logger.warning("No file_id in message, skipping")
                consumer.commit()
                continue

            file_record = repo.get_by_id(uuid.UUID(file_id))
            if not file_record:
                logger.warning(f"File not found: {file_id}")
                consumer.commit()
                continue

            embed_file(file_record, db)
            consumer.commit()

        except Exception as e:
            logger.error(
                f"❌ Failed to embed {file_data.get('filename')}: {e}"
            )
            db.rollback()

        finally:
            db.close()