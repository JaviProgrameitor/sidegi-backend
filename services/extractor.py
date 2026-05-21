
import fitz
import docx
import io
from fastapi import HTTPException


def extract_text(file_bytes: bytes, file_type: str) -> str:
    if file_type == "pdf":
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        return "".join(page.get_text() for page in doc)

    elif file_type == "docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    elif file_type in {"txt", "csv"}:
        return file_bytes.decode("utf-8", errors="ignore")

    else:
        raise HTTPException(status_code=415, detail=f"Tipo no soportado: {file_type}")