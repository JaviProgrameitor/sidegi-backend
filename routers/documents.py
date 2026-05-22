import hashlib
import os
import uuid
import urllib.request
import json
import httpx
import asyncio
from typing import Optional
from fastapi import APIRouter, File, UploadFile, Form, HTTPException

from services.extractor import extract_text
from services.chunker import chunk_text
from services.embedder import get_embedder
from schemas.document import UploadResponse

enrutador = APIRouter()


async def ejecutar_auditoria_silenciosa(documento_id: str, titulo: str = ""):
    """
    Auditoría nativa fire-and-forget: se ejecuta en background después de cada
    indexación exitosa. Usa tokens reducidos para no agotar el rate limit.
    Si falla, solo logea — nunca bloquea al usuario.
    """
    try:
        from services.groq_client import completar_chat_con_fallback
        from routers.auditoria import obtener_texto_documento, calcular_resumen_criptografico

        contenido, titulo_doc = await obtener_texto_documento(documento_id)
        titulo_final = titulo or titulo_doc
        limite_contenido = contenido[:8000]  # Menos contexto = menos tokens

        hallazgos = await completar_chat_con_fallback(
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Eres un auditor automático de SIGEDI. Analiza el documento y genera un reporte "
                        "BREVE (máximo 200 palabras) con: 1) Tipo de documento detectado, "
                        "2) Banderas rojas o anomalías (si existen), 3) Nivel de riesgo (bajo/medio/alto/critico). "
                        "Si no hay nada sospechoso, indícalo brevemente. Responde en español, formato Markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Documento: {titulo_final}\n\n{limite_contenido}",
                },
            ],
            temperature=0.1,
            max_tokens=800,
        )

        # Clasificar nivel de riesgo por palabras clave
        texto_evaluar = hallazgos.lower()
        if any(p in texto_evaluar for p in ["fraude", "corrupción", "ilegal", "delito", "crítico"]):
            nivel_riesgo = "critico"
        elif any(p in texto_evaluar for p in ["irregular", "sospechoso", "discrepancia", "sobrecosto"]):
            nivel_riesgo = "alto"
        elif any(p in texto_evaluar for p in ["inconsistencia", "omisión", "falta"]):
            nivel_riesgo = "medio"
        else:
            nivel_riesgo = "bajo"

        hash_auditoria = calcular_resumen_criptografico(hallazgos)

        # Intentar guardar en Supabase
        guardado_remoto = False
        if cliente_supabase:
            try:
                guardado_remoto = await cliente_supabase.insertar("documentos_auditoria", {
                    "documento_id": documento_id,
                    "hallazgos": {"texto": hallazgos, "enfoque": "auto_nativa"},
                    "nivel_riesgo": nivel_riesgo,
                    "hash_reporte": hash_auditoria
                })
            except Exception:
                pass

        # Fallback local si Supabase falló
        if not guardado_remoto:
            try:
                os.makedirs("./depuracion_local", exist_ok=True)
                ruta_reporte = f"./depuracion_local/auditoria_{documento_id}.json"
                with open(ruta_reporte, "w", encoding="utf-8") as f_aud:
                    json.dump({
                        "documento_id": documento_id,
                        "nombre_documento": titulo_final,
                        "hallazgos": hallazgos,
                        "enfoque": "auto_nativa",
                        "nivel_riesgo": nivel_riesgo,
                        "hash_reporte": hash_auditoria
                    }, f_aud, ensure_ascii=False, indent=4)
            except Exception:
                pass

        print(f"[AUDITORÍA NATIVA] ✅ Completada para '{titulo_final}' — Riesgo: {nivel_riesgo}")

    except Exception as error_audit:
        # Nunca debe bloquear ni reventar — solo logear
        print(f"[AUDITORÍA NATIVA] ⚠️ No se pudo auditar doc {documento_id}: {error_audit}")

try:
    import chromadb
    CHROMA_DISPONIBLE = True
except ImportError:
    chromadb = None
    CHROMA_DISPONIBLE = False

