import os
import threading
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.consumers.tika_parser import start_tika_consumer
from backend.db.database import create_tables
from backend.routers import health, organize, search
from backend.services.watcher import start_watcher
from backend.services.kafka_admin import create_topics
from backend.consumers.embedding_consumer import start_embedding_consumer

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./watch_folder")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    create_tables()  
    
    logger.info("Creating Kafka topics...")
    create_topics()

    logger.info("Starting Tika parser consumer...")
    tika_thread = threading.Thread(              
        target = start_tika_consumer,
        daemon=True
    )
    tika_thread.start()
    
    logger.info("Starting embedding consumer...")
    embedding_thread = threading.Thread(
        target=start_embedding_consumer,
        daemon=True
    )
    embedding_thread.start()
    
    logger.info("Starting file watcher...")
    watcher_thread = threading.Thread(
        target=start_watcher,
        args=(WATCH_FOLDER,),
        daemon=True
    )
    watcher_thread.start()
    logger.info(f"Watcher started on folder: {WATCH_FOLDER}")

    yield

    logger.info("Shutting down...")

app = FastAPI(
    title="Rover",
    description="API for the Smart File Organizer project",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(health.router)
app.include_router(organize.router)
app.include_router(search.router)