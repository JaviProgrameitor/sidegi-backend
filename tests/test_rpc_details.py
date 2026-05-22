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
        rpc_path = "/rpc/rls_auto_enable"
        if rpc_path in paths:
            print(f"Detalles de {rpc_path}:")
            print(json.dumps(paths[rpc_path], indent=4))
        else:
            print(f"No se encontró {rpc_path} en los paths del OpenAPI.")
except Exception as e:
    print(f"Error: {e}")
