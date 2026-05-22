from fastapi import APIRouter

from app.services.neo4j_service import neo4j_service

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])


@router.get("/documents/{document_id}")
def get_document_graph(document_id: int):
    return {
        "document_id": document_id,
        "graph": neo4j_service.get_document_graph(document_id),
    }