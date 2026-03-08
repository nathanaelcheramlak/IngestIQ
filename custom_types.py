from typing import Optional
from pydantic import BaseModel


class ChunkAndSrc(BaseModel):
    chunks: list[str]
    source_id: Optional[str] = None


class UpsertResult(BaseModel):
    ingested: int


class SearchResult(BaseModel):
    contexts: list[str]
    sources: list[str]


class QueryResult(BaseModel):
    answer: str
    sources: list[str]
    num_contexts: int
