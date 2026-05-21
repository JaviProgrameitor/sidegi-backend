
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import documents, search

app = FastAPI(title="GECEP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/documents", tags=["documents"])
app.include_router(search.router, prefix="/search", tags=["search"])


@app.get("/")
def health():
    return {"status": "ok", "project": "GECEP"}