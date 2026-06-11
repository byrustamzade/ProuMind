import hashlib
import logging
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, HttpUrl
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
from app.services.github_service import github_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("uvicorn.error")

STORAGE_DIR = Path("storage/documents")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024

redis_connection = Redis.from_url(settings.redis_url)
ingestion_queue = Queue("proumind_ingestion", connection=redis_connection)


class UrlIngestionRequest(BaseModel):
    url: HttpUrl


class GitHubIssuesIngestionRequest(BaseModel):
    repo_url: HttpUrl
    state: str = "open"
    limit: int = 20


class GitHubPullsIngestionRequest(BaseModel):
    repo_url: HttpUrl
    state: str = "open"
    limit: int = 20


class WebhookIngestionRequest(BaseModel):
    source_type: str
    url: HttpUrl
    state: str | None = "open"
    limit: int | None = 20


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


@router.post("/url", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_url(
        payload: UrlIngestionRequest,
        db: Session = Depends(get_db),
):
    url = str(payload.url)

    content_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()

    existing_document = (
        db.query(Document)
        .filter(Document.content_hash == content_hash)
        .first()
    )

    if existing_document:
        return _build_document_response(existing_document, db)

    document = Document(
        title=url,
        source_type="url",
        file_name=None,
        file_path=url,
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
            "URL queued for ingestion: id=%s url=%s",
            document.id,
            url,
        )

    except Exception as error:
        db.rollback()

        logger.exception("Failed to queue URL ingestion: url=%s", url)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue URL ingestion: {error}",
        )

    return _build_document_response(document, db)


@router.post("/github/issues", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_github_issues(
        payload: GitHubIssuesIngestionRequest,
        db: Session = Depends(get_db),
):
    repo_url = str(payload.repo_url)
    state = payload.state.lower().strip()

    if state not in github_service.valid_issue_states:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State must be one of: open, closed, all.",
        )

    limit = max(1, min(payload.limit, 100))
    issues_source = github_service.build_issues_source(repo_url, state, limit)

    content_hash = hashlib.sha256(
        f"github_issues:{repo_url}:{state}:{limit}".encode("utf-8")
    ).hexdigest()

    existing_document = (
        db.query(Document)
        .filter(Document.content_hash == content_hash)
        .first()
    )

    if existing_document:
        if existing_document.status == "failed":
            try:
                existing_document.file_path = issues_source
                existing_document.status = "pending"

                ingestion_job = IngestionJob(
                    document_id=existing_document.id,
                    status="pending",
                )

                db.add(ingestion_job)
                db.commit()
                db.refresh(existing_document)

                ingestion_queue.enqueue(
                    process_document_job,
                    existing_document.id,
                    job_timeout=900,
                )
            except Exception as error:
                db.rollback()

                logger.exception("Failed to requeue GitHub issues ingestion: repo=%s", repo_url)

                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to requeue GitHub issues ingestion: {error}",
                )

        return _build_document_response(existing_document, db)

    document = Document(
        title=f"GitHub Issues: {repo_url}",
        source_type="github_issues",
        file_name=None,
        file_path=issues_source,
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
            "GitHub issues queued for ingestion: id=%s repo=%s",
            document.id,
            repo_url,
        )

    except Exception as error:
        db.rollback()

        logger.exception("Failed to queue GitHub issues ingestion: repo=%s", repo_url)

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue GitHub issues ingestion: {error}",
        )

    return _build_document_response(document, db)


