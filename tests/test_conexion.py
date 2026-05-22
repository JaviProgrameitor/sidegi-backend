import os
import urllib.request
import json
from dotenv import load_dotenv

# Carga variables desde el nivel superior
load_dotenv(dotenv_path="../.env")
load_dotenv()

url = os.environ.get("SUPABASE_URL", "").rstrip('/')
key = os.environ.get("SUPABASE_SERVICE_KEY", "")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
    "Content-Type": "application/json"
}

print(f"URL de Supabase: {url}")
print(f"Clave disponible: {len(key) > 0}")

try:
    req = urllib.request.Request(f"{url}/rest/v1/users?select=id_user", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        print("Conexión con Supabase verificada con éxito (tabla 'users'):")
        print(content)
except Exception as e:
    print(f"Error al conectar con Supabase: {e}")
    if hasattr(e, 'read'):
        try:
            print("Respuesta de error:", e.read().decode('utf-8'))
        except Exception:
            pass
