import os

ruta_historial = r"C:\Users\carde\AppData\Roaming\Microsoft\Windows\PowerShell\PSReadLine\ConsoleHost_history.txt"

palabras_clave = ["supabase", "postgres", "psql", "db", "key", "password", "5432"]

if os.path.exists(ruta_historial):
    print("Archivo de historial encontrado. Buscando coincidencias...")
    coincidencias = []
    with open(ruta_historial, "r", encoding="utf-8", errors="ignore") as f:
        for idx, linea in enumerate(f, 1):
            linea_lower = linea.lower()
            if any(palabra in linea_lower for palabra in palabras_clave):
                coincidencias.append((idx, linea.strip()))
                
    print(f"Total de líneas coincidentes encontradas: {len(coincidencias)}")
    # Mostramos las últimas 50 coincidencias (que son las más recientes)
    for idx, coincidencia in coincidencias[-100:]:
        print(f"Línea {idx}: {coincidencia}")
else:
    print("No se encontró el archivo de historial de PowerShell.")
