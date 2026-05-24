from fastapi import APIRouter, HTTPException, status

from app.schemas.ask import AskDebug, AskRequest, AskResponse, AskSource
from app.services.knowledge_extraction_service import knowledge_extraction_service
from app.services.llm_service import llm_service
from app.services.neo4j_service import neo4j_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/ask", tags=["Ask AI"])


@router.post("", response_model=AskResponse)
def ask_question(payload: AskRequest):
    question = payload.question.strip()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required.",
        )

    retrieved_chunks = retrieval_service.hybrid_search(
        query=question,
        size=payload.size,
    )

    query_entities = knowledge_extraction_service.extract_query_entities(question)

    graph_context = neo4j_service.search_related_entities(
        entity_names=query_entities,
        limit=20,
    )

    if not retrieved_chunks and not graph_context:
        return AskResponse(
            question=question,
            answer="I could not find relevant information in the indexed documents or knowledge graph.",
            sources=[],
        )

    context = _build_context(
        retrieved_chunks=retrieved_chunks,
        graph_context=graph_context,
    )

    answer = llm_service.generate_answer(
        question=question,
        context=context,
    )

    sources = [
        AskSource(
            chunk_id=result["chunk_id"],
            document_id=result["document_id"],
            document_title=result["document_title"],
            score=result.get("hybrid_score"),
            keyword_score=result.get("keyword_score"),
            vector_score=result.get("vector_score"),
            text_preview=result["text"][:300],
        )
        for result in retrieved_chunks
    ]

    debug = None

    if payload.debug:
        debug = AskDebug(
            query_entities=query_entities,
            graph_context=graph_context,
            retrieved_chunks=[
                {
                    "chunk_id": result.get("chunk_id"),
                    "document_id": result.get("document_id"),
                    "document_title": result.get("document_title"),
                    "hybrid_score": result.get("hybrid_score"),
                    "keyword_score": result.get("keyword_score"),
                    "vector_score": result.get("vector_score"),
                    "chunk_index": result.get("chunk_index"),
                }
                for result in retrieved_chunks
            ],
        )

    return AskResponse(
        question=question,
        answer=answer,
        sources=sources,
        debug=debug,
    )


def _build_context(retrieved_chunks: list[dict], graph_context: list[dict]) -> str:
    parts = []

    if retrieved_chunks:
        chunk_parts = []

        for index, result in enumerate(retrieved_chunks, start=1):
            chunk_parts.append(
                f"""
Source {index}
Document: {result.get("document_title")}
Chunk ID: {result.get("chunk_id")}
Text:
{result.get("text")}
""".strip()
            )

        parts.append(
            "DOCUMENT CONTEXT:\n\n" + "\n\n---\n\n".join(chunk_parts)
        )

    if graph_context:
        graph_lines = []

        for item in graph_context:
            entity = item.get("entity") or {}
            related = item.get("related") or {}
            relationship = item.get("relationship")

            if not entity:
                continue

            if related and relationship:
                graph_lines.append(
                    f"{entity.get('type')}:{entity.get('name')} "
                    f"-[{relationship}]- "
                    f"{related.get('type')}:{related.get('name')}"
                )
            else:
                graph_lines.append(
                    f"{entity.get('type')}:{entity.get('name')}"
                )

        if graph_lines:
            parts.append(
                "KNOWLEDGE GRAPH CONTEXT:\n\n" + "\n".join(graph_lines)
            )

    return "\n\n====================\n\n".join(parts)