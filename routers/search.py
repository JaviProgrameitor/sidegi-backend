import os
import json
from fastapi import APIRouter, HTTPException
from services.embedder import get_embedder
from schemas.document import SearchRequest, SearchResult, SearchIaResponse, DocumentoCoincidencia
from routers.documents import cliente_supabase

try:
    import chromadb
    CHROMA_DISPONIBLE = True
except ImportError:
    chromadb = None
    CHROMA_DISPONIBLE = False

router = APIRouter()

class MockCollectionQuery:
    def query(self, query_embeddings, n_results, where, include=None):
        print(f"MockCollectionQuery: Realizando consulta vectorial de prueba en JSON local.")
        ruta_vectores = "./depuracion_local/vectores_mock.json"
        
        if not os.path.exists(ruta_vectores):
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            
        try:
            with open(ruta_vectores, "r", encoding="utf-8") as f:
                datos = json.load(f)
        except Exception:
            return {"documents": [[]], "metadatas": [[]], "distances": [[]]}
            
        user_id = None
        folder_id = None
        if where:
            if "user_id" in where:
                user_val = where["user_id"]
                if isinstance(user_val, dict) and "$eq" in user_val:
                    user_id = user_val["$eq"]
                else:
                    user_id = user_val
            elif "$and" in where:
                for condicion in where["$and"]:
                    if "user_id" in condicion:
                        user_val = condicion["user_id"]
                        user_id = user_val["$eq"] if isinstance(user_val, dict) else user_val
                    if "folder_id" in condicion:
                        folder_val = condicion["folder_id"]
                        folder_id = folder_val["$eq"] if isinstance(folder_val, dict) else folder_val

        resultados_candidatos = []
        q_emb = query_embeddings[0]
        
        for item in datos:
            meta = item.get("metadata", {})
            if user_id and str(meta.get("user_id")) != str(user_id):
                continue
            if folder_id and str(meta.get("folder_id")) != str(folder_id):
                continue
                
            # Soft delete: omitir si está marcado como eliminado lógicamente (esta_eliminado = 1)
            if meta.get("esta_eliminado") == 1:
                continue
                
            doc_id = meta.get("document_id")
            if doc_id:
                ruta_int = f"./depuracion_local/{doc_id}.json"
                if os.path.exists(ruta_int):
                    try:
                        with open(ruta_int, "r", encoding="utf-8") as f_int:
                            datos_int = json.load(f_int)
                        if datos_int.get("esta_eliminado") == 1:
                            continue
                    except Exception:
                        pass
                
            item_emb = item.get("embedding", [])
            if len(item_emb) == len(q_emb) and len(q_emb) > 0:
                similitud = sum(x * y for x, y in zip(item_emb, q_emb))
            else:
                similitud = 0.0
                
            distancia = 1.0 - similitud
            resultados_candidatos.append((distancia, item))
            
        resultados_candidatos.sort(key=lambda x: x[0])
        resultados_candidatos = resultados_candidatos[:n_results]
        
        ret_docs = []
        ret_metas = []
        ret_dists = []
        for dist, item in resultados_candidatos:
            ret_docs.append(item.get("document", ""))
            ret_metas.append(item.get("metadata", {}))
            ret_dists.append(dist)
            
        return {
            "documents": [ret_docs],
            "metadatas": [ret_metas],
            "distances": [ret_dists]
        }

if CHROMA_DISPONIBLE and chromadb is not None:
    try:
        chroma_client = chromadb.PersistentClient(path="./chroma_db")
        collection = chroma_client.get_or_create_collection(
            name="documents",
            metadata={"hnsw:space": "cosine"},
        )
    except Exception as e:
        print(f"Advertencia: No se pudo conectar a ChromaDB en routers/search.py: {e}")
        collection = MockCollectionQuery()
else:
    collection = MockCollectionQuery()

model = get_embedder()


