import logging
import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.chunk import Chunk
from app.models.document import Document
from app.models.ingestion_job import IngestionJob
from app.models.source import Source  # noqa: F401
from app.services.chunking_service import chunking_service
from app.services.elasticsearch_service import elasticsearch_service
from app.services.embedding_service import embedding_service
from app.services.knowledge_extraction_service import knowledge_extraction_service
from app.services.neo4j_service import neo4j_service
from app.services.pdf_service import pdf_service
from app.services.web_page_service import web_page_service

logger = logging.getLogger("uvicorn.error")


class IngestionService:
    def process_document(self, document_id: int, db: Session) -> None:
        started_at = time.perf_counter()

        document = db.query(Document).filter(Document.id == document_id).first()
        if not document:
            raise ValueError(f"Document not found: {document_id}")

        ingestion_job = (
            db.query(IngestionJob)
            .filter(IngestionJob.document_id == document.id)
            .order_by(IngestionJob.id.desc())
            .first()
        )

        if not ingestion_job:
            ingestion_job = IngestionJob(
                document_id=document.id,
                status="processing",
                started_at=func.now(),
            )
            db.add(ingestion_job)
            db.flush()

        try:
            document.status = "processing"
            ingestion_job.status = "processing"
            ingestion_job.started_at = func.now()
            db.commit()

            if document.source_type == "url":
                _, raw_text = web_page_service.fetch_text(document.file_path)
                raw_text = raw_text.strip()
            else:
                raw_text = pdf_service.extract_text(document.file_path).strip()

            if not raw_text:
                raise ValueError("Could not extract readable text from the PDF.")

            chunks = chunking_service.split_text(raw_text)

            if not chunks:
                raise ValueError("Text was extracted, but no usable chunks were produced.")

            document.raw_text = raw_text
            document.status = "processed"

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

            neo4j_service.upsert_document(
                document_id=document.id,
                title=document.title,
                source_type=document.source_type,
            )

            knowledge_graph = knowledge_extraction_service.extract(raw_text)

            for entity in knowledge_graph.get("entities", []):
                name = entity.get("name")
                entity_type = entity.get("type", "Other")

                if not name:
                    continue

                neo4j_service.link_document_to_entity(
                    document_id=document.id,
                    entity_name=name,
                    entity_type=entity_type,
                )

            for relationship in knowledge_graph.get("relationships", []):
                from_name = relationship.get("from")
                from_type = relationship.get("from_type", "Other")
                relation = relationship.get("relation", "RELATED_TO")
                to_name = relationship.get("to")
                to_type = relationship.get("to_type", "Other")

                if not from_name or not to_name:
                    continue

                neo4j_service.create_entity_relationship(
                    from_name=from_name,
                    from_type=from_type,
                    relation=relation,
                    to_name=to_name,
                    to_type=to_type,
                )

            ingestion_job.status = "completed"
            ingestion_job.finished_at = func.now()
            ingestion_job.error_message = None

            db.commit()

            logger.info(
                "Document processed: id=%s chunks=%s elapsed=%.2fs",
                document.id,
                len(chunks),
                time.perf_counter() - started_at,
            )

        except Exception as error:
            db.rollback()

            document.status = "failed"
            ingestion_job.status = "failed"
            ingestion_job.error_message = str(error)
            ingestion_job.finished_at = func.now()

            db.commit()

            logger.exception("Document ingestion failed: id=%s", document.id)
            raise


ingestion_service = IngestionService()
