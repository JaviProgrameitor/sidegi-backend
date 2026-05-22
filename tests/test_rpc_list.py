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
    "Authorization": f"Bearer {key}"
}

try:
    req = urllib.request.Request(f"{url}/rest/v1/", headers=headers, method="GET")
    with urllib.request.urlopen(req) as resp:
        content = json.loads(resp.read().decode('utf-8'))
        paths = content.get("paths", {})
        print("Rutas detectadas en Supabase REST API:")
        for path in paths.keys():
            if path.startswith("/rpc/"):
                print(f"- RPC: {path}")
            else:
                print(f"- Tabla/Ruta: {path}")
except Exception as e:
    print(f"Error: {e}")
