from sentence_transformers import CrossEncoder


class RerankingService:
    def __init__(self):
        self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(self, query: str, results: list[dict], size: int = 5) -> list[dict]:
        if not results:
            return []

        pairs = [
            [query, result["text"]]
            for result in results
        ]

        scores = self.model.predict(pairs)

        reranked_results = []

        for result, score in zip(results, scores):
            result["rerank_score"] = float(score)
            reranked_results.append(result)

        reranked_results.sort(
            key=lambda item: item["rerank_score"],
            reverse=True,
        )

        return reranked_results[:size]


reranking_service = RerankingService()