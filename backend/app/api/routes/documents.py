import hashlib
import logging
import re
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.chunk import Chunk
from app.models.document import Document
from app.models.source import Source  # noqa: F401
from app.schemas.document import DocumentResponse
from app.services.chunking_service import chunking_service
from app.services.pdf_service import pdf_service
from app.services.elasticsearch_service import elasticsearch_service
from app.services.embedding_service import embedding_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/documents", tags=["Documents"])
logger = logging.getLogger("uvicorn.error")

STORAGE_DIR = Path("storage/documents")
STORAGE_DIR.mkdir(parents=True, exist_ok=True)
MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024


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


def _ingest_pdf(file: UploadFile, db: Session, response: Response | None = None) -> DocumentResponse:
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
        logger.info("Duplicate upload detected: filename=%s hash=%s", filename, content_hash[:12])
        if response is not None:
            response.status_code = status.HTTP_200_OK
        return _build_document_response(existing_document, db)

    safe_filename = _sanitize_filename(filename)
    file_path = STORAGE_DIR / f"{content_hash[:12]}_{safe_filename}"
    file_path.write_bytes(file_bytes)

    try:
        raw_text = pdf_service.extract_text(str(file_path)).strip()
        logger.info(
            "Text extracted: filename=%s chars=%s elapsed=%.2fs",
            filename,
            len(raw_text),
            time.perf_counter() - started_at,
        )
    except Exception as error:
        file_path.unlink(missing_ok=True)
        logger.exception("Text extraction failed: filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract text from the PDF: {error}",
        )

    if not raw_text:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not extract readable text from the PDF.",
        )

    chunks = chunking_service.split_text(raw_text)
    if not chunks:
        file_path.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text was extracted, but no usable chunks were produced.",
        )

    document = Document(
        title=filename,
        source_type="pdf",
        file_name=filename,
        file_path=str(file_path),
        content_hash=content_hash,
        raw_text=raw_text,
        status="processed",
    )

    try:
        db.add(document)
        db.flush()

        created_chunks = [
            Chunk(
                document_id=document.id,
                chunk_index=index,
                text=chunk_text,
                token_count=None,
                page_number=None,
            )
            for index, chunk_text in enumerate(chunks)
        ]

        db.add_all(created_chunks)
        db.flush()

        for chunk in created_chunks:
            embedding = embedding_service.embed_text(chunk.text)

            elasticsearch_service.index_chunk(
                chunk_id=chunk.id,
                document_id=document.id,
                document_title=document.title,
                source_type=document.source_type,
                chunk_index=chunk.chunk_index,
                text=chunk.text,
                embedding=embedding,
                created_at=chunk.created_at.isoformat(),
            )

        db.commit()
        logger.info(
            "Upload persisted: filename=%s chunks=%s total_elapsed=%.2fs",
            filename,
            len(chunks),
            time.perf_counter() - started_at,
        )
    except Exception as error:
        db.rollback()
        file_path.unlink(missing_ok=True)
        logger.exception("Failed to save document metadata: filename=%s", filename)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save document metadata: {error}",
        )

    db.refresh(document)
    return DocumentResponse(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        status=document.status,
        chunks_count=len(chunks),
        created_at=document.created_at,
    )


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
def search_documents(query: str, size: int = 5, mode: str = "hybrid"):
    if mode == "keyword":
        results = elasticsearch_service.keyword_search(query=query, size=size)
    elif mode == "vector":
        query_embedding = embedding_service.embed_text(query)
        results = elasticsearch_service.vector_search(
            query_embedding=query_embedding,
            size=size,
        )
    else:
        results = retrieval_service.hybrid_search(query=query, size=size)

    return {
        "query": query,
        "mode": mode,
        "results": results,
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
