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

print("1. Probando Health Check...")
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/") as resp:
        print("Respuesta de salud:", json.loads(resp.read().decode('utf-8')))
except Exception as e:
    print("Error:", e)

print("\n2. Subiendo archivo de prueba...")
contenido = b"Contenido de prueba para auditoria de integridad."
fields = {"usuario_id": "123"}
files = [("archivo", "test.txt", contenido)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")
doc_id = None
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Resultado subida:", res)
        doc_id = res.get("document_id")
except Exception as e:
    print("Error:", e)

if doc_id:
    print(f"\n3. Verificando integridad de {doc_id}...")
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:8000/documents/{doc_id}/verificar") as resp:
            print("Verificacion:", json.loads(resp.read().decode('utf-8')))
    except Exception as e:
        print("Error:", e)
