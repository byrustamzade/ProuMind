from app.db.session import SessionLocal
from app.services.ingestion_service import ingestion_service


def process_document_job(document_id: int):
    db = SessionLocal()

    try:
        ingestion_service.process_document(
            document_id=document_id,
            db=db,
        )
    finally:
        db.close()