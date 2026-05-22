from fastapi import APIRouter, HTTPException, status

from app.schemas.ask import AskRequest, AskResponse, AskSource
from app.services.llm_service import llm_service
from app.services.retrieval_service import retrieval_service

router = APIRouter(prefix="/ask", tags=["Ask AI"])


@router.post("", response_model=AskResponse)
def ask_question(payload: AskRequest):
    if not payload.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question is required.",
        )

    results = retrieval_service.hybrid_search(
        query=payload.question,
        size=payload.size,
    )

    if not results:
        return AskResponse(
            question=payload.question,
            answer="I could not find relevant information in the indexed documents.",
            sources=[],
        )

    context_parts = []

    for index, result in enumerate(results, start=1):
        context_parts.append(
            f"""
Source {index}
Document: {result.get("document_title")}
Chunk ID: {result.get("chunk_id")}
Text:
{result.get("text")}
""".strip()
        )

    context = "\n\n---\n\n".join(context_parts)

    answer = llm_service.generate_answer(
        question=payload.question,
        context=context,
    )

    sources = [
        AskSource(
            chunk_id=result["chunk_id"],
            document_id=result["document_id"],
            document_title=result["document_title"],
            score=result.get("hybrid_score"),
            text_preview=result["text"][:300],
        )
        for result in results
    ]

    return AskResponse(
        question=payload.question,
        answer=answer,
        sources=sources,
    )