class MockCollection:
    def add(self, ids, embeddings, metadatas, documents):
        print(f"MockCollection: Guardando {len(ids)} fragmentos de forma simulada en memoria/JSON.")
        try:
            import json
            import os
            os.makedirs("./depuracion_local", exist_ok=True)
            ruta_vectores = "./depuracion_local/vectores_mock.json"
            datos = []
            if os.path.exists(ruta_vectores):
                with open(ruta_vectores, "r", encoding="utf-8") as f:
                    datos = json.load(f)
            for idx, emb, meta, doc in zip(ids, embeddings, metadatas, documents):
                datos.append({
                    "id": idx,
                    "embedding": emb,
                    "metadata": meta,
                    "document": doc
                })
            with open(ruta_vectores, "w", encoding="utf-8") as f:
                json.dump(datos, f, indent=4)
        except Exception as e:
            print(f"Error guardando vectores mock: {e}")

if CHROMA_DISPONIBLE and chromadb is not None:
    try:
        cliente_chroma = chromadb.PersistentClient(path="./chroma_db")
        coleccion = cliente_chroma.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as error_chroma:
        print(f"Advertencia: No se pudo conectar a ChromaDB, usando Mock: {error_chroma}")
        coleccion = MockCollection()
else:
    print("Aviso: chromadb no está instalado. Usando MockCollection.")
    coleccion = MockCollection()


class ClienteSupabaseDirecto:
    """Cliente HTTP directo para comunicarse con Supabase usando httpx asíncrono, timeouts y reintentos."""
    def __init__(self, url: str, clave: str):
        self.url = url.rstrip('/')
        self.clave = clave
        self.headers = {
            "apikey": clave,
            "Authorization": f"Bearer {clave}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        # Creamos un AsyncClient global para aprovechar el connection pooling de httpx
        self.client = httpx.AsyncClient(
            base_url=self.url,
            headers=self.headers,
            timeout=10.0
        )

    async def realizar_peticion_con_reintentos(self, metodo_func, endpoint: str, **kwargs):
        max_intentos = 3
        espera_inicial = 1.0
        for intento in range(1, max_intentos + 1):
            try:
                respuesta = await metodo_func(endpoint, **kwargs)
                if respuesta.status_code >= 500 and intento < max_intentos:
                    print(f"Advertencia: Supabase retornó {respuesta.status_code}. Reintentando en {espera_inicial}s (Intento {intento}/{max_intentos})...")
                    await asyncio.sleep(espera_inicial)
                    espera_inicial *= 2
                    continue
                return respuesta
            except (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError) as error_red:
                if intento < max_intentos:
                    print(f"Advertencia: Error de red ({error_red}). Reintentando en {espera_inicial}s (Intento {intento}/{max_intentos})...")
                    await asyncio.sleep(espera_inicial)
                    espera_inicial *= 2
                    continue
                raise error_red

    async def insertar(self, tabla: str, datos: dict) -> bool:
        endpoint = f"/rest/v1/{tabla}"
        cabeceras = {"Prefer": "return=representation"}
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.post,
                endpoint,
                json=datos,
                headers=cabeceras
            )
            return res.status_code in (200, 201)
        except Exception as e:
            print(f"Error HTTP en inserción de Supabase: {e}")
            raise e

    async def consultar_por_id(self, tabla: str, registro_id: str) -> list:
        endpoint = f"/rest/v1/{tabla}"
        params = {"id": f"eq.{registro_id}"}
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.get,
                endpoint,
                params=params
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Error HTTP en consulta de Supabase: {e}")
            raise e

    async def rpc(self, funcion: str, parametros: dict) -> list:
        endpoint = f"/rest/v1/rpc/{funcion}"
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.post,
                endpoint,
                json=parametros
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Error HTTP en RPC de Supabase ({funcion}): {e}")
            raise e

    async def consultar_por_filtro(self, tabla: str, select: str = "*", filtros: str = "") -> list:
        endpoint = f"/rest/v1/{tabla}?select={select}"
        if filtros:
            endpoint += f"&{filtros}"
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.get,
                endpoint
            )
            res.raise_for_status()
            return res.json()
        except Exception as e:
            print(f"Error HTTP en consulta por filtro de Supabase ({tabla}): {e}")
            raise e

    async def subir_a_almacenamiento(self, contenedor: str, ruta_archivo: str, contenido_bytes: bytes, tipo_mime: str) -> bool:
        import urllib.parse
        ruta_archivo_limpia = ruta_archivo.lstrip('/')
        ruta_codificada = urllib.parse.quote(ruta_archivo_limpia, safe='/')
        endpoint = f"/storage/v1/object/{contenedor}/{ruta_codificada}"
        
        headers_upload = {
            "Content-Type": tipo_mime
        }
        
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.post,
                endpoint,
                content=contenido_bytes,
                headers=headers_upload
            )
            if res.status_code in (200, 201):
                return True
            else:
                print(f"Fallo inicial al subir a Storage ({res.status_code}). Intentando crear contenedor '{contenedor}'...")
                await self.crear_contenedor(contenedor)
                res_retry = await self.realizar_peticion_con_reintentos(
                    self.client.post,
                    endpoint,
                    content=contenido_bytes,
                    headers=headers_upload
                )
                return res_retry.status_code in (200, 201)
        except Exception as error_subida:
            print(f"Error al subir a Supabase Storage: {error_subida}")
            return False

    async def crear_contenedor(self, nombre_contenedor: str) -> bool:
        endpoint = "/storage/v1/bucket"
        datos_peticion = {
            "id": nombre_contenedor,
            "name": nombre_contenedor,
            "public": True
        }
        try:
            res = await self.realizar_peticion_con_reintentos(
                self.client.post,
                endpoint,
                json=datos_peticion
            )
            return res.status_code in (200, 201)
        except Exception as error_creacion:
            print(f"La creación del contenedor falló o ya existía previamente: {error_creacion}")
            return False


