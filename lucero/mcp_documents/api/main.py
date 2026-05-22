from fastapi import FastAPI
from contextlib import asynccontextmanager
import structlog
from ..config import settings
from .routes import execute

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("server_starting", host=settings.HOST, port=settings.PORT)
    settings.STORAGE_PATH.mkdir(exist_ok=True)
    settings.TEMP_PATH.mkdir(exist_ok=True)
    yield
    log.info("server_stopping")

app = FastAPI(
    title="MCP Documents Pro (LUCERO)",
    description="Universal document processing MCP server",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(execute.router)

@app.get("/")
async def root():
    return {
        "name": "MCP Documents Pro (LUCERO)",
        "version": "1.0.0",
        "status": "running"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host=settings.HOST,
        port=settings.PORT,
        log_config=None
    )
