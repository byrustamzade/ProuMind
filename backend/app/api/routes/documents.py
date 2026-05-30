import hashlib
import logging
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session
from redis import Redis
from rq import Queue

from app.core.config import settings
from app.workers.document_worker import process_document_job
from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.source import Source  # noqa: F401
from app.schemas.document import DocumentResponse
from app.services.elasticsearch_service import elasticsearch_service
from app.services.embedding_service import embedding_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("uvicorn.error")

STORAGE_DIR = Path("storage/documents")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024

redis_connection = Redis.from_url(settings.redis_url)
ingestion_queue = Queue("proumind_ingestion", connection=redis_connection)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sanitize_filename(filename: str) -> str:
    path = Path(filename)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", path.stem).strip("._-")
    if not safe_stem:
        safe_stem = "document"
    return f"{safe_stem}.pdf"


def _build_document_response(document: Document, db: Session) -> DocumentResponse:
    chunks_count = (
                       db.query(func.count(Chunk.id))
                       .filter(Chunk.document_id == document.id)
                       .scalar()
                   ) or 0

    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        status=document.status,
        chunks_count=chunks_count,
        created_at=document.created_at,
    )


def _ingest_pdf(
        file: UploadFile,
        db: Session,
        response: Response | None = None,
) -> DocumentResponse:
    started_at = time.perf_counter()
    filename = (file.filename or "").strip()

    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File name is required.",
        )

    if Path(filename).suffix.lower() != ".pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only PDF files are supported.",
        )

    file_bytes = file.file.read()
    logger.info("Upload received: filename=%s bytes=%s", filename, len(file_bytes))

    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty.",
        )

    if len(file_bytes) > MAX_PDF_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="PDF size exceeds the 20 MB limit.",
        )

    content_hash = hashlib.sha256(file_bytes).hexdigest()

    existing_document = (
        db.query(Document)
        .filter(Document.content_hash == content_hash)
        .first()
    )

    if existing_document:
        logger.info(
            "Duplicate upload detected: filename=%s hash=%s",
            filename,
            content_hash[:12],
        )

        if response is not None:
            response.status_code = status.HTTP_200_OK

        return _build_document_response(existing_document, db)

    safe_filename = _sanitize_filename(filename)
    file_path = STORAGE_DIR / f"{content_hash[:12]}_{safe_filename}"
    file_path.write_bytes(file_bytes)

    document = Document(
        title=filename,
        source_type="pdf",
        file_name=filename,
        file_path=str(file_path),
        content_hash=content_hash,
        raw_text=None,
        status="pending",
    )

    try:
        db.add(document)
        db.flush()

        ingestion_job = IngestionJob(
            document_id=document.id,
            status="pending",
        )

        db.add(ingestion_job)
        db.commit()
        db.refresh(document)

        ingestion_queue.enqueue(
            process_document_job,
            document.id,
            job_timeout=900,
        )

        logger.info(
            "Document queued for ingestion: id=%s filename=%s elapsed=%.2fs",
            document.id,
            filename,
            time.perf_counter() - started_at,
        )

    except Exception as error:
        db.rollback()
        file_path.unlink(missing_ok=True)

        logger.exception("Failed to queue document ingestion: filename=%s", filename)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue document ingestion: {error}",
        )

    return _build_document_response(document, db)


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def upload_pdf(
        response: Response,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    return _ingest_pdf(file=file, db=db, response=response)


@router.post("", response_model=DocumentResponse, include_in_schema=False)
def upload_pdf_alias(
        response: Response,
        file: UploadFile = File(...),
        db: Session = Depends(get_db),
):
    return _ingest_pdf(file=file, db=db, response=response)


@router.get("/search")
def search_documents(
        query: str,
        size: int = 5,
        mode: str = "hybrid",
        document_id: int | None = None,
        source_type: str | None = None,
):
    filters = {
        "document_id": document_id,
        "source_type": source_type,
    }

    if mode == "keyword":
        results = elasticsearch_service.keyword_search(
            query=query,
            size=size,
            filters=filters,
        )
    elif mode == "vector":
        query_embedding = embedding_service.embed_text(query)
        results = elasticsearch_service.vector_search(
            query_embedding=query_embedding,
            size=size,
            filters=filters,
        )
    else:
        results = retrieval_service.hybrid_search(
            query=query,
            size=size,
            filters=filters,
        )

    return {
        "query": query,
        "mode": mode,
        "filters": filters,
        "results": results,
    }


@router.get("/ingestion-jobs")
def list_ingestion_jobs(db: Session = Depends(get_db)):
    jobs = (
        db.query(IngestionJob)
        .order_by(IngestionJob.id.desc())
        .limit(50)
        .all()
    )

    return [
        {
            "id": job.id,
            "document_id": job.document_id,
            "status": job.status,
            "error_message": job.error_message,
            "started_at": job.started_at,
            "finished_at": job.finished_at,
            "created_at": job.created_at,
        }
        for job in jobs
    ]


@router.get("", response_model=list[DocumentResponse])
def list_documents(db: Session = Depends(get_db)):
    rows = (
        db.query(Document, func.count(Chunk.id).label("chunks_count"))
        .outerjoin(Chunk, Chunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.id.desc())
        .all()
    )

    return [
        DocumentResponse(
            id=document.id,
            title=document.title,
            source_type=document.source_type,
            status=document.status,
            chunks_count=chunks_count,
            created_at=document.created_at,
        )
        for document, chunks_count in rows
    ]
