import json
import logging
import os
import requests
from kafka import KafkaConsumer
from dotenv import load_dotenv
from backend.db.database import SessionLocal
from backend.db.repository import FileRepository

load_dotenv()

logger = logging.getLogger(__name__)

TIKA_URL = os.getenv("TIKA_URL", "http://localhost:9998")
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Parse file using Tika
def parse_with_tika(file_path: str) -> dict:
    """
    Sends file to Tika server and gets back
    extracted text and metadata.
    """
    try:
        # Extract text content
        text_response = requests.put(
            f"{TIKA_URL}/tika",
            data=open(file_path, "rb"),
            headers={"Accept": "text/plain"},
            timeout=30
        )

        # Extract metadata
        metadata_response = requests.put(
            f"{TIKA_URL}/meta",
            data=open(file_path, "rb"),
            headers={"Accept": "application/json"},
            timeout=30
        )

        extracted_text = text_response.text.strip()
        metadata = metadata_response.json()

        # Get file type from metadata
        file_type = metadata.get("Content-Type", "unknown")

        logger.info(f"Tika parsed: {file_path} → {file_type}")

        return {
            "extracted_text": extracted_text,
            "file_type": file_type,
            "metadata": metadata
        }

    except requests.exceptions.Timeout:
        logger.error(f"Tika timeout for: {file_path}")
        raise
    except Exception as e:
        logger.error(f"Tika error for {file_path}: {e}")
        raise


# Main consumer loop
def start_tika_consumer():
    """
    Reads from file.detected Kafka topic.
    For each message:
    1. Creates DB record (status=pending)
    2. Sends file to Tika
    3. Updates DB with extracted text (status=parsed)
    4. Publishes to file.parsed topic
    5. Commits Kafka offset
    """
    logger.info("Starting Tika parser consumer...")

    consumer = KafkaConsumer(
        "file.detected",
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        group_id="tika-parser-group",
        value_deserializer=lambda v: json.loads(v.decode("utf-8")),
        auto_offset_reset="earliest",   # start from beginning if no offset
        enable_auto_commit=False,        # manual commit for reliability
    )

    logger.info("Tika consumer connected to Kafka, waiting for messages...")

    for message in consumer:
        file_data = message.value
        logger.info(f"Received: {file_data['filename']}")

        db = SessionLocal()
        try:
            repo = FileRepository(db)

            file_record = repo.create(file_data)
            logger.info(f"DB record created: {file_record.id}")

            tika_result = parse_with_tika(file_data["path"])

            repo.update_parsed(
                file_id=file_record.id,
                extracted_text=tika_result["extracted_text"],
                file_type=tika_result["file_type"],
                metadata=tika_result["metadata"]
            )

            consumer.commit()
            logger.info(f"✅ Parsed and committed: {file_data['filename']}")

        except Exception as e:
            logger.error(f"❌ Failed to process {file_data['filename']}: {e}")
            db.rollback()

        finally:
            db.close()