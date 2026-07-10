from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, Field


class EvaluationDatasetCreate(BaseModel):
    name: str = Field(..., max_length=255)
    description: str | None = None


class EvaluationDatasetResponse(BaseModel):
    id: int
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationCaseCreate(BaseModel):
    dataset_id: int
    question: str
    expected_answer: str
    expected_document_ids: list[int] | None = None
    metadata: dict[str, Any] | None = None


class EvaluationCaseResponse(BaseModel):
    id: int
    dataset_id: int
    question: str
    expected_answer: str
    expected_document_ids: list[int] | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata_", "metadata"),
    )
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class EvaluationRunResponse(BaseModel):
    id: int
    dataset_id: int
    status: str
    model_provider: str | None = None
    model_name: str | None = None
    total_cases: int
    completed_cases: int
    average_answer_similarity: float | None = None
    average_retrieval_score: float | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True
