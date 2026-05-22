import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv(dotenv_path="../.env")
load_dotenv()

url = os.environ.get("SUPABASE_URL", "").rstrip('/')
key = os.environ.get("SUPABASE_SERVICE_KEY", "")

profiles = ["public", "extensions", "auth", "storage", "graphql"]

for profile in profiles:
    print(f"\n--- Listando rutas del perfil: {profile} ---")
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept-Profile": profile
    }
    try:
        req = urllib.request.Request(f"{url}/rest/v1/", headers=headers, method="GET")
        with urllib.request.urlopen(req) as resp:
            content = json.loads(resp.read().decode('utf-8'))
            paths = content.get("paths", {})
            print(f"Rutas encontradas en {profile}:")
            for path in list(paths.keys())[:15]:  # Mostrar hasta 15
                print(f"- {path}")
            if len(paths) > 15:
                print(f"... y {len(paths) - 15} más")
    except Exception as e:
        print(f"Error en perfil {profile}: {e}")
