from pathlib import Path

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes.documents import router as documents_router
from app.api.routes.ask import router as ask_router
from app.api.routes.graph import router as graph_router
from app.core.config import settings
from app.db.session import SessionLocal

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend service for document ingestion and chunking.",
)

app.include_router(documents_router)
app.include_router(ask_router)
app.include_router(graph_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/chat")
def chat_page():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/ui/documents")
def documents_page():
    return FileResponse(STATIC_DIR / "documents.html")


@app.get("/ui/jobs")
def jobs_page():
    return FileResponse(STATIC_DIR / "jobs.html")


@app.get("/health")
def health_check():
    return {
        "status": "ok",
    }

@app.get("/health/ready")
def readiness_check():
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as error:  # pragma: no cover - defensive
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database connectivity check failed: {error}",
        )

    return {
        "status": "ready",
    }
