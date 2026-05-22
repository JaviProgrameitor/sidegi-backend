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

# RPCs comunes a probar
rpcs = ["exec_sql", "run_sql", "execute_sql", "query_sql", "sql"]

for rpc in rpcs:
    print(f"\nProbando RPC: {rpc}...")
    # Intenta ejecutar un simple SELECT 1;
    payload = {"query": "SELECT 1;"}
    # En algunos RPCs el parametro se llama sql o query
    url_rpc = f"{url}/rest/v1/rpc/{rpc}"
    
    # Probamos con parámetro "query"
    try:
        req = urllib.request.Request(url_rpc, data=json.dumps(payload).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            print(f"[EXITO] {rpc} con 'query': {content}")
            continue
    except Exception as e:
        print(f"[FALLO] {rpc} con 'query': {e}")
        if hasattr(e, 'read'):
            try:
                print("   Detalle:", e.read().decode('utf-8'))
            except Exception:
                pass
                
    # Probamos con parametro "sql"
    payload_sql = {"sql": "SELECT 1;"}
    try:
        req = urllib.request.Request(url_rpc, data=json.dumps(payload_sql).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            print(f"[EXITO] {rpc} con 'sql': {content}")
            continue
    except Exception as e:
        print(f"[FALLO] {rpc} con 'sql': {e}")
        if hasattr(e, 'read'):
            try:
                print("   Detalle:", e.read().decode('utf-8'))
            except Exception:
                pass
