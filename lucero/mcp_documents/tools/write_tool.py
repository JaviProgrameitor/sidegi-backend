from docx import Document
from docx.shared import Pt
from pathlib import Path
from typing import Dict, Any
from ..core.tools import Tool
from ..integrations.encryption import AES256Crypto
import aiofiles
import structlog

log = structlog.get_logger()

class WriteTool(Tool):
    def __init__(self):
        super().__init__(
            name="write_document",
            description="Write/modify documents with full formatting support"
        )
        self.crypto = AES256Crypto()
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path")
        content = params.get("content")
        format = params.get("format", "docx")
        append = params.get("append", False)
        encrypt = params.get("encrypt", False)
        password = params.get("password", "")
        
        try:
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            
            if format == "docx":
                await self._write_docx(file_path, content, append)
            elif format == "md" or format == "txt":
                mode = "a" if append else "w"
                async with aiofiles.open(file_path, mode, encoding="utf-8") as f:
                    await f.write(content)
            else:
                return {"success": False, "error": f"Unsupported format: {format}"}
            
            if encrypt and password:
                encrypted_path = await self.crypto.encrypt_file(file_path, password)
                return {
                    "success": True,
                    "data": {
                        "path": encrypted_path,
                        "encrypted": True,
                        "original_size": path.stat().st_size
                    }
                }
            
            return {
                "success": True,
                "data": {
                    "path": str(path),
                    "format": format,
                    "size_bytes": path.stat().st_size
                }
            }
        
        except Exception as e:
            log.error("write_error", error=str(e), file_path=file_path)
            return {"success": False, "error": str(e)}
    
    async def _write_docx(self, file_path: str, content: str, append: bool):
        if append and Path(file_path).exists():
            doc = Document(file_path)
        else:
            doc = Document()
            doc.styles['Normal'].font.name = 'Calibri'
            doc.styles['Normal'].font.size = Pt(11)
        
        for paragraph_text in content.split("\n\n"):
            if paragraph_text.startswith("# "):
                doc.add_heading(paragraph_text[2:], level=1)
            elif paragraph_text.startswith("## "):
                doc.add_heading(paragraph_text[3:], level=2)
            elif paragraph_text.startswith("### "):
                doc.add_heading(paragraph_text[4:], level=3)
            else:
                p = doc.add_paragraph(paragraph_text)
                p.style = 'Normal'
        
        doc.save(file_path)
