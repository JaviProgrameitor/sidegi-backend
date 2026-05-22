# -*- coding: utf-8 -*-
"""
Script de pruebas autónomas en tiempo real para SIGEDI.
Inicia el servidor local, sube los archivos de prueba, realiza búsquedas vectoriales
y ejecuta auditorías de IA.
"""

import subprocess
import time
import urllib.request
import json
import mimetypes
import os
import sys

URL_BASE = "http://127.0.0.1:8000"

def preparar_datos_supabase(usuario_id: int, carpeta_id: int):
    """
    Crea un usuario temporal y una carpeta en la base de datos de Supabase
    para evitar errores de clave foránea (FK) al subir documentos.
    """
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="../.env")
    load_dotenv()
    
    url_supabase = os.environ.get("SUPABASE_URL", "").rstrip('/')
    clave_supabase = os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not url_supabase or not clave_supabase:
        print("Advertencia: No se encontraron las credenciales de Supabase en las variables de entorno.")
        return
        
    cabeceras = {
        "apikey": clave_supabase,
        "Authorization": f"Bearer {clave_supabase}",
        "Content-Type": "application/json"
    }
    
    # 1. Crear o verificar usuario
    print(f"Verificando si el usuario {usuario_id} existe en Supabase...")
    url_usuario = f"{url_supabase}/rest/v1/users?id_user=eq.{usuario_id}"
    peticion_get_usr = urllib.request.Request(url_usuario, headers=cabeceras, method="GET")
    
    try:
        with urllib.request.urlopen(peticion_get_usr) as respuesta:
            usuarios = json.loads(respuesta.read().decode('utf-8'))
            if not usuarios:
                print(f"El usuario {usuario_id} no existe. Creando usuario temporal...")
                datos_usuario = {
                    "id_user": usuario_id,
                    "name": "Usuario de Pruebas",
                    "last_name": "Autónomas",
                    "email": "pruebas@sigedi.com"
                }
                url_post_usr = f"{url_supabase}/rest/v1/users"
                peticion_post_usr = urllib.request.Request(
                    url_post_usr, 
                    data=json.dumps(datos_usuario).encode('utf-8'), 
                    headers=cabeceras, 
                    method="POST"
                )
                with urllib.request.urlopen(peticion_post_usr) as resp_post:
                    print("Usuario temporal creado con éxito en Supabase.")
            else:
                print(f"El usuario {usuario_id} ya existe.")
    except Exception as error_usuario:
        print(f"Error al preparar usuario en Supabase: {error_usuario}")
        if hasattr(error_usuario, 'read'):
            try:
                print("Detalles del error del servidor:", error_usuario.read().decode('utf-8'))
            except Exception:
                pass
                
    # 2. Crear o verificar carpeta
    print(f"Verificando si la carpeta {carpeta_id} existe en Supabase...")
    url_carpeta = f"{url_supabase}/rest/v1/folders?id_folder=eq.{carpeta_id}"
    peticion_get_fld = urllib.request.Request(url_carpeta, headers=cabeceras, method="GET")
    
    try:
        with urllib.request.urlopen(peticion_get_fld) as respuesta:
            carpetas = json.loads(respuesta.read().decode('utf-8'))
            if not carpetas:
                print(f"La carpeta {carpeta_id} no existe. Creando carpeta temporal...")
                datos_carpeta = {
                    "id_folder": carpeta_id,
                    "folder_name": "Carpeta de Pruebas",
                    "user_id": usuario_id,
                    "created_at": "2026-05-22T00:00:00Z"
                }
                url_post_fld = f"{url_supabase}/rest/v1/folders"
                peticion_post_fld = urllib.request.Request(
                    url_post_fld, 
                    data=json.dumps(datos_carpeta).encode('utf-8'), 
                    headers=cabeceras, 
                    method="POST"
                )
                with urllib.request.urlopen(peticion_post_fld) as resp_post:
                    print("Carpeta temporal creada con éxito en Supabase.")
            else:
                print(f"La carpeta {carpeta_id} ya existe.")
    except Exception as error_carpeta:
        print(f"Error al preparar carpeta en Supabase: {error_carpeta}")
        if hasattr(error_carpeta, 'read'):
            try:
                print("Detalles del error del servidor:", error_carpeta.read().decode('utf-8'))
            except Exception:
                pass

