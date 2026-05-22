import urllib.request
import json
import mimetypes

def make_multipart_body(fields, files):
    boundary = b'----WebKitFormBoundary7MA4YWxkTrZu0gW'
    body = []
    
    for name, value in fields.items():
        if value is None:
            continue
        body.append(b'--' + boundary)
        body.append(f'Content-Disposition: form-data; name="{name}"'.encode('utf-8'))
        body.append(b'')
        body.append(str(value).encode('utf-8'))
        
    for name, filename, content in files:
        body.append(b'--' + boundary)
        body.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"'.encode('utf-8'))
        mime = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        body.append(f'Content-Type: {mime}'.encode('utf-8'))
        body.append(b'')
        body.append(content)
        
    body.append(b'--' + boundary + b'--')
    body.append(b'')
    
    headers = {
        'Content-Type': f'multipart/form-data; boundary={boundary.decode("utf-8")}'
    }
    
    return b'\r\n'.join(body), headers

print("1. Subiendo Documento 1 (Obras Viales)...")
doc1_contenido = b"El municipio ha destinado un presupuesto de 5 millones de pesos para la licitacion de obras viales y pavimentacion de carreteras principales durante el periodo 2026."
fields = {"usuario_id": "999"}
files = [("archivo", "obras_viales.txt", doc1_contenido)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")
doc1_id = None
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Resultado subida Documento 1:", res)
        doc1_id = res.get("document_id")
except Exception as e:
    print("Error subiendo Documento 1:", e)

print("\n2. Subiendo Documento 2 (Personal Administrativo)...")
doc2_contenido = b"El departamento de recursos humanos informa que la contratacion de personal administrativo esta sujeta al reglamento interno del ayuntamiento y requiere aprobacion del cabildo."
files = [("archivo", "recursos_humanos.txt", doc2_contenido)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")
doc2_id = None
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Resultado subida Documento 2:", res)
        doc2_id = res.get("document_id")
except Exception as e:
    print("Error subiendo Documento 2:", e)

if doc1_id and doc2_id:
    print("\n3. Probando Endpoint de busqueda con IA (/search/ia) - Consulta sobre carreteras...")
    search_data = {
        "query": "cual es el presupuesto asignado para carreteras y pavimentacion?",
        "user_id": "999",
        "limit": 5
    }
    req_search = urllib.request.Request(
        "http://127.0.0.1:8000/search/ia",
        data=json.dumps(search_data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req_search) as resp:
            resultado_ia = json.loads(resp.read().decode('utf-8'))
            print("\n--- Respuesta del Buscador de IA ---")
            print("Respuesta Sintetizada:", resultado_ia.get("respuesta_ia"))
            print("\nDocumento Principal Coincidente:")
            print(resultado_ia.get("documento_principal"))
            print("\nDocumentos Secundarios Coincidentes:")
            print(resultado_ia.get("documentos_secundarios"))
            print("\nFragmentos totales devueltos:", len(resultado_ia.get("fragmentos", [])))
            
            # Verificaciones
            doc_principal = resultado_ia.get("documento_principal")
            if doc_principal and doc_principal.get("documento_id") == doc1_id:
                print("\n[OK] Clasificacion exitosa: el documento de obras viales fue clasificado como PRINCIPAL.")
            else:
                print("\n[FALLA] Clasificacion incorrecta en el documento principal o vacia.")
    except Exception as e:
        print("Error en busqueda IA:", e)
else:
    print("\n[ERROR] No se pudieron subir los documentos de prueba.")