@router.post("/", response_model=list[SearchResult])
def search_documents(body: SearchRequest):
    query_embedding = model.encode(body.query).tolist()

    # Unificar y sanear el ID de la carpeta
    folder_id_final = None
    for valor in [body.folder_id, body.carpeta_id, body.id_folder, body.id_carpeta]:
        if valor is not None:
            valor_str = str(valor).strip()
            if valor_str and valor_str.lower() not in ("null", "undefined", "none"):
                folder_id_final = valor_str
                break

    where_filter = {"user_id": {"$eq": body.user_id}}

    if folder_id_final:
        where_filter = {
            "$and": [
                {"user_id": {"$eq": body.user_id}},
                {"folder_id": {"$eq": folder_id_final}},
            ]
        }

    try:
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=body.limit,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

    output = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i]
        
        # Soft delete: omitir si está marcado como eliminado lógicamente (esta_eliminado = 1)
        if meta.get("esta_eliminado") == 1:
            continue
            
        doc_id = meta.get("document_id")
        if doc_id:
            ruta_int = f"./depuracion_local/{doc_id}.json"
            if os.path.exists(ruta_int):
                try:
                    with open(ruta_int, "r", encoding="utf-8") as f_int:
                        datos_int = json.load(f_int)
                    if datos_int.get("esta_eliminado") == 1:
                        continue
                except Exception:
                    pass
        
        distance = results["distances"][0][i]
        similarity = round(1 - distance, 4)

        output.append(SearchResult(
            document_id=meta["document_id"],
            document_name=meta["document_name"],
            chunk_text=doc,
            similarity=similarity,
            document_path=meta["document_path"],
        ))

    return output