def limpiar_datos_supabase(usuario_id: int, carpeta_id: int):
    """
    Elimina los datos temporales llamando al RPC seguro 'eliminar_usuario_y_datos_prueba'
    en Supabase, el cual desactiva temporalmente el trigger de inmutabilidad
    mediante una transacción controlada con privilegios elevados.
    """
    from dotenv import load_dotenv
    load_dotenv(dotenv_path="../.env")
    load_dotenv()
    
    url_supabase = os.environ.get("SUPABASE_URL", "").rstrip('/')
    clave_supabase = os.environ.get("SUPABASE_SERVICE_KEY", "")
    
    if not url_supabase or not clave_supabase:
        return
        
    cabeceras = {
        "apikey": clave_supabase,
        "Authorization": f"Bearer {clave_supabase}",
        "Content-Type": "application/json"
    }
    
    print(f"\nLimpiando datos temporales en Supabase mediante RPC para el usuario {usuario_id}...")
    
    url_rpc = f"{url_supabase}/rest/v1/rpc/eliminar_usuario_y_datos_prueba"
    datos_rpc = {
        "usr_id": usuario_id,
        "fld_id": carpeta_id
    }
    
    peticion_rpc = urllib.request.Request(
        url_rpc,
        data=json.dumps(datos_rpc).encode('utf-8'),
        headers=cabeceras,
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(peticion_rpc) as respuesta:
            print(f"Limpieza completada con éxito. Usuario {usuario_id} y carpeta {carpeta_id} eliminados vía RPC.")
    except Exception as error_rpc:
        print(f"Error al ejecutar RPC de limpieza: {error_rpc}")
        if hasattr(error_rpc, 'read'):
            try:
                print("Detalles del error del servidor:", error_rpc.read().decode('utf-8'))
            except Exception:
                pass



def crear_cuerpo_multipart(campos: dict, archivos: list) -> tuple:
    """
    Crea un cuerpo multipart/form-data codificado en bytes para urllib.
    """
    limite = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
    cuerpo = []
    
    for nombre, valor in campos.items():
        if valor is None:
            continue
        cuerpo.append(b'--' + limite)
        cuerpo.append(f'Content-Disposition: form-data; name="{nombre}"'.encode('utf-8'))
        cuerpo.append(b'')
        cuerpo.append(str(valor).encode('utf-8'))
        
    for nombre, nombre_archivo, contenido in archivos:
        cuerpo.append(b'--' + limite)
        cuerpo.append(f'Content-Disposition: form-data; name="{nombre}"; filename="{nombre_archivo}"'.encode('utf-8'))
        tipo_mime = mimetypes.guess_type(nombre_archivo)[0] or 'application/octet-stream'
        cuerpo.append(f'Content-Type: {tipo_mime}'.encode('utf-8'))
        cuerpo.append(b'')
        cuerpo.append(contenido)
        
    cuerpo.append(b'--' + limite + b'--')
    cuerpo.append(b'')
    
    cabeceras = {
        'Content-Type': f'multipart/form-data; boundary={limite.decode("utf-8")}'
    }
    
    return b'\r\n'.join(cuerpo), cabeceras

def esperar_servidor(intentos_maximos: int = 10) -> bool:
    """
    Realiza peticiones al health check del servidor hasta que esté en línea.
    """
    print("Esperando a que el servidor FastAPI se inicie...")
    for intento in range(1, intentos_maximos + 1):
        try:
            with urllib.request.urlopen(f"{URL_BASE}/", timeout=2) as respuesta:
                if respuesta.status == 200:
                    datos = json.loads(respuesta.read().decode('utf-8'))
                    print(f"Servidor en línea (Intento {intento}). Respuesta: {datos}")
                    return True
        except Exception:
            pass
        time.sleep(1.5)
    return False

def subir_documento_prueba(ruta_archivo: str, usuario_id: str) -> dict:
    """
    Lee un archivo de la ruta especificada y lo sube al backend de SIGEDI.
    """
    nombre_archivo = os.path.basename(ruta_archivo)
    if not os.path.exists(ruta_archivo):
        print(f"Error: El archivo no existe en la ruta {ruta_archivo}")
        return {}

    print(f"\nSubiendo documento: {nombre_archivo}...")
    with open(ruta_archivo, "rb") as archivo_fisico:
        contenido = archivo_fisico.read()

    campos = {"usuario_id": usuario_id}
    archivos = [("archivo", nombre_archivo, contenido)]
    cuerpo, cabeceras = crear_cuerpo_multipart(campos, archivos)

    peticion = urllib.request.Request(
        f"{URL_BASE}/documents/",
        data=cuerpo,
        headers=cabeceras,
        method="POST"
    )

    tiempo_inicio = time.time()
    try:
        with urllib.request.urlopen(peticion) as respuesta:
            duracion = time.time() - tiempo_inicio
            resultado = json.loads(respuesta.read().decode('utf-8'))
            print(f"Subida exitosa de {nombre_archivo} en {duracion:.2f} segundos.")
            print(f"ID del documento: {resultado.get('document_id')}")
            print(f"Fragmentos indexados: {resultado.get('chunks_indexed')}")
            resultado["duracion_segundos"] = duracion
            return resultado
    except Exception as error_subida:
        print(f"Error al subir el documento {nombre_archivo}: {error_subida}")
        if hasattr(error_subida, 'read'):
            try:
                print("Detalles del error del servidor:", error_subida.read().decode('utf-8'))
            except Exception:
                pass
        return {}

def realizar_busqueda_ia(consulta: str, usuario_id: str, limite: int = 5) -> dict:
    """
    Realiza una búsqueda semántica de IA (RAG) en el servidor.
    """
    print(f"\nRealizando consulta semántica: '{consulta}'...")
    datos_cuerpo = {
        "query": consulta,
        "user_id": usuario_id,
        "limit": limite
    }
    
    peticion = urllib.request.Request(
        f"{URL_BASE}/search/ia",
        data=json.dumps(datos_cuerpo).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )

    try:
        with urllib.request.urlopen(peticion) as respuesta:
            resultado = json.loads(respuesta.read().decode('utf-8'))
            print("--- RESPUESTA SINTETIZADA POR LA IA ---")
            print(resultado.get("respuesta_ia"))
            print("---------------------------------------")
            print("--- RESPUESTA HTML GENERADA ---")
            print(resultado.get("respuesta_html"))
            print("-------------------------------")
            
            doc_principal = resultado.get("documento_principal")
            if doc_principal:
                print(f"Documento Principal Coincidente: {doc_principal.get('nombre')} (Similitud: {doc_principal.get('similitud'):.2%})")
            
            docs_secundarios = resultado.get("documentos_secundarios", [])
            if docs_secundarios:
                print("Documentos Secundarios:")
                for doc_sec in docs_secundarios:
                    print(f"  - {doc_sec.get('nombre')} (Similitud: {doc_sec.get('similitud'):.2%})")
            
            return resultado
    except Exception as error_busqueda:
        print(f"Error al realizar la búsqueda IA: {error_busqueda}")
        if hasattr(error_busqueda, 'read'):
            try:
                print("Detalles del error:", error_busqueda.read().decode('utf-8'))
            except Exception:
                pass
        return {}

def auditar_documento(documento_id: str, enfoque: str = "general") -> dict:
    """
    Ejecuta el servicio de auditoría de IA para evaluar riesgos del documento.
    """
    print(f"\nEjecutando auditoría con enfoque '{enfoque}' para el ID {documento_id}...")
    datos_cuerpo = {
        "documento_id": documento_id,
        "enfoque": enfoque
    }
    
    peticion = urllib.request.Request(
        f"{URL_BASE}/auditoria/auditar",
        data=json.dumps(datos_cuerpo).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method="POST"
    )

    try:
        with urllib.request.urlopen(peticion) as respuesta:
            resultado = json.loads(respuesta.read().decode('utf-8'))
            print("=== INFORME DE AUDITORÍA DE SIGEDI ===")
            print(f"Documento: {resultado.get('documento')}")
            print(f"Nivel de Riesgo: {resultado.get('nivel_riesgo').upper()}")
            print(f"Hash inmutable del reporte: {resultado.get('hash_inmutable')}")
            print(f"Almacenamiento remoto exitoso: {resultado.get('almacenado_remoto')}")
            print("\nHALLAZGOS Y ANÁLISIS:")
            print(resultado.get("hallazgos"))
            print("======================================")
            print("=== HALLAZGOS EN HTML ===")
            print(resultado.get("hallazgos_html"))
            print("=========================")
            return resultado
    except Exception as error_auditoria:
        print(f"Error al auditar el documento: {error_auditoria}")
        if hasattr(error_auditoria, 'read'):
            try:
                print("Detalles del error:", error_auditoria.read().decode('utf-8'))
            except Exception:
                pass
        return {}

def ejecutar_pruebas():
    """
    Función principal de orquestación de la prueba.
    """
    # Usar venv de Python si existe, de lo contrario usar sys.executable
    python_ejecutable = os.path.join(".", "venv", "Scripts", "python.exe")
    if not os.path.exists(python_ejecutable):
        python_ejecutable = sys.executable

    # Registrar variables para telemetría
    usuario_prueba = 100
    carpeta_prueba = 1
    usuario_prueba_str = str(usuario_prueba)
    documentos_subidos = {}
    
    # Preparar el entorno de datos en Supabase antes de arrancar las pruebas
    preparar_datos_supabase(usuario_prueba, carpeta_prueba)

    print(f"Iniciando proceso de FastAPI usando: {python_ejecutable}")
    
    # Arrancar el servidor en segundo plano sin ocultar su salida estándar para depuración
    proceso_servidor = subprocess.Popen(
        [python_ejecutable, "-m", "uvicorn", "main:app", "--port", "8000"]
    )
    
    try:
        # Esperar a que el servidor FastAPI esté listo
        if not esperar_servidor():
            print("Error: No se pudo levantar el servidor FastAPI.")
            proceso_servidor.terminate()
            return
            
        # Subir los archivos PDF requeridos
        gafete_ruta = "GAFET PARTICIPANTE.pdf"
        presentacion_ruta = "PRESENTACION INNOVATECNM2026  Hackatec.pdf"
        
        datos_gafete = subir_documento_prueba(gafete_ruta, usuario_prueba_str)
        datos_presentacion = subir_documento_prueba(presentacion_ruta, usuario_prueba_str)
        
        if not datos_gafete or not datos_presentacion:
            print("Error: Uno o ambos documentos fallaron en el proceso de subida e indexación.")
            return

        id_gafete = datos_gafete.get("document_id")
        id_presentacion = datos_presentacion.get("document_id")
        
        documentos_subidos[id_gafete] = "GAFET PARTICIPANTE.pdf"
        documentos_subidos[id_presentacion] = "PRESENTACION INNOVATECNM2026  Hackatec.pdf"
        
        # Realizar búsquedas semánticas
        # 1. Búsqueda semántica para: "correo del entregable"
        print("\n\n--- PRUEBA DE BÚSQUEDA SEMÁNTICA 1 ---")
        realizar_busqueda_ia("correo del entregable", usuario_prueba_str)
        
        # 2. Búsqueda semántica para: "que dice el gafete"
        print("\n\n--- PRUEBA DE BÚSQUEDA SEMÁNTICA 2 ---")
        realizar_busqueda_ia("que dice el gafete", usuario_prueba_str)
        
        # Realizar auditorías
        print("\n\n--- PRUEBA DE AUDITORÍA 1 (GAFETE) ---")
        auditar_documento(id_gafete, enfoque="general")
        
        print("\n\n--- PRUEBA DE AUDITORÍA 2 (PRESENTACIÓN) ---")
        auditar_documento(id_presentacion, enfoque="irregularidades")
        
    finally:
        print("\nFinalizando y deteniendo el servidor FastAPI...")
        proceso_servidor.terminate()
        try:
            proceso_servidor.wait(timeout=5)
            print("Servidor detenido correctamente.")
        except subprocess.TimeoutExpired:
            proceso_servidor.kill()
            print("Servidor forzado a detenerse.")
        
        # Limpiar datos temporales de Supabase
        limpiar_datos_supabase(usuario_prueba, carpeta_prueba)

if __name__ == "__main__":
    import sys
    # Configurar codificación en Windows para evitar errores charmap
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')
    ejecutar_pruebas()
