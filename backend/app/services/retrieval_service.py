from app.services.elasticsearch_service import elasticsearch_service
from app.services.embedding_service import embedding_service
from app.services.reranking_service import reranking_service


class RetrievalService:
    def hybrid_search(
            self,
            query: str,
            size: int = 5,
            keyword_weight: float = 0.4,
            vector_weight: float = 0.6,
            rerank: bool = True,
            filters: dict | None = None,
    ):
        query_embedding = embedding_service.embed_text(query)

        candidate_size = max(size * 10, 50)

        keyword_results = elasticsearch_service.keyword_search(
            query=query,
            size=candidate_size,
            filters=filters,
        )

        vector_results = elasticsearch_service.vector_search(
            query_embedding=query_embedding,
            size=candidate_size,
            filters=filters,
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

        if rerank:
            return reranking_service.rerank(
                query=query,
                results=results,
                size=size,
            )

        return results[:size]

    def graph_expanded_search(
            self,
            query: str,
            expansion_terms: list[str],
            size: int = 5,
            filters: dict | None = None,
    ):
        expanded_query = query

        if expansion_terms:
            expanded_query = query + " " + " ".join(expansion_terms)

        return self.hybrid_search(
            query=expanded_query,
            size=size,
            filters=filters,
            rerank=True,
        )


retrieval_service = RetrievalService()