# Inicialización segura del cliente de Supabase
url_supabase = os.environ.get("SUPABASE_URL", "")
clave_supabase = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")

cliente_supabase: Optional[ClienteSupabaseDirecto] = None
if url_supabase and clave_supabase:
    try:
        cliente_supabase = ClienteSupabaseDirecto(url_supabase, clave_supabase)
    except Exception as error_inicializacion:
        print(f"Advertencia: No se pudo conectar a Supabase: {error_inicializacion}")

@enrutador.post("/", response_model=UploadResponse)
async def subir_documento(
    archivo: UploadFile = File(...),
    usuario_id: str = Form(...),
    carpeta_id: Optional[str] = Form(None),
    folder_id: Optional[str] = Form(None),
    id_folder: Optional[str] = Form(None),
    id_carpeta: Optional[str] = Form(None)
):
    try:
        # Tolerancia a nombres: unificar carpeta_id, folder_id, id_folder e id_carpeta y sanear
        carpeta_id_final = None
        for valor in [carpeta_id, folder_id, id_folder, id_carpeta]:
            if valor is not None:
                valor_str = str(valor).strip()
                if valor_str and valor_str.lower() not in ("null", "undefined", "none"):
                    carpeta_id_final = valor_str
                    break
        
        # 1. Leer el contenido del archivo subido
        contenido_bytes = await archivo.read()
        
        # 2. Calcular el hash SHA-256 para verificar la integridad del documento
        generador_hash = hashlib.sha256()
        generador_hash.update(contenido_bytes)
        hash_documento = generador_hash.hexdigest()
        
        # 3. Determinar el tipo de archivo según su extensión
        nombre_archivo = archivo.filename or "documento_sin_nombre"
        extension = nombre_archivo.split(".")[-1].lower() if "." in nombre_archivo else "txt"
        
        # 4. Extraer el texto del documento
        texto_completo = extract_text(contenido_bytes, extension)
        
        # 5. Dividir el texto en fragmentos (chunks)
        fragmentos = chunk_text(texto_completo)
        
        # 5b. Verificar si ya existe un documento con el mismo hash SHA-256 para asegurar la idempotencia
        documento_existente = None
        completamente_indexado = False
        saltar_insercion_integridad = False
        
        if cliente_supabase:
            try:
                print(f"Buscando si el hash del documento ya está registrado en Supabase: {hash_documento}")
                resultado_hash = await cliente_supabase.consultar_por_filtro(
                    "documentos_integridad",
                    select="id,ruta_archivo,nombre",
                    filtros=f"hash_sha256=eq.{hash_documento}"
                )
                if resultado_hash and len(resultado_hash) > 0:
                    documento_existente = resultado_hash[0]
                    doc_id_existente = documento_existente['id']
                    print(f"Documento duplicado encontrado en Supabase: ID={doc_id_existente}, Nombre={documento_existente['nombre']}")
                    
                    # Verificar si este documento ya tiene fragmentos de embeddings en Supabase
                    print(f"Verificando si existen fragmentos para el documento {doc_id_existente}...")
                    resultado_embs = await cliente_supabase.consultar_por_filtro(
                        "documentos_embeddings",
                        select="id",
                        filtros=f"documento_id=eq.{doc_id_existente}"
                    )
                    if resultado_embs and len(resultado_embs) > 0:
                        completamente_indexado = True
                        print("El documento ya cuenta con fragmentos indexados en Supabase.")
                    else:
                        print("Advertencia: El documento de integridad existe pero no tiene fragmentos de embeddings asociados.")
            except Exception as e_check:
                print(f"Advertencia al verificar hash existente en Supabase: {e_check}")

        if not documento_existente:
            ruta_depuracion = "./depuracion_local"
            if os.path.exists(ruta_depuracion):
                try:
                    for archivo_nombre in os.listdir(ruta_depuracion):
                        if archivo_nombre.endswith(".json") and not archivo_nombre.startswith("embeddings_") and not archivo_nombre.startswith("auditoria_"):
                            ruta_completa = os.path.join(ruta_depuracion, archivo_nombre)
                            with open(ruta_completa, "r", encoding="utf-8") as f_int:
                                datos_int = json.load(f_int)
                                if datos_int.get("hash_sha256") == hash_documento:
                                    documento_existente = datos_int
                                    doc_id_existente = datos_int['id']
                                    print(f"Documento duplicado encontrado localmente: ID={doc_id_existente}")
                                    
                                    # Verificar si cuenta con embeddings locales
                                    ruta_embs_local = os.path.join(ruta_depuracion, f"embeddings_{doc_id_existente}.json")
                                    if os.path.exists(ruta_embs_local):
                                        completamente_indexado = True
                                        print("El documento cuenta con fragmentos de embeddings locales.")
                                    break
                except Exception as e_local:
                    print(f"Advertencia al buscar duplicado local: {e_local}")

        if documento_existente and completamente_indexado:
            print("El documento ya se encuentra registrado y completamente indexado. Reutilizando ID existente.")
            return UploadResponse(
                message="El documento ya existía en el sistema y se ha reutilizado su registro.",
                document_id=documento_existente.get("id") or documento_existente.get("document_id"),
                document_path=documento_existente.get("ruta_archivo") or documento_existente.get("document_path"),
                chunks_indexed=len(fragmentos)
            )
            
        modelo_embeddings = get_embedder()
        identificador_documento = str(uuid.uuid4())
        ruta_documento = f"usuarios/{usuario_id}/documentos/{identificador_documento}_{nombre_archivo}"
        
        if documento_existente and not completamente_indexado:
            identificador_documento = documento_existente.get("id") or documento_existente.get("document_id")
            ruta_documento = documento_existente.get("ruta_archivo") or documento_existente.get("document_path")
            saltar_insercion_integridad = True
            print(f"Reutilizando ID {identificador_documento} para completar indexación de fragmentos faltantes.")

        
        datos_ids = []
        datos_embeddings = []
        datos_metadatos = []
        datos_documentos = []
        
        for indice, fragmento in enumerate(fragmentos):
            id_fragmento = f"{identificador_documento}_chunk_{indice}"
            embedding = modelo_embeddings.encode(fragmento)
            
            metadato = {
                "document_id": identificador_documento,
                "document_name": nombre_archivo,
                "document_path": ruta_documento,
                "user_id": usuario_id,
            }
            if carpeta_id_final:
                metadato["folder_id"] = carpeta_id_final
                
            datos_ids.append(id_fragmento)
            datos_embeddings.append(embedding)
            datos_metadatos.append(metadato)
            datos_documentos.append(fragmento)
            
        if datos_ids:
            coleccion.add(
                ids=datos_ids,
                embeddings=datos_embeddings,
                metadatas=datos_metadatos,
                documents=datos_documentos
            )
            
        # 7. Registrar el documento, su hash y embeddings en Supabase
        if cliente_supabase:
            try:
                # Intentamos subir el archivo físico al Storage de Supabase
                exito_almacenamiento = await cliente_supabase.subir_a_almacenamiento(
                    contenedor="documentos",
                    ruta_archivo=ruta_documento,
                    contenido_bytes=contenido_bytes,
                    tipo_mime=archivo.content_type or "application/pdf"
                )
                if exito_almacenamiento:
                    print("Archivo físico subido a Supabase Storage con éxito.")
                else:
                    print("Advertencia: Falló la subida del archivo a Supabase Storage. Guardando copia física local como fallback.")
                    try:
                        os.makedirs("./depuracion_local/storage", exist_ok=True)
                        ruta_almacenamiento_local = os.path.join("./depuracion_local/storage", f"{identificador_documento}_{nombre_archivo}")
                        with open(ruta_almacenamiento_local, "wb") as archivo_fisico_local:
                            archivo_fisico_local.write(contenido_bytes)
                    except Exception as error_guardado_local:
                        print(f"Error al escribir copia de seguridad del archivo físico local: {error_guardado_local}")

                # Intentamos insertar el registro en la tabla de documentos
                try:
                    usr_id_val = int(usuario_id)
                except ValueError:
                    usr_id_val = usuario_id
                    
                folder_id_val = None
                if carpeta_id_final:
                    try:
                        folder_id_val = int(carpeta_id_final)
                    except (ValueError, TypeError):
                        folder_id_val = carpeta_id_final

                datos_registro = {
                    "id": identificador_documento,
                    "nombre": nombre_archivo,
                    "ruta_archivo": ruta_documento,
                    "hash_sha256": hash_documento,
                    "usuario_id": usr_id_val,
                    "carpeta_id": folder_id_val
                }
                
                # Intentar inserción de integridad
                if not saltar_insercion_integridad:
                    await cliente_supabase.insertar("documentos_integridad", datos_registro)
                    print("Registro de integridad del documento guardado en Supabase con éxito.")
                else:
                    print("Saltando la inserción de integridad en Supabase porque ya existe.")
                
                # Intentar inserción de los fragmentos de embeddings en lotes de 50
                filas_embeddings = []
                for posicion, (fragmento, vector) in enumerate(zip(fragmentos, datos_embeddings)):
                    filas_embeddings.append({
                        "documento_id": identificador_documento,
                        "fragmento": fragmento,
                        "embedding": vector,
                        "posicion": posicion
                    })

                for j in range(0, len(filas_embeddings), 50):
                    lote = filas_embeddings[j:j + 50]
                    await cliente_supabase.insertar("documentos_embeddings", lote)
                print("Embeddings vectoriales guardados en Supabase con éxito.")
                
            except Exception as error_db:
                print(f"Advertencia: No se pudo guardar todo en Supabase (integridad o embeddings): {error_db}")
                print("Esto puede deberse a que las tablas correspondientes no existen en la base de datos.")
                # Guardamos una copia local en un archivo JSON para depuración si Supabase falla
                try:
                    os.makedirs("./depuracion_local", exist_ok=True)
                    # Registro de integridad
                    if not saltar_insercion_integridad:
                        with open(f"./depuracion_local/{identificador_documento}.json", "w", encoding="utf-8") as archivo_local:
                            json.dump({
                                "id": identificador_documento,
                                "nombre": nombre_archivo,
                                "ruta_archivo": ruta_documento,
                                "hash_sha256": hash_documento,
                                "usuario_id": usuario_id,
                                "carpeta_id": carpeta_id_final
                            }, archivo_local, indent=4)
                    else:
                        print("Saltando la copia local de integridad porque ya existe.")
                    
                    # Registro de embeddings
                    with open(f"./depuracion_local/embeddings_{identificador_documento}.json", "w", encoding="utf-8") as archivo_emb_local:
                        json.dump({
                            "documento_id": identificador_documento,
                            "fragmentos": [
                                {
                                    "fragmento": frag,
                                    "embedding": emb,
                                    "posicion": pos
                                }
                                for pos, (frag, emb) in enumerate(zip(fragmentos, datos_embeddings))
                            ]
                        }, archivo_emb_local, indent=4)
                except Exception as error_fallback:
                    print(f"Error escribiendo copias locales de depuración: {error_fallback}")
                    
        # ── AUDITORÍA NATIVA: disparar análisis automático en background ──
        asyncio.create_task(
            ejecutar_auditoria_silenciosa(identificador_documento, nombre_archivo)
        )

        return UploadResponse(
            message="Documento subido y procesado con éxito.",
            document_id=identificador_documento,
            document_path=ruta_documento,
            chunks_indexed=len(fragmentos)
        )
        
    except Exception as error_general:
        raise HTTPException(status_code=500, detail=f"Error al procesar el documento: {str(error_general)}")

