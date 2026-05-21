
from fastapi import APIRouter, HTTPException
from services.embedder import get_embedder
from schemas.document import SearchRequest, SearchResult
import chromadb

router = APIRouter()

chroma_client = chromadb.PersistentClient(path="./chroma_db")
collection = chroma_client.get_or_create_collection(
    name="documents",
    metadata={"hnsw:space": "cosine"},
)
model = get_embedder()


@router.post("/", response_model=list[SearchResult])
def search_documents(body: SearchRequest):
    query_embedding = model.encode(body.query).tolist()

    where_filter = {"user_id": {"$eq": body.user_id}}

    # Filtro adicional por folder si se envía
    if body.folder_id:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": body.user_id}},
                {"folder_id": {"$eq": body.folder_id}},
            ]
        }

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=body.limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

    output = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        distance = results["distances"][0][i]
        similarity = round(1 - distance, 4)  # cosine distance → similarity

        output.append(SearchResult(
            document_id=meta["document_id"],
            document_name=meta["document_name"],
            chunk_text=doc,
            similarity=similarity,
            document_path=meta["document_path"],
        ))

    return output