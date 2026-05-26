from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    size: int = 5
    debug: bool = False


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
    graph_context: list[dict]
    retrieved_chunks: list[dict]


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[AskSource]
    debug: AskDebug | None = None
