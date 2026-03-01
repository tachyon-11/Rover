from fastapi import FastAPI
from backend.routers import health

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WATCH_FOLDER = os.getenv("WATCH_FOLDER", "./watch_folder")

@asynccontextmanager
async def lifespan(app: FastAPI):
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
    version="1.0.0"
)

app.include_router(health.router)