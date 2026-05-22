from pathlib import Path
from typing import Dict, Any
from ..core.tools import Tool
import subprocess
import asyncio
import structlog

log = structlog.get_logger()

class TransformTool(Tool):
    def __init__(self):
        super().__init__(
            name="transform_document",
            description="Convert between formats (DOCX↔PDF↔Markdown)"
        )
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        source_path = params.get("source_path")
        target_format = params.get("target_format")
        
        try:
            source = Path(source_path)
            target_path = source.with_suffix(f".{target_format}")
            source_fmt = source.suffix.lower()
            
            if source_fmt == ".docx" and target_format == "pdf":
                await self._docx_to_pdf(source_path, str(target_path))
            elif source_fmt == ".docx" and target_format == "md":
                await self._docx_to_markdown(source_path, str(target_path))
            else:
                return {
                    "success": False,
                    "error": f"Conversion {source_fmt} → {target_format} not supported"
                }
            
            return {
                "success": True,
                "data": {
                    "source": str(source),
                    "target": str(target_path),
                    "format": target_format,
                    "size_bytes": target_path.stat().st_size
                }
            }
        
        except Exception as e:
            log.error("transform_error", error=str(e))
            return {"success": False, "error": str(e)}
    
    async def _docx_to_pdf(self, docx_path: str, pdf_path: str):
        cmd = [
            "libreoffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(Path(pdf_path).parent),
            docx_path
        ]
        await asyncio.to_thread(subprocess.run, cmd, check=True)
    
    async def _docx_to_markdown(self, docx_path: str, md_path: str):
        cmd = ["pandoc", docx_path, "-o", md_path]
        await asyncio.to_thread(subprocess.run, cmd, check=True)
