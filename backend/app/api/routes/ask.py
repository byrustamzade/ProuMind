from fastapi import APIRouter

from app.services.retrieval_service import retrieval_service
from app.services.llm_service import llm_service

router = APIRouter(prefix="/ask", tags=["Ask AI"])


@router.post("")
def ask_question(question: str, size: int = 5):
    results = retrieval_service.hybrid_search(query=question, size=size)

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
        question=question,
        context=context,
    )

    return {
        "question": question,
        "answer": answer,
        "sources": [
            {
                "chunk_id": result.get("chunk_id"),
                "document_id": result.get("document_id"),
                "document_title": result.get("document_title"),
                "score": result.get("hybrid_score"),
            }
            for result in results
        ],
    }
