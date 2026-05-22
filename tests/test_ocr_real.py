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

# Ruta de una imagen en los artefactos
appdata_dir = r"C:\Users\carde\.gemini\antigravity"
conv_id = "0a09158e-f4ea-4614-8063-f4551b3113b9"
posibles_rutas = [
    os.path.join(appdata_dir, "brain", conv_id, ".tempmediaStorage", "media_0a09158e-f4ea-4614-8063-f4551b3113b9_1779406716002.png"),
    os.path.join(appdata_dir, "brain", conv_id, ".tempmediaStorage", "media_0a09158e-f4ea-4614-8063-f4551b3113b9_1779406719637.png"),
    os.path.join(appdata_dir, "brain", conv_id, ".tempmediaStorage", "media_0a09158e-f4ea-4614-8063-f4551b3113b9_1779406723660.png")
]

imagen_bytes = None
nombre_usado = ""
for ruta in posibles_rutas:
    if os.path.exists(ruta):
        try:
            with open(ruta, "rb") as f:
                imagen_bytes = f.read()
            nombre_usado = os.path.basename(ruta)
            print(f"Imagen encontrada en: {ruta} ({len(imagen_bytes)} bytes)")
            break
        except Exception as e:
            print(f"Error leyendo {ruta}: {e}")

if not imagen_bytes:
    print("No se encontró ninguna imagen de prueba en los artefactos. Se utilizará una imagen simulada generada dinámicamente con texto básico si Pillow está disponible...")
    try:
        from PIL import Image, ImageDraw
        img = Image.new('RGB', (200, 100), color = (73, 109, 137))
        # Intentar dibujar algo de texto si es posible, o simplemente guardar
        import io
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='PNG')
        imagen_bytes = img_byte_arr.getvalue()
        nombre_usado = "imagen_generada.png"
        print("Imagen generada con Pillow de forma básica.")
    except Exception as e:
        print("Pillow no está disponible para generar una imagen. Creando un archivo de texto como fallback.")
        imagen_bytes = b"Este es un texto simulado de prueba."
        nombre_usado = "prueba_texto.txt"

print(f"Iniciando prueba de OCR en endpoint /documents/ con archivo: {nombre_usado}...")
fields = {"usuario_id": "999"}
files = [("archivo", nombre_usado, imagen_bytes)]
body, headers = make_multipart_body(fields, files)

req = urllib.request.Request("http://127.0.0.1:8000/documents/", data=body, headers=headers, method="POST")
try:
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        res = json.loads(resp.read().decode('utf-8'))
        print("\n[OK] El servidor procesó el documento con éxito!")
        print("Respuesta de la API de carga:")
        print(json.dumps(res, indent=4, ensure_ascii=False))
        
        # Verificar la copia local para ver qué texto se extrajo
        doc_id = res.get("document_id")
        ruta_copia = f"./depuracion_local/{doc_id}.json"
        ruta_emb = f"./depuracion_local/embeddings_{doc_id}.json"
        
        if os.path.exists(ruta_copia):
            print(f"\nCopia local de integridad encontrada para documento {doc_id}.")
        if os.path.exists(ruta_emb):
            with open(ruta_emb, "r", encoding="utf-8") as f:
                emb_data = json.load(f)
                fragmentos = emb_data.get("fragmentos", [])
                print(f"Se generaron {len(fragmentos)} fragmentos indexados.")
                print("Texto extraído de los primeros fragmentos:")
                for i, frag in enumerate(fragmentos[:3]):
                    print(f"--- Fragmento {i+1} ---")
                    print(frag.get("fragmento"))
except urllib.error.HTTPError as he:
    print(f"\n[ERROR] El servidor respondió con código {he.code}:")
    try:
        print("Detalle:", he.read().decode('utf-8'))
    except Exception:
        pass
except Exception as e:
    print("\n[ERROR] Error de conexión:", e)
