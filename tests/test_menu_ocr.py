import base64
import urllib.request
import json
import mimetypes
import os

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

# Ruta de la imagen provista en la conversación
ruta_menu = r"C:\Users\carde\.gemini\antigravity\brain\0a09158e-f4ea-4614-8063-f4551b3113b9\media__1779417006159.jpg"

if not os.path.exists(ruta_menu):
    print(f"Error: No se encontró la imagen en {ruta_menu}")
    exit(1)

with open(ruta_menu, "rb") as f:
    imagen_bytes = f.read()

print(f"Imagen del menú encontrada: {ruta_menu} ({len(imagen_bytes)} bytes)")
print("Enviando al endpoint de carga /documents/ del backend...")

fields = {"usuario_id": "123"}
files = [("archivo", "menu_pizzeria.jpg", imagen_bytes)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")

try:
    with urllib.request.urlopen(req, timeout=90.0) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("\n[OK] ¡El servidor procesó el menú con éxito!")
        print("Respuesta de la API de carga:")
        print(json.dumps(res, indent=4, ensure_ascii=False))
        
        doc_id = res.get("document_id")
        ruta_emb = f"./depuracion_local/embeddings_{doc_id}.json"
        
        if os.path.exists(ruta_emb):
            with open(ruta_emb, "r", encoding="utf-8") as f:
                emb_data = json.load(f)
                fragmentos = emb_data.get("fragmentos", [])
                print(f"\nSe generaron {len(fragmentos)} fragmento(s).")
                print("--- Texto extraído por Gemini OCR (completo) ---")
                for frag in fragmentos:
                    print(frag.get("fragmento"))
except urllib.error.HTTPError as he:
    print(f"\n[ERROR] El servidor respondió con código {he.code}:")
    try:
        print("Detalle:", he.read().decode('utf-8'))
    except Exception:
        pass
except Exception as e:
    print("\n[ERROR] Error de conexión:", e)
