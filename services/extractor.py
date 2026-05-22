import base64
import urllib.request
import json
import os
import io
import time
from pypdf import PdfReader
import docx
from fastapi import HTTPException


def ocr_con_gemini(file_bytes: bytes, mime_type: str) -> str:
    """
    Realiza una consulta a la API de Gemini 1.5 Flash para extraer el texto
    contenido en una imagen o en un PDF escaneado (OCR multimodal).
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        print("Advertencia: GEMINI_API_KEY no configurada. Saltando OCR.")
        return ""
        
    print(f"Iniciando OCR con Gemini API para mimeType: {mime_type}...")
    
    # Codificar bytes en base64
    base64_data = base64.b64encode(file_bytes).decode("utf-8")
    
    # Endpoint de Google AI Studio (se usa gemini-2.5-flash en lugar del obsoleto gemini-1.5-flash)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    # Prompt y datos
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Extrae de forma exacta todo el texto contenido en este archivo/imagen. Conserva el formato original y saltos de línea donde sea posible. No incluyas resúmenes, explicaciones ni preámbulos, solo el texto extraído."
                    },
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64_data
                        }
                    }
                ]
            }
        ]
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    peticion = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    intentos_maximos = 3
    espera_inicial = 2 # segundos
    
    for intento in range(1, intentos_maximos + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=60.0) as respuesta:
                resultado = json.loads(respuesta.read().decode("utf-8"))
                candidatos = resultado.get("candidates", [])
                if candidatos:
                    content = candidatos[0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        texto_extraido = parts[0].get("text", "")
                        print("OCR de Gemini completado con éxito.")
                        return texto_extraido
                print("Gemini no devolvió texto en su respuesta.")
                return ""
        except Exception as e:
            es_transitorio = False
            codigo_error = None
            if hasattr(e, 'code'):
                codigo_error = e.code
                if codigo_error in (429, 503):
                    es_transitorio = True
            
            print(f"Intento {intento} falló al llamar a Gemini API (Código: {codigo_error}): {e}")
            if hasattr(e, 'read'):
                try:
                    print("Detalles del error de Gemini:", e.read().decode('utf-8'))
                except Exception:
                    pass
            
            if es_transitorio and intento < intentos_maximos:
                tiempo_espera = espera_inicial * (2 ** (intento - 1))
                print(f"Error transitorio detectado (503/429). Reintentando en {tiempo_espera} segundos...")
                time.sleep(tiempo_espera)
            else:
                # Si no es transitorio o ya superamos los intentos, salimos del bucle
                break
                
    return ""


def extract_text(file_bytes: bytes, file_type: str) -> str:
    # Mapear extensiones a mimeTypes
    mime_types = {
        "pdf": "application/pdf",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "webp": "image/webp",
        "gif": "image/gif"
    }
    
    tipo_normalizado = file_type.lower().strip(".")
    mime_type = mime_types.get(tipo_normalizado)

    # 1. Si es una imagen, usar OCR directamente
    if tipo_normalizado in {"png", "jpg", "jpeg", "webp", "gif"}:
        texto_ocr = ocr_con_gemini(file_bytes, mime_type or "image/jpeg")
        if texto_ocr and len(texto_ocr.strip()) > 10:
            return texto_ocr
        raise HTTPException(status_code=422, detail="No se pudo extraer suficiente texto de la imagen usando Gemini OCR.")

    # 2. Si es PDF, intentar texto nativo y fallback a OCR si viene en blanco o escaneado
    elif tipo_normalizado == "pdf":
        try:
            # Intento de lectura digital nativa
            lector = PdfReader(io.BytesIO(file_bytes))
            texto = ""
            for pagina in lector.pages:
                texto_pagina = pagina.extract_text()
                if texto_pagina:
                    texto += texto_pagina + "\n"
            
            # Si el texto digital nativo está vacío o es insignificante (< 50 caracteres)
            if len(texto.strip()) < 50:
                print("El PDF parece estar escaneado o sin capa de texto digital. Aplicando OCR de Gemini...")
                texto_ocr = ocr_con_gemini(file_bytes, "application/pdf")
                if texto_ocr and len(texto_ocr.strip()) >= 10:
                    return texto_ocr
                print("Gemini OCR no pudo extraer texto. Devolviendo texto digital original (si tiene).")
            
            return texto
        except Exception as error_pdf:
            print(f"Error al procesar el archivo PDF digital: {error_pdf}. Probando fallback OCR de Gemini...")
            texto_ocr = ocr_con_gemini(file_bytes, "application/pdf")
            if texto_ocr:
                return texto_ocr
            raise HTTPException(status_code=400, detail=f"Error al procesar el archivo PDF: {str(error_pdf)}")

    # 3. Archivos de Word
    elif tipo_normalizado == "docx":
        doc = docx.Document(io.BytesIO(file_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # 4. Texto plano y similares
    elif tipo_normalizado in {"txt", "csv", "md"}:
        return file_bytes.decode("utf-8", errors="ignore")

    else:
        raise HTTPException(status_code=415, detail=f"Tipo de archivo no soportado: {file_type}")
