import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

url = os.environ.get("SUPABASE_URL", "").rstrip('/')
key = os.environ.get("SUPABASE_SERVICE_KEY", "")

headers = {
    "apikey": key,
    "Authorization": f"Bearer {key}",
}

print(f"Obteniendo metadatos detallados de: {url}/rest/v1/")

try:
    req = urllib.request.Request(f"{url}/rest/v1/", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        content = json.loads(resp.read().decode('utf-8'))
        definitions = content.get("definitions", {})
        
        for tabla in ["users", "folders"]:
            if tabla in definitions:
                print(f"\n--- Estructura de tabla: {tabla} ---")
                def_tabla = definitions[tabla]
                propiedades = def_tabla.get("properties", {})
                requeridos = def_tabla.get("required", [])
                
                for prop, detalles in propiedades.items():
                    tipo = detalles.get("type", "desconocido")
                    req_str = " (REQUERIDO)" if prop in requeridos else ""
                    print(f"  * {prop}: {tipo}{req_str}")
            else:
                print(f"\nLa tabla '{tabla}' no se encontró en las definiciones.")
except Exception as e:
    print(f"Error: {e}")
