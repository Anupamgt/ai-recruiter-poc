"""Local folder watcher for CV file ingestion.

Simulates a cloud storage trigger:
- Production: GCS bucket object-created event → Eventarc → Cloud Function
- PoC: watchdog filesystem observer → async pipeline call
"""
import asyncio
import logging
import os
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

logger = logging.getLogger(__name__)

# Track processed files to avoid re-processing on restart
_processed_files: set[str] = set()
_observer: Observer | None = None


class CVFileHandler(FileSystemEventHandler):
    """Handle new CV files dropped into the watch directory.
    
    In production, this entire class would be replaced by:
    1. A GCS bucket with an object-created trigger
    2. Eventarc routing the event to a Cloud Function
    3. The Cloud Function calling the ingestion pipeline
    """
    
    SUPPORTED_EXTENSIONS = {'.pdf', '.txt'}
    
    def __init__(self):
        super().__init__()
        self._loop: asyncio.AbstractEventLoop | None = None
    
    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create an event loop for async pipeline calls."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
        return self._loop
    
    def on_created(self, event: FileCreatedEvent) -> None:
        """Called when a new file appears in the watch directory."""
        if event.is_directory:
            return
        
        file_path = str(event.src_path)
        ext = os.path.splitext(file_path)[1].lower()
        
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.debug("Ignoring non-CV file: %s", file_path)
            return
        
        if file_path in _processed_files:
            logger.debug("Already processed: %s", file_path)
            return
        
        # Small delay to ensure file write is complete
        time.sleep(0.5)
        
        logger.info(
            "New CV detected: %s — triggering ingestion pipeline",
            file_path,
        )
        
        _processed_files.add(file_path)
        
        # Run the async pipeline in a thread-safe way
        try:
            from app.ingestion.pipeline import process_cv
            
            loop = self._get_loop()
            if loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    self._process(file_path), loop
                )
            else:
                loop.run_until_complete(self._process(file_path))
        except Exception as e:
            logger.error("Failed to trigger pipeline for '%s': %s", file_path, e)
    
    async def _process(self, file_path: str) -> None:
        """Async wrapper for pipeline processing."""
        try:
            from app.ingestion.pipeline import process_cv
            profile = await process_cv(file_path=file_path, filename=os.path.basename(file_path))
            logger.info(
                "Watcher pipeline complete: %s → %s (status=%s)",
                os.path.basename(file_path),
                profile.id,
                profile.status,
            )
        except ValueError as e:
            logger.warning("CV rejected by pipeline: %s — %s", file_path, e)
        except Exception as e:
            logger.error("Pipeline error for '%s': %s", file_path, e)


def start_watcher(watch_dir: str) -> Observer:
    """Start the filesystem observer watching for new CV files.
    
    Runs the observer in a daemon thread so it doesn't block the main app.
    
    Args:
        watch_dir: Directory path to watch for new files.
    
    Returns:
        The watchdog Observer instance.
    """
    global _observer
    
    watch_path = Path(watch_dir).resolve()
    watch_path.mkdir(parents=True, exist_ok=True)
    
    handler = CVFileHandler()
    _observer = Observer()
    _observer.schedule(handler, str(watch_path), recursive=False)
    _observer.daemon = True
    _observer.start()
    
    logger.info(
        "File watcher started — monitoring '%s' for new .pdf/.txt files",
        watch_path,
    )
    
    return _observer


def stop_watcher() -> None:
    """Stop the filesystem observer."""
    global _observer
    if _observer is not None:
        _observer.stop()
        _observer.join(timeout=5)
        _observer = None
        logger.info("File watcher stopped")
