from fastapi import APIRouter, Body, HTTPException
from typing import Dict, Any
from ...schemas import ToolResponse
from ...core.executor import ToolExecutor
import structlog

router = APIRouter()
executor = ToolExecutor()

log = structlog.get_logger()

@router.post("/execute", response_model=ToolResponse)
async def execute_tool(
    platform: str,
    tool_name: str,
    params: Dict[str, Any] = Body(...)
):
    """Execute a tool on the specified platform."""
    
    try:
        result = await executor.execute(
            platform=platform,
            tool_name=tool_name,
            params=params
        )
        
        return ToolResponse(
            success=result.get("success", False),
            data=result.get("data", {}),
            error=result.get("error"),
            elapsed_ms=result.get("elapsed_ms", 0.0)
        )
    
    except Exception as e:
        log.error("execute_error", error=str(e), tool=tool_name)
        raise HTTPException(status_code=500, detail=str(e))
