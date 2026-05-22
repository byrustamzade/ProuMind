from pydantic import BaseModel


class AskRequest(BaseModel):
    question: str
    size: int = 5


class AskSource(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    score: float | None = None
    text_preview: str


class AskResponse(BaseModel):
    question: str
    answer: str
    sources: list[AskSource]