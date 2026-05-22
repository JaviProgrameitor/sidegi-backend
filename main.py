import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Cargar las variables de entorno del archivo .env al inicio
load_dotenv()

from routers import documents, search, auditoria

app = FastAPI(title="GECEP API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Incluir los enrutadores en la aplicación
app.include_router(documents.enrutador, prefix="/documents", tags=["documents"])
app.include_router(search.router, prefix="/search", tags=["search"])
app.include_router(auditoria.router, prefix="/auditoria", tags=["auditoria"])


@app.get("/")
def health():
    return {"status": "ok", "project": "GECEP"}

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)