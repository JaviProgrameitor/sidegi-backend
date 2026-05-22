import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

key = os.environ.get("SUPABASE_SERVICE_KEY", "")
# El ref del proyecto es la parte inicial de la url de Supabase
# url: https://ihzhdrqayivwnorttsto.supabase.co
# ref: ihzhdrqayivwnorttsto
ref = "ihzhdrqayivwnorttsto"

print(f"Probando API de administración de Supabase con ref: {ref}")

# Endpoint para ejecutar consultas en la API de administración (usado por la consola)
url_mgmt = f"https://api.supabase.com/v1/projects/{ref}/query"
# En la consola de Supabase, la petición suele ser POST con el cuerpo:
# {"query": "SELECT 1;"}
payload = {"query": "SELECT 1;"}

headers = {
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

try:
    req = urllib.request.Request(url_mgmt, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        print("ÉXITO al conectar a la API de administración con la service role key:")
        print(content)
except Exception as e:
    print(f"FALLO en API de administración: {e}")
    if hasattr(e, 'read'):
        try:
            print("   Detalle de error:", e.read().decode('utf-8'))
        except Exception:
            pass
            
# Probemos también obtener detalles del proyecto en /v1/projects/{ref}
try:
    url_proj = f"https://api.supabase.com/v1/projects/{ref}"
    req = urllib.request.Request(url_proj, headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        print("ÉXITO al obtener datos del proyecto con la service role key:")
        print(content)
except Exception as e:
    print(f"FALLO al obtener datos del proyecto: {e}")
    if hasattr(e, 'read'):
        try:
            print("   Detalle de error:", e.read().decode('utf-8'))
        except Exception:
            pass
