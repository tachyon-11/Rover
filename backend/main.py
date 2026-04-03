import os
import threading
import logging
from fastapi import FastAPI
from contextlib import asynccontextmanager
from backend.db.database import create_tables
from backend.routers import health
from backend.services.watcher import start_watcher
from backend.services.kafka_admin import create_topics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./watch_folder")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Creating database tables...")
    create_tables()  
    
    logger.info("Creating Kafka topics...")
    create_topics()

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