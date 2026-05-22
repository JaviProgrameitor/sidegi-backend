import os
import re

raiz = r"C:\Users\carde\Desktop\MUACK"
ref_proyecto = "ihzhdrqayivwnorttsto"

extensiones_interes = [".env", ".txt", ".json", ".py", ".md", ".sql", ".sh", ".bat", ".toml"]

print(f"Buscando el ref del proyecto '{ref_proyecto}' en {raiz}...")

for root, dirs, files in os.walk(raiz):
    # Omitir carpetas grandes e innecesarias
    dirs[:] = [d for d in dirs if d not in ["node_modules", ".git", "venv", ".venv", "__pycache__", ".idea", ".vscode", "vcpkg"]]
    
    for f in files:
        nombre, ext = os.path.splitext(f)
        if ext.lower() in extensiones_interes or f.startswith(".env"):
            ruta_completa = os.path.join(root, f)
            try:
                with open(ruta_completa, "r", encoding="utf-8", errors="ignore") as archivo:
                    contenido = archivo.read()
                    if ref_proyecto in contenido or "postgres" in contenido.lower() or "supabase" in contenido.lower():
                        # Buscar si hay cadenas de conexion de postgresql o contraseñas
                        lineas = contenido.splitlines()
                        for idx, linea in enumerate(lineas, 1):
                            linea_lower = linea.lower()
                            # Buscar postgresql:// o postgres:// o palabras clave
                            if "postgres" in linea_lower or "password" in linea_lower or ref_proyecto in linea_lower:
                                # Reemplazar si contiene la service key completa para no contaminar la salida
                                if "key" in linea_lower and len(linea) > 100:
                                    linea_safe = linea[:30] + "..."
                                else:
                                    linea_safe = linea.strip()
                                print(f"Archivo: {os.path.relpath(ruta_completa, raiz)} (Línea {idx}): {linea_safe}")
            except Exception as e:
                pass
print("Búsqueda finalizada.")
