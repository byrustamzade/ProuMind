from elasticsearch import Elasticsearch

from app.core.config import settings


class ElasticsearchService:
    INDEX_NAME = "proumind_chunks"

    def __init__(self):
        self.client = Elasticsearch(settings.elasticsearch_url)

    def ensure_index(self):
        if self.client.indices.exists(index=self.INDEX_NAME):
            return

        self.client.indices.create(
            index=self.INDEX_NAME,
            mappings={
                "properties": {
                    "chunk_id": {"type": "integer"},
                    "document_id": {"type": "integer"},
                    "document_title": {"type": "text"},
                    "source_type": {"type": "keyword"},
                    "chunk_index": {"type": "integer"},
                    "text": {"type": "text"},
                    "embedding": {
                        "type": "dense_vector",
                        "dims": 384,
                        "index": True,
                        "similarity": "cosine",
                    },
                    "created_at": {"type": "date"},
                }
            },
        )

    def index_chunk(
        self,
        chunk_id: int,
        document_id: int,
        document_title: str,
        source_type: str,
        chunk_index: int,
        text: str,
        embedding: list[float],
        created_at: str,
    ):
        self.ensure_index()

        self.client.index(
            index=self.INDEX_NAME,
            id=chunk_id,
            document={
                "chunk_id": chunk_id,
                "document_id": document_id,
                "document_title": document_title,
                "source_type": source_type,
                "chunk_index": chunk_index,
                "text": text,
                "embedding": embedding,
                "created_at": created_at,
            },
        )

    def keyword_search(self, query: str, size: int = 5):
        self.ensure_index()

        response = self.client.search(
            index=self.INDEX_NAME,
            query={
                "match": {
                    "text": query,
                }
            },
            size=size,
        )

        return self._format_hits(response)

    def vector_search(self, query_embedding: list[float], size: int = 5):
        self.ensure_index()

        response = self.client.search(
            index=self.INDEX_NAME,
            knn={
                "field": "embedding",
                "query_vector": query_embedding,
                "k": size,
                "num_candidates": max(size * 10, 50),
            },
        )

        return self._format_hits(response)

    def _format_hits(self, response):
        return [
            {
                "score": hit["_score"],
                **hit["_source"],
            }
            for hit in response["hits"]["hits"]
        ]


elasticsearch_service = ElasticsearchService()