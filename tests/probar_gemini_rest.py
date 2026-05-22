import os
import httpx
from dotenv import load_dotenv

load_dotenv()

api_key = os.environ.get("GEMINI_API_KEY", "")
if not api_key:
    print("GEMINI_API_KEY no encontrada.")
    exit(1)

# Usamos gemini-2.5-flash que es compatible y de última generación
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
headers = {"Content-Type": "application/json"}
payload = {
    "contents": [
        {
            "parts": [
                {"text": "Responde con una sola palabra: 'Conectado'."}
            ]
        }
    ],
    "generationConfig": {
        "temperature": 0.2
    }
}

try:
    print("Enviando petición HTTP POST a Gemini API (gemini-2.5-flash)...")
    response = httpx.post(url, headers=headers, json=payload, timeout=10.0)
    print(f"Respuesta HTTP Status: {response.status_code}")
    if response.status_code == 200:
        data = response.json()
        texto = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        print(f"Respuesta de Gemini: '{texto}'")
    else:
        print("Error en la respuesta:", response.text)
except Exception as e:
    print("Error al conectar con Gemini:", e)
