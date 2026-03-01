import os
import time
import logging
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from backend.services.kafka_producer import publish_file_detected

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FileHandler(FileSystemEventHandler):

    def on_created(self, event):
        """
        Triggered automatically by Watchdog
        every time a new file appears in the watch folder.
        """

        # Ignore folder creation events — only care about files
        if event.is_directory:
            return

        file_path = event.src_path

        time.sleep(0.5)

        if not os.path.exists(file_path):
            return

        logger.info(f"New file detected: {file_path}")

        # Build the message payload to send to Kafka
        file_data = {
            "filename": os.path.basename(file_path),
            "path": file_path,
            "size_bytes": os.path.getsize(file_path),
            "detected_at": datetime.utcnow().isoformat()
        }

        # Publish to Kafka — Observer fires the event
        publish_file_detected(file_data)

def start_watcher(watch_folder: str):
    """
    Starts watching the given folder for new files.
    Runs forever until manually stopped.
    """
    os.makedirs(watch_folder, exist_ok=True)

    event_handler = FileHandler()
    observer = Observer()

    observer.schedule(event_handler, watch_folder, recursive=True)
    observer.start()

    logger.info(f"Watching folder: {watch_folder}")

    try:
        while True:
            time.sleep(1)  
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Watcher stopped")

    observer.join()