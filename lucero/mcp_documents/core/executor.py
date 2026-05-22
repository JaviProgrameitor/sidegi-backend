from typing import Dict, Any
from .tools import Tool
from ..tools.read_tool import ReadTool
from ..tools.write_tool import WriteTool
from ..tools.transform_tool import TransformTool
from ..tools.encrypt_tool import EncryptTool
import structlog
import sys

structlog.configure(
    logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
)

log = structlog.get_logger()

class ToolExecutor:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        self.register_tool(ReadTool())
        self.register_tool(WriteTool())
        self.register_tool(TransformTool())
        self.register_tool(EncryptTool())

    def register_tool(self, tool: Tool):
        self._tools[tool.name] = tool
        log.info("tool_registered", tool_name=tool.name)

    async def execute(self, platform: str, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if tool_name not in self._tools:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' not found."
            }
        
        tool = self._tools[tool_name]
        return await tool.execute_with_timing(params)

    def get_schemas(self, platform: str) -> list[Dict[str, Any]]:
        return [tool.to_schema(platform) for tool in self._tools.values()]
