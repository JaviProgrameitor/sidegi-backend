from pydantic import BaseModel
from typing import Optional, List


class UploadResponse(BaseModel):
    message: str
    document_id: str
    document_path: str
    chunks_indexed: int


class SearchRequest(BaseModel):
    query: str
    user_id: str
    folder_id: Optional[str] = None
    carpeta_id: Optional[str] = None
    id_folder: Optional[str] = None
    id_carpeta: Optional[str] = None
    limit: int = 5


class SearchResult(BaseModel):
    document_id: str
    document_name: str
    chunk_text: str
    similarity: float
    document_path: str


class DocumentoCoincidencia(BaseModel):
    documento_id: str
    nombre: str
    similitud: float
    ruta_archivo: str


class SearchIaResponse(BaseModel):
    respuesta_ia: str
    respuesta_html: Optional[str] = None
    documento_principal: Optional[DocumentoCoincidencia] = None
    documentos_secundarios: List[DocumentoCoincidencia] = []
    fragmentos: List[SearchResult] = []