import base64
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

# Imagen de 1x1 px transparente en formato PNG
imagen_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
imagen_bytes = base64.b64decode(imagen_b64)

print("Iniciando prueba de OCR con la API de Gemini...")
fields = {"usuario_id": "888"}
files = [("archivo", "prueba_ocr.png", imagen_bytes)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("Resultado exitoso inesperado (debería fallar o estar vacío para 1x1):", res)
except urllib.error.HTTPError as he:
    print(f"\n[OK] El servidor respondió HTTP {he.code} como se esperaba:")
    print("Detalle:", he.read().decode('utf-8'))
except Exception as e:
    print("Error inesperado en la conexión:", e)