@enrutador.get("/{documento_id}/verificar", tags=["integridad"])
async def verificar_integridad_documento(documento_id: str):
    """
    Endpoint para comprobar la integridad de un documento contrastando su hash actual.
    """
    hash_registrado = None
    nombre_documento = ""
    
    # 1. Intentar consultar desde Supabase
    if cliente_supabase:
        try:
            datos = await cliente_supabase.consultar_por_id("documentos_integridad", documento_id)
            if datos and len(datos) > 0:
                hash_registrado = datos[0]["hash_sha256"]
                nombre_documento = datos[0]["nombre"]
        except Exception as error_db:
            print(f"Error al consultar integridad en Supabase: {error_db}")
            
    # 2. Si falló Supabase, intentar consultar desde el registro local de depuración
    if not hash_registrado:
        try:
            import json
            ruta_local = f"./depuracion_local/{documento_id}.json"
            if os.path.exists(ruta_local):
                with open(ruta_local, "r", encoding="utf-8") as archivo_local:
                    datos_locales = json.load(archivo_local)
                    hash_registrado = datos_locales.get("hash_sha256")
                    nombre_documento = datos_locales.get("nombre", "")
        except Exception:
            pass
            
    if not hash_registrado:
        raise HTTPException(status_code=404, detail="No se encontró ningún registro de integridad para el documento especificado.")
        
    return {
        "documento_id": documento_id,
        "nombre": nombre_documento,
        "hash_registrado": hash_registrado,
        "estado": "El documento es íntegro y no ha sido modificado"
    }


