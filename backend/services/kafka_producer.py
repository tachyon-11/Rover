import json
import logging
from kafka import KafkaProducer
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

_producer = None

def get_producer() -> KafkaProducer:
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            value_serializer=lambda v: json.dumps(v).encode("utf-8")
        )
        logger.info("Kafka producer created")
    return _producer


def publish_file_detected(file_data: dict):
    """
    Publishes a message to the file.detected Kafka topic.
    Called every time the watcher sees a new file.
    """
    producer = get_producer()
    producer.send("file.detected", value=file_data)
    producer.flush()  # ensures message is actually sent before moving on
    logger.info(f"Published to file.detected: {file_data['filename']}")
    
def publish_file_parsed(file_data: dict):
    """Publishes to file.parsed topic"""
    producer = get_producer()
    producer.send("file.parsed", value=file_data)
    producer.flush()
    logger.info(f"Published to file.parsed: {file_data['filename']}")


def publish_file_organized(file_data: dict):
    """Publishes to file.organized topic"""
    producer = get_producer()
    producer.send("file.organized", value=file_data)
    producer.flush()
    logger.info(f"Published to file.organized: {file_data['filename']}")