from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel
import time
import structlog
import sys

structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger()

class Tool(ABC):
    """Base class for all document tools."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    @abstractmethod
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the tool. Must return dict with 'success', 'data', 'error'."""
        pass
    
    async def execute_with_timing(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute with timing & logging."""
        start = time.time()
        try:
            result = await self.execute(params)
            elapsed = (time.time() - start) * 1000
            
            log.info(
                "tool_executed",
                tool_name=self.name,
                elapsed_ms=elapsed,
                success=result.get("success", False),
            )
            
            return {
                **result,
                "elapsed_ms": elapsed
            }
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            log.error(
                "tool_error",
                tool_name=self.name,
                error=str(e),
                elapsed_ms=elapsed,
            )
            raise

    def to_schema(self, platform: str) -> Dict[str, Any]:
        """Convert tool to platform-specific schema."""
        if platform == "mcp":
            return self._mcp_schema()
        elif platform == "groq":
            return self._groq_schema()
        elif platform == "gemini":
            return self._gemini_schema()
        else:
            raise ValueError(f"Unknown platform: {platform}")
    
    def _mcp_schema(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            # Subclasses override with inputSchema
        }
    
    def _groq_schema(self) -> Dict:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                # Subclasses provide parameters
            }
        }
    
    def _gemini_schema(self) -> Dict:
        return {
            "type": "FUNCTION_DECLARATION",
            "name": self.name,
            "description": self.description,
            # Subclasses provide parameters
        }
