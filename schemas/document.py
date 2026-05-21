
from pydantic import BaseModel
from typing import Optional


class UploadResponse(BaseModel):
    message: str
    document_id: str
    document_path: str
    chunks_indexed: int


class SearchRequest(BaseModel):
    query: str
    user_id: str
    folder_id: Optional[str] = None
    limit: int = 5


class SearchResult(BaseModel):
    document_id: str
    document_name: str
    chunk_text: str
    similarity: float
    document_path: str