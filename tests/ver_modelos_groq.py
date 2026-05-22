import os
import groq
from dotenv import load_dotenv

# Cargar .env desde la raíz del backend
load_dotenv()

api_key = os.environ.get("GROQ_API_KEY", "")
if not api_key:
    print("GROQ_API_KEY no encontrada en las variables de entorno.")
    exit(1)

print(f"GROQ_API_KEY encontrada: {api_key[:6]}...{api_key[-4:] if len(api_key) > 4 else ''}")

try:
    client = groq.Groq(api_key=api_key)
    modelos = client.models.list().data
    print("\nModelos de Groq disponibles:")
    for m in modelos:
        print(f"- {m.id}")
except Exception as e:
    print("Error al listar modelos de Groq:", e)
