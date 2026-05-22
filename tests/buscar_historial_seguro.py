import os
import sys

# Forzar salida en UTF-8 para evitar errores de codificación en Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ruta_historial = r"C:\Users\carde\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"

palabras_clave = ["supabase", "postgres", "psql", "db", "key", "password", "5432", "ihzhdrqayivwnorttsto"]

if os.path.exists(ruta_historial):
    print("Archivo de historial encontrado. Buscando coincidencias...")
    coincidencias = []
    with open(ruta_historial, "r", encoding="utf-8", errors="ignore") as f:
        for idx, linea in enumerate(f, 1):
            linea_lower = linea.lower()
            if any(palabra in linea_lower for palabra in palabras_clave):
                coincidencias.append((idx, linea.strip()))
                
    print(f"Total de líneas coincidentes encontradas: {len(coincidencias)}")
    # Mostramos las últimas 150 coincidencias de forma segura
    for idx, coincidencia in coincidencias[-150:]:
        # Reemplazar emojis o caracteres raros que fallen al imprimir
        safe_line = coincidencia.encode('utf-8', errors='replace').decode('utf-8')
        print(f"Línea {idx}: {safe_line}")
else:
    print("No se encontró el archivo de historial de PowerShell.")
