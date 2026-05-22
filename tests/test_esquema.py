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
}

print(f"Obteniendo esquema de API REST de: {url}/rest/v1/")

try:
    req = urllib.request.Request(f"{url}/rest/v1/", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        content = json.loads(resp.read().decode('utf-8'))
        definitions = content.get("definitions", {})
        print("Tablas detectadas en Supabase:")
        for table in definitions.keys():
            print(f"- {table}")
except Exception as e:
    print(f"Error: {e}")
