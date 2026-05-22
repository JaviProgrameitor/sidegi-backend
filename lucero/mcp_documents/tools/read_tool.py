import aiofiles
from pathlib import Path
from docx import Document
from pypdf import PdfReader
from typing import Dict, Any
from ..core.tools import Tool
import structlog

log = structlog.get_logger()

class ReadTool(Tool):
    def __init__(self):
        super().__init__(
            name="read_document",
            description="Read any document (DOCX, PDF, MD, TXT) and extract content"
        )
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path")
        extract_type = params.get("extract_type", "full_text")
        
        try:
            path = Path(file_path)
            suffix = path.suffix.lower()
            
            if suffix == ".docx":
                content = await self._read_docx(file_path, extract_type)
            elif suffix == ".pdf":
                content = await self._read_pdf(file_path, extract_type)
            elif suffix in [".md", ".txt"]:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
            else:
                return {
                    "success": False,
                    "error": f"Unsupported format: {suffix}"
                }
            
            return {
                "success": True,
                "data": {
                    "format": suffix,
                    "path": str(path),
                    "content": content,
                    "size_bytes": path.stat().st_size,
                    "encoding": "utf-8"
                }
            }
        
        except Exception as e:
            log.error("read_error", error=str(e), file_path=file_path)
            return {"success": False, "error": str(e)}
    
    async def _read_docx(self, file_path: str, extract_type: str) -> str:
        """Extract DOCX content with python-docx."""
        doc = Document(file_path)
        
        if extract_type == "full_text":
            return "\n".join([p.text for p in doc.paragraphs])
        
        elif extract_type == "tables":
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join([cell.text for cell in row.cells])
                    tables_text.append(row_text)
            return "\n".join(tables_text)
        
        elif extract_type == "metadata":
            core_props = doc.core_properties
            return f"Title: {core_props.title}\nAuthor: {core_props.author}\nCreated: {core_props.created}"
        
        else:
            full = "\n".join([p.text for p in doc.paragraphs])
            return full
    
    async def _read_pdf(self, file_path: str, extract_type: str) -> str:
        """Extract PDF content with pypdf."""
        reader = PdfReader(file_path)
        
        if extract_type == "full_text":
            text = []
            for page in reader.pages:
                text.append(page.extract_text())
            return "\n".join(text)
        elif extract_type == "metadata":
            meta = reader.metadata
            return f"Title: {meta.get('/Title', 'N/A')}\nAuthor: {meta.get('/Author', 'N/A')}"
        else:
            return await self._read_pdf(file_path, "full_text")

    def _mcp_schema(self):
        return {
            "name": "read_document",
            "description": "Read and extract content from documents",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string", "description": "Path to file"},
                    "extract_type": {
                        "type": "string",
                        "enum": ["full_text", "metadata", "tables", "images", "all"],
                        "default": "full_text"
                    }
                },
                "required": ["file_path"]
            }
        }
