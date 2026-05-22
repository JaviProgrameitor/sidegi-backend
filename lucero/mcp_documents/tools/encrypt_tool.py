from pathlib import Path
from typing import Dict, Any
from ..core.tools import Tool
from ..integrations.encryption import AES256Crypto
import structlog

log = structlog.get_logger()

class EncryptTool(Tool):
    def __init__(self):
        super().__init__(
            name="encrypt_document",
            description="Encrypt documents with AES-256 and PBKDF2"
        )
        self.crypto = AES256Crypto()
    
    async def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        file_path = params.get("file_path")
        password = params.get("password")
        output_path = params.get("output_path")
        
        try:
            encrypted_path = await self.crypto.encrypt_file(
                file_path=file_path,
                password=password,
                output_path=output_path
            )
            
            return {
                "success": True,
                "data": {
                    "encrypted_path": encrypted_path,
                    "algorithm": "AES-256-GCM",
                    "key_derivation": "PBKDF2",
                    "original_size": Path(file_path).stat().st_size,
                    "encrypted_size": Path(encrypted_path).stat().st_size
                }
            }
        
        except Exception as e:
            log.error("encrypt_error", error=str(e))
            return {"success": False, "error": str(e)}
