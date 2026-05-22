import os
from dotenv import load_dotenv

load_dotenv()

variables = ["GROQ_API_KEY", "COHERE_API_KEY", "GEMINI_API_KEY", "OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"]

print("Estado de variables de entorno configuradas:")
for var in variables:
    val = os.environ.get(var, "")
    if val:
        print(f"- {var}: Configurada (longitud={len(val)}, inicio={val[:6]}...)")
    else:
        print(f"- {var}: No configurada")
