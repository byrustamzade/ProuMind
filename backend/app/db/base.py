from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


from app.models.source import Source  # noqa
from app.models.document import Document  # noqa
from app.models.chunk import Chunk  # noqa
from app.models.ingestion_job import IngestionJob  # noqa