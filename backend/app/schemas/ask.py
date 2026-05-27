from pydantic import BaseModel


class AskFilters(BaseModel):
    document_id: int | None = None
    source_type: str | None = None


class AskRequest(BaseModel):
    question: str
    size: int = 5
    debug: bool = False
    filters: AskFilters | None = None


class AskSource(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    score: float | None = None
    keyword_score: float | None = None
    vector_score: float | None = None
    text_preview: str
    rerank_score: float | None = None


class AskDebug(BaseModel):
    query_entities: list[str]
    expansion_terms: list[str]
    graph_context: dict
    retrieved_chunks: list[dict]


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[AskSource]
    debug: AskDebug | None = None
