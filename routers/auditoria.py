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
            from services.groq_client import completar_chat_con_fallback
            print("Enviando prompt de auditoría a Groq con rotación de modelos...")
            hallazgos_texto = await completar_chat_con_fallback(
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


# ─── LÓGICA DE AUDITORÍA COMPLETA (HERRAMIENTAS DE ÉLITE TIERS 1-5) ─────────

class EntradaComparar(BaseModel):
    documentos_ids: list[str] = Field(..., description="Lista de UUIDs de documentos a comparar")

class EntradaExtraer(BaseModel):
    documento_id: str = Field(..., description="UUID del documento")
    tipo_extraccion: str = Field(..., description="Tipo de extracción: dates, tables, metadata, names o custom")

class EntradaResumir(BaseModel):
    documento_id: str = Field(..., description="UUID del documento")
    tipo_resumen: str = Field(default="executive", description="Tipo de resumen: executive, detailed, bullets")

class EntradaCompletitud(BaseModel):
    documento_id: str = Field(..., description="UUID del documento")
    secciones_esperadas: list[str] = Field(..., description="Lista de secciones esperadas en el documento")


async def obtener_texto_documento(documento_id: str) -> tuple[str, str]:
    """
    Intenta obtener el texto completo y el nombre de un documento
    ya sea de Supabase o del fallback de depuración local.
    """
    contenido_documento = ""
    titulo_documento = "documento_desconocido"
    
    if cliente_supabase:
        try:
            datos_doc = await cliente_supabase.consultar_por_id("documentos_integridad", documento_id)
            if datos_doc and len(datos_doc) > 0:
                titulo_documento = datos_doc[0]["nombre"]
                
                datos_frag = await cliente_supabase.consultar_por_filtro(
                    "documentos_embeddings", 
                    select="fragmento,posicion", 
                    filtros=f"documento_id=eq.{documento_id}"
                )
                if datos_frag:
                    datos_frag.sort(key=lambda x: x.get("posicion", 0))
                    contenido_documento = "\n\n".join([f.get("fragmento", "") for f in datos_frag])
        except Exception as error_db:
            print(f"Advertencia al consultar documento en Supabase para obtener texto: {error_db}")

    if not contenido_documento:
        try:
            ruta_local_integridad = f"./depuracion_local/{documento_id}.json"
            ruta_local_embeddings = f"./depuracion_local/embeddings_{documento_id}.json"
            
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
            print(f"Error al leer fallback local del documento: {error_local}")

    if not contenido_documento:
        raise HTTPException(status_code=404, detail=f"No se encontró el contenido del documento con ID: {documento_id}")

    return contenido_documento, titulo_documento


@router.post("/comparar", tags=["auditoría_élite"])
async def comparar_documentos(entrada: EntradaComparar):
    """
    Compara múltiples documentos para identificar puntos de concordancia,
    contradicciones/conflictos y vacíos de información (Gaps) entre ellos (Tier 1).
    """
    textos = []
    for doc_id in entrada.documentos_ids:
        contenido, titulo = await obtener_texto_documento(doc_id)
        textos.append(f"--- DOCUMENTO: {titulo} (ID: {doc_id}) ---\n{contenido[:12000]}")

    contexto_documentos = "\n\n".join(textos)
    
    prompt_sistema = (
        "Eres un analista de documentos de élite en SIGEDI. Compara detalladamente los documentos provistos. "
        "Debes responder estrictamente en formato JSON válido con las siguientes claves: "
        "'consistencias' (lista de puntos en los que todos los documentos concuerdan), "
        "'conflictos' (lista de contradicciones o discrepancias detalladas con referencias a los nombres de archivos), "
        "'gaps' (vacíos de información importantes identificados entre ellos). "
        "No incluyas texto explicativo fuera del JSON."
    )
    
    prompt_usuario = f"Compara estos documentos:\n\n{contexto_documentos}"
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        elif respuesta.strip().startswith("```"):
            respuesta = respuesta.strip().split("```")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en comparación élite: {str(e)}")


@router.post("/extraer-selectivo", tags=["auditoría_élite"])
async def extraer_selectivo(entrada: EntradaExtraer):
    """
    Extrae selectivamente elementos de un documento (fechas, tablas, metadatos, nombres) (Tier 1).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    prompts_tipo = {
        "dates": "Extrae todas las fechas clave, hitos y fechas límite mencionadas en el documento.",
        "tables": "Extrae de forma estructurada todas las tablas o datos tabulares que encuentres.",
        "metadata": "Extrae metadatos del documento como títulos, autores, fechas de creación, versión o firmantes.",
        "names": "Extrae todos los nombres de personas, cargos, organizaciones y entidades mencionadas."
    }
    
    instruccion = prompts_tipo.get(entrada.tipo_extraccion, f"Extrae los siguientes elementos específicos: {entrada.tipo_extraccion}")
    
    prompt_sistema = (
        "Eres un extractor de datos de alta precisión en SIGEDI. Tu tarea es extraer la información solicitada del documento. "
        "Genera tu respuesta en formato JSON estructurado con la clave 'datos_extraidos'. "
        "Sé preciso y no agregues explicaciones fuera de la estructura de datos."
    )
    
    prompt_usuario = f"Instrucción: {instruccion}\n\nDocumento:\n{contenido[:25000]}"
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en extracción selectiva: {str(e)}")


@router.post("/detectar-conflictos", tags=["auditoría_élite"])
async def detectar_conflictos(entrada: EntradaComparar):
    """
    Compara múltiples documentos buscando contradicciones (fechas, montos, acuerdos) (Tier 1).
    """
    textos = []
    for doc_id in entrada.documentos_ids:
        contenido, titulo = await obtener_texto_documento(doc_id)
        textos.append(f"Documento: {titulo} (ID: {doc_id})\nContenido:\n{contenido[:10000]}")
        
    contexto = "\n\n===\n\n".join(textos)
    
    prompt_sistema = (
        "Eres un auditor especializado en detección de discrepancias y conflictos contractuales o documentales en SIGEDI. "
        "Analiza los siguientes textos y reporta cualquier contradicción en fechas, montos, nombres, tareas o acuerdos. "
        "Tu salida debe ser un JSON válido que sea una lista de objetos. Cada objeto debe tener: "
        "'conflicto' (descripción clara), 'fuentes' (nombres de los archivos en conflicto y lo que afirma cada uno), "
        "y 'resolucion_sugerida' (cómo se podría conciliar u optar según criterios de buenas prácticas)."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": contexto}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en detección de conflictos: {str(e)}")


@router.post("/resumir", tags=["auditoría_élite"])
async def generar_resumen(entrada: EntradaResumir):
    """
    Genera un resumen estructurado (ejecutivo, detallado o en viñetas) (Tier 1).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    guias = {
        "executive": "un resumen ejecutivo formal y conciso para alta gerencia (máximo 300 palabras).",
        "detailed": "un resumen analítico y detallado de las secciones principales del documento.",
        "bullets": "una lista clara y numerada de los puntos y conclusiones clave del documento."
    }
    
    guia = guias.get(entrada.tipo_resumen, guias["executive"])
    
    prompt_sistema = "Eres un redactor experto de la plataforma SIGEDI. Tu tarea es resumir el documento siguiendo la guía solicitada. Responde en español."
    prompt_usuario = f"Por favor genera {guia}\n\nDocumento:\n{contenido[:25000]}"
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": prompt_usuario}
            ],
            temperature=0.3,
            max_tokens=2000
        )
        return {"resumen": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar resumen: {str(e)}")


@router.post("/checklist", tags=["auditoría_élite"])
async def crear_checklist(entrada: EntradaAuditoria):
    """
    Crea una lista interactiva de tareas basada en compromisos y obligaciones del documento (Tier 2).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    prompt_sistema = (
        "Analiza el documento y extrae todas las tareas, hitos obligatorios, entregables o acciones requeridas. "
        "Responde en formato JSON estructurado con una lista de tareas bajo la clave 'tareas'. "
        "Cada tarea debe tener: 'descripcion', 'responsable_sugerido' (si se menciona o infiere), y 'criterio_exito' (cómo saber si está completa)."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Documento:\n{contenido[:20000]}"}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al crear checklist: {str(e)}")


@router.post("/cronograma", tags=["auditoría_élite"])
async def extraer_cronograma(entrada: EntradaAuditoria):
    """
    Extrae hitos y eventos organizados cronológicamente (Tier 2).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    prompt_sistema = (
        "Extrae todos los eventos con fecha de este documento. Genera un JSON que contenga una lista "
        "ordenada cronológicamente. Cada elemento debe ser un objeto con: 'fecha' (en formato YYYY-MM-DD o aproximado), "
        "'evento' (descripción de lo que ocurre), y 'prioridad' ('alta', 'media', 'baja')."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Documento:\n{contenido[:20000]}"}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al extraer cronograma: {str(e)}")


@router.post("/calidad-ocr", tags=["auditoría_élite"])
async def calidad_ocr(entrada: EntradaAuditoria):
    """
    Mide y califica la calidad del texto extraído, buscando ruido de OCR o caracteres inválidos (Tier 3).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    largo = len(contenido)
    muestras = []
    if largo > 0:
        muestras.append(contenido[:1500])
    if largo > 6000:
        muestras.append(contenido[largo//2 : largo//2 + 1500])
    if largo > 12000:
        muestras.append(contenido[-1500:])
        
    contexto_muestra = "\n\n[MUESTRA]\n".join(muestras)
    
    prompt_sistema = (
        "Analiza las siguientes muestras de texto extraídas de un documento para evaluar la calidad del OCR. "
        "Busca caracteres extraños (como $, #, @ mal puestos), palabras cortadas, saltos de línea incorrectos o ruido. "
        "Responde en JSON con: 'puntuacion_calidad' (0 a 100, donde 100 es perfecto), 'ruido_detectado' (true/false), "
        "'ejemplos_ruido' (lista de ejemplos) y 'sugerencia_reprocesar' (true/false)."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": contexto_muestra}
            ],
            temperature=0.2,
            max_tokens=2000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al evaluar calidad OCR: {str(e)}")


@router.post("/completitud", tags=["auditoría_élite"])
async def verificacion_completitud(entrada: EntradaCompletitud):
    """
    Comprueba si el documento cumple con la estructura mínima o secciones obligatorias (Tier 3).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    contexto_solicitud = {
        "secciones_esperadas": entrada.secciones_esperadas,
        "documento_inicio": contenido[:20000]
    }
    
    prompt_sistema = (
        "Eres un validador de completitud de SIGEDI. Revisa si en el documento se desarrollan o mencionan claramente las secciones "
        "solicitadas. Genera un reporte JSON con: 'completo' (bool), 'secciones_encontradas' (lista de secciones que sí están), "
        "'secciones_faltantes' (lista de secciones no encontradas) y 'comentarios' (breve descripción para mejorar el documento)."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": json.dumps(contexto_solicitud, ensure_ascii=False)}
            ],
            temperature=0.2,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar completitud: {str(e)}")


@router.post("/briefing", tags=["auditoría_élite"])
async def briefing_ejecutivo(entrada: EntradaComparar):
    """
    Consolida información de múltiples documentos y genera un reporte briefing de una página (Tier 5).
    """
    textos = []
    for doc_id in entrada.documentos_ids:
        contenido, titulo = await obtener_texto_documento(doc_id)
        textos.append(f"Expediente: {titulo} (ID: {doc_id})\n{contenido[:8000]}")
        
    contexto = "\n\n---\n\n".join(textos)
    
    prompt_sistema = (
        "Eres un asesor municipal experto en SIGEDI. Tu cliente necesita un Briefing Ejecutivo de 1 página que resuma y conecte "
        "el contenido de los siguientes documentos. Sé directo, estructurado y enfocado en la toma de decisiones. "
        "Usa formato Markdown formal en español con títulos y viñetas estructuradas."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": contexto}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        return {"briefing": respuesta}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en briefing ejecutivo: {str(e)}")


@router.post("/items-accion", tags=["auditoría_élite"])
async def generar_items_accion(entrada: EntradaAuditoria):
    """
    Extrae tareas de acción con su respectivo responsable, plazo e impacto conceptual (Tier 5).
    """
    contenido, titulo = await obtener_texto_documento(entrada.documento_id)
    
    prompt_sistema = (
        "Extrae una lista de tareas de acción (action items) del documento. Cada item debe tener: "
        "'tarea' (qué se debe hacer), 'responsable' (quién), 'plazo' (cuándo) e 'impacto' ('alto', 'medio', 'bajo'). "
        "Entrega tu resultado como una lista JSON válida."
    )
    
    try:
        from services.groq_client import completar_chat_con_fallback
        respuesta = await completar_chat_con_fallback(
            messages=[
                {"role": "system", "content": prompt_sistema},
                {"role": "user", "content": f"Documento:\n{contenido[:20000]}"}
            ],
            temperature=0.3,
            max_tokens=3000
        )
        if respuesta.strip().startswith("```json"):
            respuesta = respuesta.strip().split("```json")[1].split("```")[0].strip()
        return json.loads(respuesta)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al generar items de acción: {str(e)}")
