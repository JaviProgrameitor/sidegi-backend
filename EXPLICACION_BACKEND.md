# El backend de SIGEDI por dentro

En pocas palabras: el backend es el cerebro que hace el trabajo sucio. El frontend (la app en Next.js) se encarga de que todo se vea bonito e interactivo, mientras que este backend en FastAPI procesa los archivos pesados, calcula vectores para las búsquedas semánticas y ejecuta los análisis de auditoría con inteligencia artificial.

## Cómo se comunican el frontend y el backend

Trabajan en pareja a través de peticiones HTTP. El flujo típico funciona así:

### 1. Subir y preparar documentos
Cuando arrastras un PDF en la aplicación:
- El frontend le envía el archivo al backend.
- El backend extrae todo el texto limpio.
- Fragmenta el texto en pedazos pequeños y genera un "embedding" (una representación numérica) para cada fragmento usando Cohere.
- Guarda la información en Supabase (y guarda una copia local en `depuracion_local` por si acaso).
- Si borras un archivo, el frontend le avisa al backend para que marque la columna `esta_eliminado` como `1` (un soft delete). Esto es clave: el archivo no se destruye de la base de datos, pero la búsqueda semántica lo ignorará de inmediato.

### 2. Buscar respuestas (RAG)
Cuando le haces una pregunta al buscador inteligente:
- El frontend le manda tu consulta de texto al backend.
- El backend genera el vector de la pregunta y busca en la base de datos los fragmentos de documentos que más se parecen a lo que estás preguntando. Aquí se aplica el filtro de soft delete para no buscar en archivos borrados.
- El backend junta esos fragmentos y se los envía como contexto a Groq (usando Llama 3.3).
- **Si Groq se queda sin tokens o da error de rate limit (429)**, el backend automáticamente rota a Llama 3.1 o salta al modelo Gemini 2.5 Flash de Google usando su API Key.
- El modelo redacta la respuesta usando esos fragmentos como fuente y el backend se la devuelve al frontend formateada en Markdown y HTML para que la muestre en pantalla.

### 3. Herramientas de auditoría avanzada (Élite)
Cuando pides una auditoría (comparar contratos, buscar conflictos de fechas, resumir en viñetas o evaluar la calidad del texto escaneado):
- El frontend llama a uno de los endpoints de la API (`/comparar`, `/detectar-conflictos`, `/calidad-ocr`, etc.).
- El backend recupera el texto del documento (desde la base de datos o el fallback local) y estructura un prompt especializado para la IA.
- Retorna el análisis detallado estructurado en JSON para que el frontend pueda pintar los gráficos de riesgo y las tablas correspondientes.
