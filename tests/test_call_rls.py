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
    "Content-Type": "application/json"
}

url_rpc = f"{url}/rest/v1/rpc/rls_auto_enable"

print(f"Probando /rpc/rls_auto_enable...")

# Probamos con payload vacío
try:
    req = urllib.request.Request(url_rpc, data=json.dumps({}).encode('utf-8'), headers=headers, method="POST")
    with urllib.request.urlopen(req) as resp:
        content = resp.read().decode('utf-8')
        print(f"[EXITO] Retorno con vacío: {content}")
except Exception as e:
    print(f"[FALLO] Con vacío: {e}")
    if hasattr(e, 'read'):
        try:
            print("   Detalle:", e.read().decode('utf-8'))
        except Exception:
            pass

# Probamos con parámetros típicos si adivinamos qué hace
# Quizás recibe tabla o similar
payloads_adivinar = [
    {"table": "documentos_integridad"},
    {"table_name": "documentos_integridad"},
    {"schema": "public"},
    {"enable": True}
]

for pl in payloads_adivinar:
    try:
        req = urllib.request.Request(url_rpc, data=json.dumps(pl).encode('utf-8'), headers=headers, method="POST")
        with urllib.request.urlopen(req) as resp:
            content = resp.read().decode('utf-8')
            print(f"[EXITO] Con payload {pl}: {content}")
    except Exception as e:
        print(f"[FALLO] Con payload {pl}: {e}")
        if hasattr(e, 'read'):
            try:
                print("   Detalle:", e.read().decode('utf-8'))
            except Exception:
                pass
