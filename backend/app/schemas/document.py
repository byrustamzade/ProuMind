from datetime import datetime

from pydantic import BaseModel


class DocumentResponse(BaseModel):
    id: int
    title: str
    source_type: str
    status: str
    chunks_count: int
    created_at: datetime

    class Config:
        from_attributes = True
