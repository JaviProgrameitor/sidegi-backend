import urllib.request
import json
import os

api_key = "AIzaSyDytEJFRjecMa3mi5HURFDQmSfvGhl9RIE"

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
print("Consultando modelos en v1beta...")
try:
    with urllib.request.urlopen(url) as response:
        datos = json.loads(response.read().decode('utf-8'))
        models = datos.get("models", [])
        print(f"Encontrados {len(models)} modelos.")
        for m in models:
            name = m.get("name")
            supported = m.get("supportedGenerationMethods", [])
            if "generateContent" in supported:
                print(f"- {name} (soporta generateContent)")
except Exception as e:
    print("Error en v1beta:", e)
    if hasattr(e, 'read'):
        try:
            print(e.read().decode('utf-8'))
        except Exception:
            pass

url_v1 = f"https://generativelanguage.googleapis.com/v1/models?key={api_key}"
print("\nConsultando modelos en v1...")
try:
    with urllib.request.urlopen(url_v1) as response:
        datos = json.loads(response.read().decode('utf-8'))
        models = datos.get("models", [])
        print(f"Encontrados {len(models)} modelos.")
        for m in models:
            name = m.get("name")
            supported = m.get("supportedGenerationMethods", [])
            if "generateContent" in supported:
                print(f"- {name} (soporta generateContent)")
except Exception as e:
    print("Error en v1:", e)
    if hasattr(e, 'read'):
        try:
            print(e.read().decode('utf-8'))
        except Exception:
            pass
