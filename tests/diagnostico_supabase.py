# -*- coding: utf-8 -*-
"""
Script de Diagnóstico para Supabase en SIGEDI.
Verifica la conexión, el acceso a las tablas clave y detecta inconsistencias.
"""
import os
import sys
import json
import urllib.request
from dotenv import load_dotenv

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

load_dotenv()

def realizar_peticion(url, cabeceras, metodo="GET", datos=None):
    cuerpo = json.dumps(datos).encode('utf-8') if datos else None
    peticion = urllib.request.Request(url, data=cuerpo, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            contenido = respuesta.read().decode('utf-8')
            return json.loads(contenido) if contenido else {}
    except Exception as e:
        detalle = ""
        if hasattr(e, 'read'):
            try:
                detalle = e.read().decode('utf-8')
            except Exception:
                pass
        raise Exception(f"{e} - Detalle: {detalle}")

def diagnosticar():
    url_supabase = os.environ.get("SUPABASE_URL", "").rstrip('/')
    clave_supabase = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
    
    print("=== DIAGNÓSTICO DE CONEXIÓN A SUPABASE ===")
    print(f"URL de Supabase: {url_supabase}")
    print(f"Clave de Servicio configurada: {'Sí (longitud: ' + str(len(clave_supabase)) + ')' if clave_supabase else 'No'}")
    
    if not url_supabase or not clave_supabase:
        print("ERROR: No se han configurado las variables de entorno de Supabase correctamente.")
        return

    cabeceras = {
        "apikey": clave_supabase,
        "Authorization": f"Bearer {clave_supabase}",
        "Content-Type": "application/json"
    }

    # 1. Comprobar salud básica del API REST de PostgREST
    print("\n1. Probando conexión básica al API REST...")
    try:
        # Consultar la raíz de PostgREST
        realizar_peticion(f"{url_supabase}/rest/v1/", cabeceras)
        print("¡Conexión exitosa! El API de Supabase responde correctamente.")
    except Exception as e:
        print(f"ERROR al conectar con el API REST de Supabase: {e}")
        return

    # 2. Verificar existencia de las tablas de documentos y contar registros
    tablas = ["users", "folders", "documentos_integridad", "documentos_embeddings", "documentos_auditoria"]
    print("\n2. Inspeccionando tablas clave y conteo de registros...")
    
    for tabla in tablas:
        url_tabla = f"{url_supabase}/rest/v1/{tabla}?select=count"
        cabeceras_conteo = cabeceras.copy()
        cabeceras_conteo["Prefer"] = "count=exact"
        try:
            peticion = urllib.request.Request(url_tabla, headers=cabeceras_conteo, method="GET")
            with urllib.request.urlopen(peticion) as respuesta:
                rango = respuesta.headers.get("Content-Range")
                conteo = rango.split("/")[-1] if rango else "desconocido"
                print(f"  - Tabla '{tabla}': Conexión exitosa. Registros: {conteo}")
        except Exception as e:
            print(f"  - Tabla '{tabla}': ERROR al consultar o no existe. Detalle: {e}")

    # 3. Diagnosticar documentos huérfanos o inconsistentes
    print("\n3. Buscando documentos huérfanos en Supabase...")
    try:
        url_docs = f"{url_supabase}/rest/v1/documentos_integridad?select=id,nombre,hash_sha256"
        docs = realizar_peticion(url_docs, cabeceras)
        print(f"Se encontraron {len(docs)} documentos registrados en la tabla de integridad.")
        
        for doc in docs:
            doc_id = doc["id"]
            nombre = doc["nombre"]
            
            # Consultar si tiene embeddings
            url_embs = f"{url_supabase}/rest/v1/documentos_embeddings?select=count&documento_id=eq.{doc_id}"
            cabeceras_conteo = cabeceras.copy()
            cabeceras_conteo["Prefer"] = "count=exact"
            
            peticion_embs = urllib.request.Request(url_embs, headers=cabeceras_conteo, method="GET")
            try:
                with urllib.request.urlopen(peticion_embs) as resp_embs:
                    rango = resp_embs.headers.get("Content-Range")
                    cant_embs = int(rango.split("/")[-1]) if rango else 0
            except Exception:
                cant_embs = -1 # Error
                
            estado = "COMPLETO" if cant_embs > 0 else ("INCOMPLETO (Sin embeddings)" if cant_embs == 0 else "ERROR DE CONSULTA")
            print(f"  - Documento '{nombre}' (ID: {doc_id}): {estado} (Fragmentos: {cant_embs})")
    except Exception as e:
        print(f"ERROR al listar e inspeccionar documentos: {e}")

if __name__ == "__main__":
    diagnosticar()
