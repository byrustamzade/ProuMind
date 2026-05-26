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

    def keyword_search(self, query: str, size: int = 5, filters: dict | None = None):
        self.ensure_index()

        es_query = {
            "bool": {
                "must": [
                    {
                        "match": {
                            "text": query,
                        }
                    }
                ],
                "filter": self._build_filters(filters),
            }
        }

        response = self.client.search(
            index=self.INDEX_NAME,
            query=es_query,
            size=size,
        )

        return self._format_hits(response)

    def vector_search(
            self,
            query_embedding: list[float],
            size: int = 5,
            filters: dict | None = None,
    ):
        self.ensure_index()

        knn = {
            "field": "embedding",
            "query_vector": query_embedding,
            "k": size,
            "num_candidates": max(size * 10, 50),
        }

        es_filters = self._build_filters(filters)
        if es_filters:
            knn["filter"] = es_filters

        response = self.client.search(
            index=self.INDEX_NAME,
            knn=knn,
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

    def _build_filters(self, filters: dict | None = None) -> list[dict]:
        if not filters:
            return []

        es_filters = []

        document_id = filters.get("document_id")
        if document_id:
            es_filters.append(
                {
                    "term": {
                        "document_id": document_id,
                    }
                }
            )

        source_type = filters.get("source_type")
        if source_type:
            es_filters.append(
                {
                    "term": {
                        "source_type": source_type,
                    }
                }
            )

        return es_filters


elasticsearch_service = ElasticsearchService()
