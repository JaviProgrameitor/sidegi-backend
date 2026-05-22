import os
import httpx
from groq import AsyncGroq
import groq

async def completar_chat_con_fallback(messages, temperature=0.3, max_tokens=1500):
    """
    Realiza una inferencia de chat con Groq utilizando una lista de modelos
    con rotación y fallback automático en caso de rate limits (429) o errores.
    Si Groq falla en todos sus modelos (o se agotan los tokens de la cuenta),
    realiza un fallback a Gemini API (gemini-2.5-flash) mediante una petición REST asíncrona.
    """
    groq_api_key = os.environ.get("GROQ_API_KEY", "")
    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    
    # 1. Intentar con Groq si la clave está disponible
    if groq_api_key:
        client = AsyncGroq(api_key=groq_api_key)
        # Los dos modelos principales del usuario en Groq y el modelo agenticio compound
        modelos = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "compound"]
        
        for modelo in modelos:
            try:
                print(f"Intentando inferencia en Groq con el modelo: {modelo}...")
                respuesta = await client.chat.completions.create(
                    model=modelo,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                print(f"Inferencia completada con éxito usando el modelo de Groq: {modelo}")
                return respuesta.choices[0].message.content
            except groq.RateLimitError as e:
                print(f"Límite de tasa (429) alcanzado para el modelo {modelo} en Groq. Intentando fallback...")
            except Exception as e:
                print(f"Error al invocar el modelo {modelo} en Groq. Detalle: {e}. Intentando fallback...")
                
    # 2. Si fallaron los modelos de Groq, o no hay clave de Groq, intentar con Gemini API (REST)
    if gemini_api_key:
        try:
            print("Iniciando fallback a Gemini API (gemini-2.5-flash) vía REST...")
            
            # Mapear mensajes de formato OpenAI a formato Gemini REST
            system_instruction = ""
            gemini_messages = []
            
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                if role == "system":
                    system_instruction += content + "\n"
                elif role in ("user", "human"):
                    gemini_messages.append({
                        "role": "user",
                        "parts": [{"text": content}]
                    })
                elif role in ("assistant", "model", "bot"):
                    gemini_messages.append({
                        "role": "model",
                        "parts": [{"text": content}]
                    })
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            
            payload = {
                "contents": gemini_messages,
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens
                }
            }
            
            if system_instruction:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_instruction.strip()}]
                }
                
            async with httpx.AsyncClient() as http_client:
                response = await http_client.post(url, headers=headers, json=payload, timeout=45.0)
                
            if response.status_code == 200:
                data = response.json()
                texto_gemini = data["candidates"][0]["content"]["parts"][0]["text"]
                print("Inferencia completada con éxito usando Gemini API (gemini-2.5-flash) de Google.")
                return texto_gemini
            else:
                print(f"Error en respuesta de Gemini REST (Status {response.status_code}): {response.text}")
        except Exception as e:
            print(f"Error crítico al invocar fallback a Gemini REST: {e}")
            
    # Si todo falla, levantamos una excepción clara
    raise Exception("Todos los proveedores y modelos de inferencia de IA (Groq y Gemini) fallaron o no están disponibles.")
