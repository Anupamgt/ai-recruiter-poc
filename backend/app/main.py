"""FastAPI application entrypoint for the AI Recruiter PoC."""
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.session import init_db
from app.retrieval.vector_store import init_collection
from app.ingestion.watcher import start_watcher
from app.api.routes import router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler — runs on startup and shutdown."""
    logger.info("Starting AI Recruiter PoC backend...")
    
    # 1. Initialize SQLite database (create tables)
    await init_db()
    logger.info("Database initialized")
    
    # 2. Initialize Qdrant collection
    try:
        init_collection()
        logger.info("Qdrant collection ready")
    except Exception as e:
        logger.warning(
            "Could not connect to Qdrant (%s). "
            "Vector search will fail until Qdrant is available. "
            "Start it with: docker compose up -d",
            e,
        )
    
    # 3. Start file watcher for CV ingestion
    # In production: GCS bucket → Eventarc → Cloud Functions
    watch_dir = settings.WATCH_DIR
    os.makedirs(watch_dir, exist_ok=True)
    try:
        start_watcher(watch_dir)
        logger.info("File watcher started on '%s'", watch_dir)
    except Exception as e:
        logger.warning("Could not start file watcher: %s", e)
    
    logger.info(
        "AI Recruiter backend ready — API at http://%s:%d",
        settings.BACKEND_HOST,
        settings.BACKEND_PORT,
    )
    
    yield
    
    # Shutdown
    logger.info("Shutting down AI Recruiter backend")


app = FastAPI(
    title="AI Recruiter PoC",
    description="AI-powered ranked candidate shortlisting with explainable results",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS middleware for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router)


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.BACKEND_HOST,
        port=settings.BACKEND_PORT,
        reload=True,
        log_level="info",
    )
