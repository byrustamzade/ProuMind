from app.services.elasticsearch_service import elasticsearch_service
from app.services.embedding_service import embedding_service


class RetrievalService:
    def hybrid_search(
        self,
        query: str,
        size: int = 5,
        keyword_weight: float = 0.4,
        vector_weight: float = 0.6,
    ):
        query_embedding = embedding_service.embed_text(query)

        keyword_results = elasticsearch_service.keyword_search(
            query=query,
            size=size * 2,
        )

        vector_results = elasticsearch_service.vector_search(
            query_embedding=query_embedding,
            size=size * 2,
        )

        merged = {}

        for result in keyword_results:
            chunk_id = result["chunk_id"]
            merged.setdefault(chunk_id, result | {"hybrid_score": 0})
            merged[chunk_id]["hybrid_score"] += result["score"] * keyword_weight
            merged[chunk_id]["keyword_score"] = result["score"]

        for result in vector_results:
            chunk_id = result["chunk_id"]
            merged.setdefault(chunk_id, result | {"hybrid_score": 0})
            merged[chunk_id]["hybrid_score"] += result["score"] * vector_weight
            merged[chunk_id]["vector_score"] = result["score"]

        results = sorted(
            merged.values(),
            key=lambda item: item["hybrid_score"],
            reverse=True,
        )

        return results[:size]


retrieval_service = RetrievalService()