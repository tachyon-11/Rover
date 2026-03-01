import logging
import os
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

TOPICS = [
    ("file.detected",  1, 1),
    ("file.parsed",    1, 1),
    ("file.organized", 1, 1),
    ("file.failed",    1, 1),
]


def create_topics():
    try:
        logger.info("Attempting to create Kafka topics...")

        admin_client = KafkaAdminClient(
            bootstrap_servers=os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        )

        existing_topics = admin_client.list_topics()

        topics_to_create = [
            NewTopic(
                name=name,
                num_partitions=partitions,
                replication_factor=replication_factor
            )
            for name, partitions, replication_factor in TOPICS
            if name not in existing_topics
        ]

        if topics_to_create:
            admin_client.create_topics(new_topics=topics_to_create)
            for topic in topics_to_create:
                logger.info(f"Created Kafka topic: {topic.name}")
        else:
            logger.info("All Kafka topics already exist")

        admin_client.close()

    except TopicAlreadyExistsError:
        logger.info("Topics already exist, skipping creation")

    except Exception as e:
        logger.error(f"Failed to create Kafka topics: {e}")
        raise