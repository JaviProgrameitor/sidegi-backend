import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

# Cargar las variables de entorno del archivo .env al inicio
load_dotenv()

from routers import documents, search, auditoria

app = FastAPI(title="GECEP API")

# Lista de orígenes permitidos — agregar aquí cualquier URL nueva del frontend
ORIGENES_PERMITIDOS = [
    # Dev Tunnels de VS Code (cualquier subdominio de devtunnels.ms)
    "https://pk17qp0c-8000.usw3.devtunnels.ms",
    # Desarrollo local
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:5173",
    "http://localhost:8080",
    "http://127.0.0.1",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ORIGENES_PERMITIDOS,
    allow_origin_regex=r"https://.*\.devtunnels\.ms",  # Cubre CUALQUIER Dev Tunnel dinámico
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cachea el preflight 10 minutos para no repetirlo en cada request
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