@router.post("/ia", response_model=SearchIaResponse)
@router.post("/ia/", response_model=SearchIaResponse)
@router.post("/buscar", response_model=SearchIaResponse)
@router.post("/buscar/", response_model=SearchIaResponse)
async def search_ia(body: SearchRequest):
    """
    Realiza una búsqueda semántica de documentos (RAG).
    Vectoriza la consulta, busca en la base de datos (con fallback local) y
    sintetiza una respuesta usando Groq.
    Clasifica los resultados en documento principal (máxima similitud) y secundarios.
    """
    try:
        # 1. Vectorizar la consulta
        query_embedding = model.encode_query(body.query)

        fragmentos_encontrados = []
        usando_db_remota = False

        # 2. Intentar buscar en Supabase vía RPC 'buscar_fragmentos_similares'
        if cliente_supabase:
            try:
                print("Intentando búsqueda vectorial vía RPC en Supabase...")
                
                # Conversión segura a entero para BIGINT de Supabase
                try:
                    usr_id_val = int(body.user_id)
                except (ValueError, TypeError):
                    usr_id_val = body.user_id
                    
                # Unificar y sanear el ID de la carpeta
                folder_id_final = None
                for valor in [body.folder_id, body.carpeta_id, body.id_folder, body.id_carpeta]:
                    if valor is not None:
                        valor_str = str(valor).strip()
                        if valor_str and valor_str.lower() not in ("null", "undefined", "none"):
                            folder_id_final = valor_str
                            break

                folder_id_val = None
                if folder_id_final:
                    try:
                        folder_id_val = int(folder_id_final)
                    except (ValueError, TypeError):
                        folder_id_val = folder_id_final

                # La función buscar_fragmentos_similares recibe consulta_embedding, usuario_id_filtro, carpeta_id_filtro y limite
                resultados_rpc = await cliente_supabase.rpc("buscar_fragmentos_similares", {
                    "consulta_embedding": query_embedding,
                    "usuario_id_filtro": usr_id_val,
                    "carpeta_id_filtro": folder_id_val,
                    "limite": body.limit
                })
                if resultados_rpc:
                    fragmentos_encontrados = resultados_rpc
                    usando_db_remota = True
                    print(f"Búsqueda vectorial exitosa en Supabase. {len(resultados_rpc)} fragmentos recuperados.")
            except Exception as error_rpc:
                print(f"Advertencia: Error al llamar a RPC buscar_fragmentos_similares: {error_rpc}")

        # 3. Fallback local si no pudimos consultar Supabase o no arrojó resultados
        if not usando_db_remota or not fragmentos_encontrados:
            print("Ejecutando motor de coincidencia vectorial local desde archivos JSON...")
            candidatos = []
            ruta_depuracion = "./depuracion_local"
            
            # Recalcular folder_id_final localmente para fallback
            folder_id_final = None
            for valor in [body.folder_id, body.carpeta_id, body.id_folder, body.id_carpeta]:
                if valor is not None:
                    valor_str = str(valor).strip()
                    if valor_str and valor_str.lower() not in ("null", "undefined", "none"):
                        folder_id_final = valor_str
                        break
            
            # Buscar en los archivos individuales embeddings_{id}.json
            if os.path.exists(ruta_depuracion):
                for archivo_nombre in os.listdir(ruta_depuracion):
                    if archivo_nombre.startswith("embeddings_") and archivo_nombre.endswith(".json"):
                        ruta_completa = os.path.join(ruta_depuracion, archivo_nombre)
                        try:
                            with open(ruta_completa, "r", encoding="utf-8") as f:
                                datos_emb = json.load(f)
                            doc_id = datos_emb.get("documento_id")
                            
                            # Cargar metadatos de integridad local para filtrar por usuario/carpeta
                            ruta_int_local = os.path.join(ruta_depuracion, f"{doc_id}.json")
                            if os.path.exists(ruta_int_local):
                                with open(ruta_int_local, "r", encoding="utf-8") as f_int:
                                    datos_int = json.load(f_int)
                                if body.user_id and str(datos_int.get("usuario_id")) != str(body.user_id):
                                    continue
                                if folder_id_final and str(datos_int.get("carpeta_id")) != str(folder_id_final):
                                    continue
                                # Soft delete: omitir si está marcado como eliminado lógicamente (esta_eliminado = 1)
                                if datos_int.get("esta_eliminado") == 1:
                                    continue
                            else:
                                # Excluir si no hay registro de integridad local por seguridad
                                continue

                            for frag_item in datos_emb.get("fragmentos", []):
                                v_emb = frag_item.get("embedding", [])
                                frag_text = frag_item.get("fragmento", "")
                                pos = frag_item.get("posicion", 0)
                                
                                if len(v_emb) == len(query_embedding) and len(query_embedding) > 0:
                                    sim = sum(x * y for x, y in zip(v_emb, query_embedding))
                                else:
                                    sim = 0.0
                                    
                                candidatos.append({
                                    "documento_id": doc_id,
                                    "fragmento": frag_text,
                                    "similitud": sim,
                                    "posicion": pos
                                })
                        except Exception as err_arch:
                            print(f"Error procesando archivo local {archivo_nombre}: {err_arch}")

            # Buscar también en vectores_mock.json (Chroma fallback)
            ruta_vectores = "./depuracion_local/vectores_mock.json"
            if os.path.exists(ruta_vectores):
                try:
                    with open(ruta_vectores, "r", encoding="utf-8") as f:
                        datos_vectores = json.load(f)
                    for item in datos_vectores:
                        meta = item.get("metadata", {})
                        if body.user_id and str(meta.get("user_id")) != str(body.user_id):
                            continue
                        
                        # Soft delete: omitir si está marcado como eliminado lógicamente (esta_eliminado = 1)
                        if meta.get("esta_eliminado") == 1:
                            continue
                        
                        # Recalcular folder_id_final localmente para el mock
                        folder_id_final = None
                        for valor in [body.folder_id, body.carpeta_id, body.id_folder, body.id_carpeta]:
                            if valor is not None:
                                valor_str = str(valor).strip()
                                if valor_str and valor_str.lower() not in ("null", "undefined", "none"):
                                    folder_id_final = valor_str
                                    break
                                    
                        if folder_id_final and str(meta.get("folder_id")) != str(folder_id_final):
                            continue
                            
                        v_emb = item.get("embedding", [])
                        frag_text = item.get("document", "")
                        doc_id = meta.get("document_id")
                        
                        if len(v_emb) == len(query_embedding) and len(query_embedding) > 0:
                            sim = sum(x * y for x, y in zip(v_emb, query_embedding))
                        else:
                            sim = 0.0
                            
                        candidatos.append({
                            "documento_id": doc_id,
                            "fragmento": frag_text,
                            "similitud": sim,
                            "nombre_doc_mock": meta.get("document_name"),
                            "ruta_doc_mock": meta.get("document_path")
                        })
                except Exception as err_mock:
                    print(f"Error procesando vectores_mock.json: {err_mock}")

            # Ordenar por similitud y cortar
            candidatos.sort(key=lambda x: x["similitud"], reverse=True)
            fragmentos_encontrados = candidatos[:body.limit]

        if not fragmentos_encontrados:
            msg_sin_docs = "No se encontraron documentos indexados en el sistema para realizar la consulta semántica."
            from services.parser import parsear_markdown_a_html
            return SearchIaResponse(
                respuesta_ia=msg_sin_docs,
                respuesta_html=parsear_markdown_a_html(msg_sin_docs),
                documento_principal=None,
                documentos_secundarios=[],
                fragmentos=[]
            )

        # 4. Obtener metadatos de documentos asociados
        documentos_metadatos = {}
        ids_documentos = list(set([f["documento_id"] for f in fragmentos_encontrados if f.get("documento_id")]))

        if usando_db_remota and ids_documentos:
            try:
                # Filtrar con in. en Supabase
                ids_formateados = ",".join(ids_documentos)
                filtro_in = f"id=in.({ids_formateados})"
                docs_db = await cliente_supabase.consultar_por_filtro("documentos_integridad", select="id,nombre,ruta_archivo", filtros=filtro_in)
                for doc in docs_db:
                    documentos_metadatos[doc["id"]] = {
                        "nombre": doc["nombre"],
                        "ruta_archivo": doc["ruta_archivo"]
                    }
            except Exception as err_meta:
                print(f"Error cargando metadatos desde Supabase: {err_meta}")

        # Rellenar con metadatos locales si faltan
        for doc_id in ids_documentos:
            if doc_id not in documentos_metadatos:
                ruta_doc_local = f"./depuracion_local/{doc_id}.json"
                if os.path.exists(ruta_doc_local):
                    try:
                        with open(ruta_doc_local, "r", encoding="utf-8") as f:
                            doc_local_data = json.load(f)
                        documentos_metadatos[doc_id] = {
                            "nombre": doc_local_data.get("nombre", "documento_local.pdf"),
                            "ruta_archivo": doc_local_data.get("ruta_archivo", "")
                        }
                    except Exception:
                        pass
                else:
                    # Buscar en los fragmentos de fallback de vectores_mock.json
                    nombre_encontrado = "documento_desconocido"
                    ruta_encontrada = ""
                    for f in fragmentos_encontrados:
                        if f.get("documento_id") == doc_id and f.get("nombre_doc_mock"):
                            nombre_encontrado = f["nombre_doc_mock"]
                            ruta_encontrada = f.get("ruta_doc_mock", "")
                            break
                    documentos_metadatos[doc_id] = {
                        "nombre": nombre_encontrado,
                        "ruta_archivo": ruta_encontrada
                    }

        # 5. Algoritmo de Clasificación: Principal y Secundarios
        # Como los fragmentos ya están ordenados por similitud de coseno descendente:
        primer_frag = fragmentos_encontrados[0]
        id_principal = primer_frag["documento_id"]
        meta_principal = documentos_metadatos.get(id_principal, {"nombre": "documento_desconocido", "ruta_archivo": ""})

        documento_principal = DocumentoCoincidencia(
            documento_id=id_principal,
            nombre=meta_principal["nombre"],
            similitud=round(primer_frag["similitud"], 4),
            ruta_archivo=meta_principal["ruta_archivo"]
        )

        documentos_secundarios_dict = {}
        for frag in fragmentos_encontrados[1:]:
            id_doc = frag["documento_id"]
            if id_doc != id_principal:
                if id_doc not in documentos_secundarios_dict:
                    meta_sec = documentos_metadatos.get(id_doc, {"nombre": "documento_desconocido", "ruta_archivo": ""})
                    documentos_secundarios_dict[id_doc] = DocumentoCoincidencia(
                        documento_id=id_doc,
                        nombre=meta_sec["nombre"],
                        similitud=round(frag["similitud"], 4),
                        ruta_archivo=meta_sec["ruta_archivo"]
                    )
        documentos_secundarios = list(documentos_secundarios_dict.values())

        # 6. Construir el contexto para la síntesis de IA
        contexto_items = []
        for i, f in enumerate(fragmentos_encontrados):
            nombre_doc = documentos_metadatos.get(f["documento_id"], {}).get("nombre", "documento_desconocido")
            contexto_items.append(f"[Documento: {nombre_doc} | Similitud: {f['similitud']:.2%}]\n{f['fragmento']}")
        contexto = "\n\n---\n\n".join(contexto_items)

        # 7. Ejecutar consulta generativa RAG usando Groq
        respuesta_ia_texto = ""
        groq_api_key = os.environ.get("GROQ_API_KEY", "")

        if groq_api_key:
            try:
                from services.groq_client import completar_chat_con_fallback
                print("Enviando prompt de RAG a Groq con rotación de modelos...")
                respuesta_ia_texto = await completar_chat_con_fallback(
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "Eres un asistente de inteligencia artificial especialista en análisis documental "
                                "y auditoría de gestión pública para la plataforma SIGEDI. "
                                "Tu trabajo es responder a la pregunta del usuario en base al contexto de documentos provisto. "
                                "Responde SIEMPRE en español de forma profesional, clara y concisa. "
                                "Cita siempre los nombres de los documentos fuente en los que te basas para responder."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Contexto documental:\n{contexto}\n\nPregunta del usuario: {body.query}",
                        },
                    ],
                    temperature=0.3,
                    max_tokens=1500,
                )
                print("Respuesta recibida exitosamente desde Groq.")
            except Exception as error_groq:
                print(f"Error al conectar con Groq: {error_groq}. Iniciando generación local.")

        if not respuesta_ia_texto:
            # Fallback en caso de que no haya API key o haya fallado Groq
            respuesta_ia_texto = (
                f"**[Respuesta del Sistema - Modo de Depuración Local]**\n\n"
                f"El servicio generativo de IA (Groq) no está disponible en este momento. Sin embargo, he procesado tus "
                f"documentos y he encontrado información relevante.\n\n"
                f"El documento más coincidente por contexto semántico es **{documento_principal.nombre}**.\n\n"
                f"**Fragmento clave extraído de {documento_principal.nombre}:**\n"
                f"\"{primer_frag['fragmento']}\"\n\n"
            )
            if documentos_secundarios:
                nombres_secundarios = ", ".join([f"**{d.nombre}** (Similitud: {d.similitud:.2%})" for d in documentos_secundarios])
                respuesta_ia_texto += f"También se detectaron coincidencias secundarias en los documentos: {nombres_secundarios}."

        # 8. Mapear resultados a SearchResult
        fragmentos_resultado = []
        for f in fragmentos_encontrados:
            meta = documentos_metadatos.get(f["documento_id"], {"nombre": "documento_desconocido", "ruta_archivo": ""})
            fragmentos_resultado.append(SearchResult(
                document_id=f["documento_id"],
                document_name=meta["nombre"],
                chunk_text=f["fragmento"],
                similarity=round(f["similitud"], 4),
                document_path=meta["ruta_archivo"]
            ))

        from services.parser import parsear_markdown_a_html
        respuesta_html_texto = parsear_markdown_a_html(respuesta_ia_texto)

        return SearchIaResponse(
            respuesta_ia=respuesta_ia_texto,
            respuesta_html=respuesta_html_texto,
            documento_principal=documento_principal,
            documentos_secundarios=documentos_secundarios,
            fragmentos=fragmentos_resultado
        )

    except Exception as error_general:
        raise HTTPException(status_code=500, detail=f"Error en el endpoint de búsqueda IA: {str(error_general)}")