@router.post("/github/pulls", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_github_pulls(
        payload: GitHubPullsIngestionRequest,
        db: Session = Depends(get_db),
):
    repo_url = str(payload.repo_url)
    state = payload.state.lower().strip()

    if state not in {"open", "closed", "all"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="State must be one of: open, closed, all.",
        )

    limit = max(1, min(payload.limit, 100))

    content_hash = hashlib.sha256(
        f"github_pulls:{repo_url}:{state}:{limit}".encode("utf-8")
    ).hexdigest()

    existing_document = (
        db.query(Document)
        .filter(Document.content_hash == content_hash)
        .first()
    )

    if existing_document:
        return _build_document_response(existing_document, db)

    document = Document(
        title=f"GitHub Pull Requests: {repo_url}",
        source_type="github_pulls",
        file_name=None,
        file_path=repo_url,
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
            "GitHub pull requests queued for ingestion: id=%s repo=%s",
            document.id,
            repo_url,
        )

    except Exception as error:
        db.rollback()

        logger.exception(
            "Failed to queue GitHub pull requests ingestion: repo=%s",
            repo_url,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue GitHub pull requests ingestion: {error}",
        )

    return _build_document_response(document, db)


@router.post("/webhook", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def ingest_from_webhook(
        payload: WebhookIngestionRequest,
        db: Session = Depends(get_db),
):
    source_type = payload.source_type.lower().strip()
    url = str(payload.url)

    allowed_source_types = {
        "url",
        "github_issues",
        "github_pulls",
    }

    if source_type not in allowed_source_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source_type must be one of: url, github_issues, github_pulls.",
        )

    state = (payload.state or "open").lower().strip()
    limit = max(1, min(payload.limit or 20, 100))

    if source_type in {"github_issues", "github_pulls"} and state not in {"open", "closed", "all"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="state must be one of: open, closed, all.",
        )

    content_hash = hashlib.sha256(
        f"webhook:{source_type}:{url}:{state}:{limit}".encode("utf-8")
    ).hexdigest()

    existing_document = (
        db.query(Document)
        .filter(Document.content_hash == content_hash)
        .first()
    )

    if existing_document:
        return _build_document_response(existing_document, db)

    document = Document(
        title=f"Webhook Source: {source_type} - {url}",
        source_type=source_type,
        file_name=None,
        file_path=url,
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
            "Webhook ingestion queued: id=%s source_type=%s url=%s",
            document.id,
            source_type,
            url,
        )

    except Exception as error:
        db.rollback()

        logger.exception(
            "Failed to queue webhook ingestion: source_type=%s url=%s",
            source_type,
            url,
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to queue webhook ingestion: {error}",
        )

    return _build_document_response(document, db)


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


@router.post("/ingestion-jobs/{job_id}/retry")
def retry_ingestion_job(
        job_id: int,
        db: Session = Depends(get_db),
):
    ingestion_job = (
        db.query(IngestionJob)
        .filter(IngestionJob.id == job_id)
        .first()
    )

    if not ingestion_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found.",
        )

    if ingestion_job.status != "failed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only failed ingestion jobs can be retried.",
        )

    document = (
        db.query(Document)
        .filter(Document.id == ingestion_job.document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Related document not found.",
        )

    document.status = "pending"
    ingestion_job.status = "pending"
    ingestion_job.error_message = None
    ingestion_job.started_at = None
    ingestion_job.finished_at = None

    db.commit()

    ingestion_queue.enqueue(
        process_document_job,
        document.id,
        job_timeout=900,
    )

    return {
        "message": "Ingestion job queued for retry.",
        "job_id": ingestion_job.id,
        "document_id": document.id,
        "status": ingestion_job.status,
    }


@router.get("/ingestion-jobs/{job_id}")
def get_ingestion_job(
        job_id: int,
        db: Session = Depends(get_db),
):
    ingestion_job = (
        db.query(IngestionJob)
        .filter(IngestionJob.id == job_id)
        .first()
    )

    if not ingestion_job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Ingestion job not found.",
        )

    document = (
        db.query(Document)
        .filter(Document.id == ingestion_job.document_id)
        .first()
    )

    return {
        "id": ingestion_job.id,
        "document_id": ingestion_job.document_id,
        "document_title": document.title if document else None,
        "document_status": document.status if document else None,
        "status": ingestion_job.status,
        "error_message": ingestion_job.error_message,
        "started_at": ingestion_job.started_at,
        "finished_at": ingestion_job.finished_at,
        "created_at": ingestion_job.created_at,
    }


@router.post("/{document_id}/reprocess")
def reprocess_document(
        document_id: int,
        db: Session = Depends(get_db),
):
    document = (
        db.query(Document)
        .filter(Document.id == document_id)
        .first()
    )

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

    document.status = "pending"

    ingestion_job = IngestionJob(
        document_id=document.id,
        status="pending",
    )

    db.add(ingestion_job)
    db.commit()

    ingestion_queue.enqueue(
        process_document_job,
        document.id,
        job_timeout=900,
    )

    return {
        "message": "Document queued for reprocessing.",
        "document_id": document.id,
        "job_id": ingestion_job.id,
        "status": ingestion_job.status,
    }


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
