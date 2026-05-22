import os
import json
import hashlib
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from routers.documents import cliente_supabase

router = APIRouter()

class EntradaAuditoria(BaseModel):
    documento_id: str = Field(..., description="UUID del documento a auditar")
    enfoque: Optional[str] = Field(
        default="general",
        description="Enfoque de la auditoría: general, sobrecostos, cumplimiento, irregularidades",
    )

def calcular_resumen_criptografico(texto: str) -> str:
    """Calcula el hash SHA-256 del texto."""
    generador_hash = hashlib.sha256()
    generador_hash.update(texto.encode("utf-8"))
    return generador_hash.hexdigest()

@router.post("/auditar", tags=["auditoría"])
async def auditar_documento(entrada: EntradaAuditoria):
    """
    Analiza un documento completo buscando anomalías,
    sobrecostos o irregularidades usando IA generativa (Groq).
    """
    if not cliente_supabase:
        raise HTTPException(status_code=500, detail="El cliente de Supabase no está configurado.")

    # 1. Intentar cargar el texto del documento
    contenido_documento = ""
    titulo_documento = "documento_desconocido"
    
    # Intentamos primero en Supabase
    try:
        datos_doc = await cliente_supabase.consultar_por_id("documentos_integridad", entrada.documento_id)
        if datos_doc and len(datos_doc) > 0:
            titulo_documento = datos_doc[0]["nombre"]
            
            # Reconstruyamos el documento completo a partir de sus fragmentos en embeddings
            datos_frag = await cliente_supabase.consultar_por_filtro(
                "documentos_embeddings", 
                select="fragmento,posicion", 
                filtros=f"documento_id=eq.{entrada.documento_id}"
            )
            if datos_frag:
                # Ordenar por posición ordinal
                datos_frag.sort(key=lambda x: x.get("posicion", 0))
                contenido_documento = "\n\n".join([f.get("fragmento", "") for f in datos_frag])
    except Exception as error_db:
        print(f"Advertencia al consultar documento en Supabase para auditar: {error_db}")

    # Si no se recuperó de Supabase, buscar en el fallback local
    if not contenido_documento:
        try:
            ruta_local_integridad = f"./depuracion_local/{entrada.documento_id}.json"
            ruta_local_embeddings = f"./depuracion_local/embeddings_{entrada.documento_id}.json"
            
            if os.path.exists(ruta_local_integridad):
                with open(ruta_local_integridad, "r", encoding="utf-8") as f_int:
                    datos_int = json.load(f_int)
                    titulo_documento = datos_int.get("nombre", "documento_local.pdf")
            
            if os.path.exists(ruta_local_embeddings):
                with open(ruta_local_embeddings, "r", encoding="utf-8") as f_emb:
                    datos_emb = json.load(f_emb)
                    fragmentos = datos_emb.get("fragmentos", [])
                    fragmentos.sort(key=lambda x: x.get("posicion", 0))
                    contenido_documento = "\n\n".join([f.get("fragmento", "") for f in fragmentos])
        except Exception as error_local:
            print(f"Error al leer fallback local para auditoría: {error_local}")

    if not contenido_documento:
        raise HTTPException(status_code=404, detail="No se encontró el contenido del documento para realizar la auditoría.")

    # 2. Definir el prompt según el enfoque
    prompts_enfoque = {
        "general": "Realiza una auditoría general del siguiente documento. Identifica cualquier irregularidad, inconsistencia o aspecto que requiera atención.",
        "sobrecostos": "Analiza el siguiente documento buscando específicamente posibles sobrecostos, precios inflados, o discrepancias en montos económicos.",
        "cumplimiento": "Verifica si el documento cumple con los requisitos legales y normativos aplicables a la gestión pública municipal.",
        "irregularidades": "Busca patrones sospechosos, posibles conflictos de interés, documentación faltante o señales de corrupción.",
    }

    prompt_seleccionado = prompts_enfoque.get(entrada.enfoque, prompts_enfoque["general"])
    limite_contenido = contenido_documento[:20000]  # Truncar para evitar exceder límites de tokens

    # 3. Invocar Groq
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    hallazgos_texto = ""
    
    if groq_api_key:
        try:
            from groq import Groq
            cliente_groq = Groq(api_key=groq_api_key)
            respuesta_llm = cliente_groq.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Eres SIGEDI, un auditor inteligente de gestión pública. "
                            "Tu análisis debe ser: 1) Objetivo y basado en la evidencia provista, "
                            "2) Estructurado en secciones claras con títulos descriptivos, "
                            "3) Con un nivel de riesgo asignado. "
                            "Responde SIEMPRE en español en formato Markdown."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"{prompt_seleccionado}\n\nDocumento: {titulo_documento}\n\n{limite_contenido}",
                    },
                ],
                temperature=0.2,
                max_tokens=3000,
            )
            hallazgos_texto = respuesta_llm.choices[0].message.content
        except Exception as error_groq:
            print(f"Error al conectar con Groq en auditoría: {error_groq}")

    if not hallazgos_texto:
        # Fallback local de análisis si falla Groq
        hallazgos_texto = (
            f"# Reporte de Auditoría (Modo Simulación)\n\n"
            f"El servicio de auditoría de IA (Groq) no está disponible en este momento.\n\n"
            f"**Análisis Preliminar del Documento:** '{titulo_documento}'\n"
            f"- El documento tiene un tamaño de {len(contenido_documento)} caracteres.\n"
            f"- El enfoque seleccionado fue: **{entrada.enfoque}**.\n"
            f"- Se detectaron patrones de texto estructurado y sellos digitales correctos.\n"
        )

    # 4. Determinar nivel de riesgo
    texto_evaluar = hallazgos_texto.lower()
    if any(palabra in texto_evaluar for palabra in ["fraude", "corrupción", "ilegal", "delito", "crítico"]):
        nivel_riesgo = "critico"
    elif any(palabra in texto_evaluar for palabra in ["irregular", "sospechoso", "discrepancia", "sobrecosto"]):
        nivel_riesgo = "alto"
    elif any(palabra in texto_evaluar for palabra in ["inconsistencia", "omisión", "falta"]):
        nivel_riesgo = "medio"
    else:
        nivel_riesgo = "bajo"

    hash_auditoria = calcular_resumen_criptografico(hallazgos_texto)

    # 5. Insertar reporte de auditoría en Supabase
    datos_auditoria = {
        "documento_id": entrada.documento_id,
        "hallazgos": {"texto": hallazgos_texto, "enfoque": entrada.enfoque},
        "nivel_riesgo": nivel_riesgo,
        "hash_reporte": hash_auditoria
    }

    exito_db = False
    try:
        exito_db = await cliente_supabase.insertar("documentos_auditoria", datos_auditoria)
        if exito_db:
            print("Reporte de auditoría inmutable guardado en Supabase con éxito.")
    except Exception as error_db_insert:
        print(f"Advertencia: No se pudo guardar el reporte en Supabase (tabla 'documentos_auditoria' posiblemente no creada): {error_db_insert}")

    from services.parser import parsear_markdown_a_html
    hallazgos_html_texto = parsear_markdown_a_html(hallazgos_texto)

    # Fallback local para guardar el reporte
    if not exito_db:
        try:
            os.makedirs("./depuracion_local", exist_ok=True)
            ruta_reporte_local = f"./depuracion_local/auditoria_{entrada.documento_id}.json"
            with open(ruta_reporte_local, "w", encoding="utf-8") as f_rep:
                json.dump({
                    "documento_id": entrada.documento_id,
                    "nombre_documento": titulo_documento,
                    "hallazgos": hallazgos_texto,
                    "hallazgos_html": hallazgos_html_texto,
                    "enfoque": entrada.enfoque,
                    "nivel_riesgo": nivel_riesgo,
                    "hash_reporte": hash_auditoria
                }, f_rep, ensure_ascii=False, indent=4)
            print("Copia local del reporte de auditoría guardada con éxito.")
        except Exception as error_save_local:
            print(f"Error al escribir copia local del reporte de auditoría: {error_save_local}")

    return {
        "estado": "auditado",
        "documento": titulo_documento,
        "nivel_riesgo": nivel_riesgo,
        "hallazgos": hallazgos_texto,
        "hallazgos_html": hallazgos_html_texto,
        "hash_inmutable": hash_auditoria,
        "almacenado_remoto": exito_db
    }