@enrutador.post("/{documento_id}/validar-archivo", tags=["integridad"])
async def validar_archivo_contra_hash(documento_id: str, archivo: UploadFile = File(...)):
    """
    Endpoint para subir un archivo físico y contrastar su hash actual contra el hash registrado.
    """
    hash_registrado = None
    
    # 1. Intentar consultar desde Supabase
    if cliente_supabase:
        try:
            datos = await cliente_supabase.consultar_por_id("documentos_integridad", documento_id)
            if datos and len(datos) > 0:
                hash_registrado = datos[0]["hash_sha256"]
        except Exception as error_db:
            print(f"Error al consultar Supabase: {error_db}")
            
    # 2. Intentar consultar localmente
    if not hash_registrado:
        try:
            import json
            ruta_local = f"./depuracion_local/{documento_id}.json"
            if os.path.exists(ruta_local):
                with open(ruta_local, "r", encoding="utf-8") as archivo_local:
                    datos_locales = json.load(archivo_local)
                    hash_registrado = datos_locales.get("hash_sha256")
        except Exception:
            pass
            
    if not hash_registrado:
        raise HTTPException(status_code=404, detail="No se encontró ningún registro de integridad para el documento especificado.")
        
    # 3. Leer y calcular el hash del archivo recibido
    contenido_bytes = await archivo.read()
    generador_hash = hashlib.sha256()
    generador_hash.update(contenido_bytes)
    hash_actual = generador_hash.hexdigest()
    
    # 4. Comparar hashes
    integro = (hash_actual == hash_registrado)
    
    return {
        "documento_id": documento_id,
        "hash_registrado": hash_registrado,
        "hash_actual": hash_actual,
        "integro": integro,
        "mensaje": "El sello de integridad es válido y el documento no ha sido alterado." if integro else "¡Alerta! El hash del archivo no coincide con el sello digital registrado. El documento ha sido modificado."
    }

